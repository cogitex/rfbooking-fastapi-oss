# RFBooking FastAPI OSS - Self-hosted Equipment Booking System
# Copyright (C) 2025 Oleg Tokmakov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Equipment management routes."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user, require_admin, check_equipment_access
from app.models.equipment import Equipment, EquipmentType, EquipmentTypeUser, EquipmentManager
from app.models.user import User
from app.utils.helpers import sanitize_input
from app.services.ai_service import invalidate_equipment_cache

router = APIRouter()


# Pydantic schemas
class EquipmentTypeCreate(BaseModel):
    """Equipment type creation request."""

    name: str
    description: Optional[str] = None


class EquipmentTypeUpdate(BaseModel):
    """Equipment type update request."""

    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    manager_notifications_enabled: Optional[bool] = None


class EquipmentCreate(BaseModel):
    """Equipment creation request."""

    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    type_id: Optional[int] = None
    next_calibration_date: Optional[date] = None


class EquipmentUpdate(BaseModel):
    """Equipment update request."""

    name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    type_id: Optional[int] = None
    next_calibration_date: Optional[date] = None
    is_active: Optional[bool] = None


# Equipment Type Routes
@router.get("/api/admin/equipment-types")
async def list_equipment_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all equipment types."""
    types = db.query(EquipmentType).order_by(EquipmentType.name).all()
    return {
        "success": True,
        "types": [t.to_dict() for t in types],
    }


@router.post("/api/admin/equipment-types")
async def create_equipment_type(
    data: EquipmentTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new equipment type (admin only)."""
    # Check if name already exists
    existing = db.query(EquipmentType).filter(EquipmentType.name == data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Equipment type with this name already exists",
        )

    # Create type
    eq_type = EquipmentType(
        name=sanitize_input(data.name, 255),
        description=sanitize_input(data.description, 1000) if data.description else None,
    )
    db.add(eq_type)
    db.commit()
    db.refresh(eq_type)

    # Grant access to all active users
    users = db.query(User).filter(User.is_active == True).all()
    for user in users:
        type_access = EquipmentTypeUser(
            type_id=eq_type.id,
            user_id=user.id,
            granted_by=current_user.id,
        )
        db.add(type_access)

    db.commit()

    return {
        "success": True,
        "type": eq_type.to_dict(),
        "message": f"Equipment type '{eq_type.name}' created",
    }


@router.put("/api/admin/equipment-types/{type_id}")
async def update_equipment_type(
    type_id: int,
    data: EquipmentTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update equipment type (admin only)."""
    eq_type = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    if not eq_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment type not found",
        )

    # Check for name conflict
    if data.name and data.name != eq_type.name:
        existing = db.query(EquipmentType).filter(EquipmentType.name == data.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Equipment type with this name already exists",
            )
        eq_type.name = sanitize_input(data.name, 255)

    if data.description is not None:
        eq_type.description = sanitize_input(data.description, 1000) if data.description else None

    if data.is_active is not None:
        eq_type.is_active = data.is_active

    if data.manager_notifications_enabled is not None:
        eq_type.manager_notifications_enabled = data.manager_notifications_enabled

    db.commit()
    db.refresh(eq_type)

    return {
        "success": True,
        "type": eq_type.to_dict(),
        "message": f"Equipment type '{eq_type.name}' updated",
    }


@router.delete("/api/admin/equipment-types/{type_id}")
async def delete_equipment_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Soft delete equipment type (admin only)."""
    eq_type = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    if not eq_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment type not found",
        )

    eq_type.is_active = False
    db.commit()

    return {
        "success": True,
        "message": f"Equipment type '{eq_type.name}' deactivated",
    }


