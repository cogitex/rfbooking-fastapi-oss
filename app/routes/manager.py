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

"""Manager-specific routes."""

from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_manager, check_equipment_manager
from app.models.booking import Booking
from app.models.equipment import Equipment, EquipmentManager, EquipmentType
from app.models.user import User

router = APIRouter(prefix="/api/manager")


class BookingUpdate(BaseModel):
    """Booking update request."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None


@router.get("/equipment")
async def list_managed_equipment(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """List equipment managed by current user."""
    if current_user.is_admin:
        # Admins see all equipment
        equipment = db.query(Equipment).filter(Equipment.is_active == True).all()
    else:
        # Managers see only assigned equipment
        equipment = (
            db.query(Equipment)
            .join(EquipmentManager, EquipmentManager.equipment_id == Equipment.id)
            .filter(
                EquipmentManager.manager_id == current_user.id,
                Equipment.is_active == True,
            )
            .all()
        )

    return {
        "success": True,
        "equipment": [e.to_dict() for e in equipment],
    }


@router.get("/equipment/{equipment_id}/bookings")
async def list_equipment_bookings(
    equipment_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """List bookings for managed equipment."""
    # Check if user manages this equipment
    if not check_equipment_manager(current_user, equipment_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a manager of this equipment",
        )

    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    query = db.query(Booking).filter(Booking.equipment_id == equipment_id)

    if start_date:
        query = query.filter(Booking.end_date >= start_date)

    if end_date:
        query = query.filter(Booking.start_date <= end_date)

    if status_filter:
        query = query.filter(Booking.status == status_filter)

    bookings = query.order_by(Booking.start_date, Booking.start_time).all()

    return {
        "success": True,
        "equipment": equipment.to_dict(),
        "bookings": [b.to_dict() for b in bookings],
    }


@router.put("/bookings/{booking_id}")
async def update_booking(
    booking_id: int,
    data: BookingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Update booking on managed equipment."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    # Check if user manages this equipment
    if not check_equipment_manager(current_user, booking.equipment_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a manager of this equipment",
        )

    if booking.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit cancelled booking",
        )

    # Apply updates
    if data.start_date:
        booking.start_date = data.start_date
    if data.end_date:
        booking.end_date = data.end_date
    if data.description is not None:
        booking.description = data.description

    db.commit()
    db.refresh(booking)

    return {
        "success": True,
        "booking": booking.to_dict(),
        "message": "Booking updated",
    }


@router.delete("/bookings/{booking_id}")
async def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Cancel booking on managed equipment."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    # Check if user manages this equipment
    if not check_equipment_manager(current_user, booking.equipment_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a manager of this equipment",
        )

    if booking.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is already cancelled",
        )

    booking.status = "cancelled"
    db.commit()

    return {
        "success": True,
        "message": "Booking cancelled",
    }


@router.get("/controlled-types")
async def list_controlled_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """List equipment types where user manages at least one equipment."""
    if current_user.is_admin:
        # Admins see all types
        types = db.query(EquipmentType).filter(EquipmentType.is_active == True).all()
    else:
        # Get types of managed equipment
        managed_type_ids = (
            db.query(Equipment.type_id)
            .join(EquipmentManager, EquipmentManager.equipment_id == Equipment.id)
            .filter(
                EquipmentManager.manager_id == current_user.id,
                Equipment.is_active == True,
                Equipment.type_id.isnot(None),
            )
            .distinct()
            .all()
        )
        managed_type_ids = [t[0] for t in managed_type_ids]

        types = (
            db.query(EquipmentType)
            .filter(
                EquipmentType.id.in_(managed_type_ids),
                EquipmentType.is_active == True,
            )
            .all()
        )

    return {
        "success": True,
        "types": [t.to_dict() for t in types],
    }