# Equipment Routes
@router.get("/api/equipment")
async def list_equipment(
    type_id: Optional[int] = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List equipment (filtered by user's type access)."""
    query = db.query(Equipment)

    # Filter by type if specified
    if type_id:
        query = query.filter(Equipment.type_id == type_id)

    # Filter by active status
    if not include_inactive:
        query = query.filter(Equipment.is_active == True)

    # Get user's accessible type IDs
    if not current_user.is_admin:
        accessible_type_ids = (
            db.query(EquipmentTypeUser.type_id)
            .filter(EquipmentTypeUser.user_id == current_user.id)
            .all()
        )
        accessible_type_ids = [t[0] for t in accessible_type_ids]

        # Filter to accessible equipment
        query = query.filter(
            (Equipment.type_id.in_(accessible_type_ids)) | (Equipment.type_id.is_(None))
        )

    equipment = query.order_by(Equipment.name).all()

    return {
        "success": True,
        "equipment": [e.to_dict() for e in equipment],
    }


@router.get("/api/equipment/{equipment_id}")
async def get_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get equipment details."""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()

    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    # Check access
    if not check_equipment_access(current_user, equipment_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this equipment",
        )

    # Get managers
    managers = (
        db.query(User)
        .join(EquipmentManager, EquipmentManager.manager_id == User.id)
        .filter(EquipmentManager.equipment_id == equipment_id)
        .all()
    )

    result = equipment.to_dict()
    result["managers"] = [{"id": m.id, "name": m.name, "email": m.email} for m in managers]

    return {
        "success": True,
        "equipment": result,
    }


@router.post("/api/equipment")
async def create_equipment(
    data: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create new equipment (admin only)."""
    # Validate type if provided
    if data.type_id:
        eq_type = db.query(EquipmentType).filter(EquipmentType.id == data.type_id).first()
        if not eq_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid equipment type",
            )

    equipment = Equipment(
        name=sanitize_input(data.name, 255),
        description=sanitize_input(data.description, 10000) if data.description else None,
        location=sanitize_input(data.location, 255) if data.location else None,
        type_id=data.type_id,
        next_calibration_date=data.next_calibration_date,
    )
    db.add(equipment)
    db.commit()
    db.refresh(equipment)

    # Invalidate AI equipment cache
    invalidate_equipment_cache()

    return {
        "success": True,
        "equipment": equipment.to_dict(),
        "message": f"Equipment '{equipment.name}' created",
    }


@router.put("/api/equipment/{equipment_id}")
async def update_equipment(
    equipment_id: int,
    data: EquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update equipment (admin only)."""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()

    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    # Update fields
    if data.name is not None:
        equipment.name = sanitize_input(data.name, 255)

    if data.description is not None:
        equipment.description = sanitize_input(data.description, 10000) if data.description else None

    if data.location is not None:
        equipment.location = sanitize_input(data.location, 255) if data.location else None

    if data.type_id is not None:
        if data.type_id:
            eq_type = db.query(EquipmentType).filter(EquipmentType.id == data.type_id).first()
            if not eq_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid equipment type",
                )
        equipment.type_id = data.type_id or None

    if data.next_calibration_date is not None:
        equipment.next_calibration_date = data.next_calibration_date

    if data.is_active is not None:
        equipment.is_active = data.is_active

    db.commit()
    db.refresh(equipment)

    # Invalidate AI equipment cache
    invalidate_equipment_cache()

    return {
        "success": True,
        "equipment": equipment.to_dict(),
        "message": f"Equipment '{equipment.name}' updated",
    }


@router.delete("/api/equipment/{equipment_id}")
async def delete_equipment(
    equipment_id: int,
    new_status: Optional[int] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Soft delete/deactivate equipment (admin only).

    Use status query parameter to toggle:
    - status=0: Deactivate equipment
    - status=1: Activate equipment
    - No status: Deactivate equipment (default)
    """
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()

    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    # Determine status (default is deactivate)
    is_active = new_status == 1 if new_status is not None else False
    action = "activated" if is_active else "deactivated"

    equipment.is_active = is_active
    db.commit()

    # Invalidate AI equipment cache
    invalidate_equipment_cache()

    return {
        "success": True,
        "message": f"Equipment '{equipment.name}' {action}",
    }


# Equipment Managers Routes
@router.get("/api/admin/equipment/{equipment_id}/managers")
async def list_equipment_managers(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List managers for equipment."""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()

    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    managers = (
        db.query(User)
        .join(EquipmentManager, EquipmentManager.manager_id == User.id)
        .filter(EquipmentManager.equipment_id == equipment_id)
        .all()
    )

    return {
        "success": True,
        "managers": [{"id": m.id, "name": m.name, "email": m.email} for m in managers],
    }


@router.post("/api/admin/equipment/{equipment_id}/managers")
async def assign_equipment_manager(
    equipment_id: int,
    manager_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Assign manager to equipment."""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    manager = db.query(User).filter(User.id == manager_id).first()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if already assigned
    existing = (
        db.query(EquipmentManager)
        .filter(
            EquipmentManager.equipment_id == equipment_id,
            EquipmentManager.manager_id == manager_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a manager for this equipment",
        )

    assignment = EquipmentManager(
        equipment_id=equipment_id,
        manager_id=manager_id,
        assigned_by=current_user.id,
    )
    db.add(assignment)
    db.commit()

    return {
        "success": True,
        "message": f"{manager.name} assigned as manager for {equipment.name}",
    }


@router.delete("/api/admin/equipment/{equipment_id}/managers/{manager_id}")
async def remove_equipment_manager(
    equipment_id: int,
    manager_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Remove manager from equipment."""
    assignment = (
        db.query(EquipmentManager)
        .filter(
            EquipmentManager.equipment_id == equipment_id,
            EquipmentManager.manager_id == manager_id,
        )
        .first()
    )

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager assignment not found",
        )

    db.delete(assignment)
    db.commit()

    return {
        "success": True,
        "message": "Manager removed from equipment",
    }


# Equipment Type User Access Routes
@router.get("/api/equipment-types/{type_id}/users")
async def list_type_users(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List users with access to equipment type."""
    if not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )

    eq_type = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    if not eq_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment type not found",
        )

    users = (
        db.query(User)
        .join(EquipmentTypeUser, EquipmentTypeUser.user_id == User.id)
        .filter(EquipmentTypeUser.type_id == type_id)
        .all()
    )

    return {
        "success": True,
        "users": [{"id": u.id, "name": u.name, "email": u.email} for u in users],
    }


@router.post("/api/equipment-types/{type_id}/users/{user_id}/grant")
async def grant_type_access(
    type_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grant user access to equipment type."""
    if not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )

    eq_type = db.query(EquipmentType).filter(EquipmentType.id == type_id).first()
    if not eq_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment type not found",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if already has access
    existing = (
        db.query(EquipmentTypeUser)
        .filter(
            EquipmentTypeUser.type_id == type_id,
            EquipmentTypeUser.user_id == user_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has access to this equipment type",
        )

    access = EquipmentTypeUser(
        type_id=type_id,
        user_id=user_id,
        granted_by=current_user.id,
    )
    db.add(access)
    db.commit()

    return {
        "success": True,
        "message": f"Access to '{eq_type.name}' granted to {user.name}",
    }


@router.delete("/api/equipment-types/{type_id}/users/{user_id}/revoke")
async def revoke_type_access(
    type_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke user access to equipment type."""
    if not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )

    access = (
        db.query(EquipmentTypeUser)
        .filter(
            EquipmentTypeUser.type_id == type_id,
            EquipmentTypeUser.user_id == user_id,
        )
        .first()
    )

    if not access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User doesn't have access to this equipment type",
        )

    db.delete(access)
    db.commit()

    return {
        "success": True,
        "message": "Access revoked",
    }
