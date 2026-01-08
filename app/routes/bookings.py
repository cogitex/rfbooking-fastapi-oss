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

"""Booking management routes."""

from datetime import date, time, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, validator
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import (
    get_current_user,
    check_equipment_access,
    check_equipment_manager,
)
from app.models.booking import Booking
from app.models.equipment import Equipment
from app.models.user import User
from app.utils.helpers import sanitize_input

router = APIRouter(prefix="/api/bookings")


class BookingCreate(BaseModel):
    """Booking creation request."""

    equipment_id: int
    start_date: date
    end_date: date
    start_time: time
    end_time: time
    description: Optional[str] = None

    @validator("end_date")
    def validate_dates(cls, v, values):
        if "start_date" in values and v < values["start_date"]:
            raise ValueError("End date must be on or after start date")
        return v


class BookingUpdate(BaseModel):
    """Booking update request."""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    description: Optional[str] = None


class BookingDescriptionUpdate(BaseModel):
    """Booking description update request."""

    description: str


def check_booking_conflicts(
    db: Session,
    equipment_id: int,
    start_date: date,
    end_date: date,
    start_time: time,
    end_time: time,
    exclude_booking_id: Optional[int] = None,
) -> List[Booking]:
    """Check for booking conflicts.

    Returns list of conflicting bookings.
    """
    query = db.query(Booking).filter(
        Booking.equipment_id == equipment_id,
        Booking.status == "active",
        # Date overlap check
        Booking.start_date <= end_date,
        Booking.end_date >= start_date,
    )

    if exclude_booking_id:
        query = query.filter(Booking.id != exclude_booking_id)

    potential_conflicts = query.all()

    # Filter for actual time conflicts
    conflicts = []
    for booking in potential_conflicts:
        # Check if there's actual time overlap
        if booking.overlaps_with(start_date, end_date, start_time, end_time):
            conflicts.append(booking)

    return conflicts


@router.get("")
async def list_bookings(
    equipment_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List bookings with optional filters."""
    query = db.query(Booking).options(joinedload(Booking.user), joinedload(Booking.equipment))

    # Apply filters
    if equipment_id:
        query = query.filter(Booking.equipment_id == equipment_id)

    if user_id:
        # Only allow viewing own bookings unless admin/manager
        if user_id != current_user.id and not current_user.is_manager:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view other users' bookings",
            )
        query = query.filter(Booking.user_id == user_id)

    if start_date:
        query = query.filter(Booking.end_date >= start_date)

    if end_date:
        query = query.filter(Booking.start_date <= end_date)

    if status_filter:
        query = query.filter(Booking.status == status_filter)

    # Order by date
    bookings = query.order_by(Booking.start_date, Booking.start_time).all()

    return {
        "success": True,
        "bookings": [b.to_dict() for b in bookings],
    }


@router.get("/{booking_id}")
async def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get booking details."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    # Check access
    can_view = (
        booking.user_id == current_user.id
        or current_user.is_admin
        or check_equipment_manager(current_user, booking.equipment_id, db)
    )

    if not can_view:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this booking",
        )

    return {
        "success": True,
        "booking": booking.to_dict(),
    }


@router.post("")
async def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new booking."""
    settings = get_settings()

    # Check equipment exists and is active
    equipment = db.query(Equipment).filter(
        Equipment.id == data.equipment_id,
        Equipment.is_active == True,
    ).first()

    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found or inactive",
        )

    # Check user has access to equipment
    if not check_equipment_access(current_user, data.equipment_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to book this equipment",
        )

    # Validate booking duration
    duration = (data.end_date - data.start_date).days + 1
    if duration > settings.booking.max_duration_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking duration cannot exceed {settings.booking.max_duration_days} days",
        )

    # Check start date is not in the past
    today = date.today()
    if data.start_date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create bookings in the past",
        )

    # Check for conflicts
    conflicts = check_booking_conflicts(
        db,
        data.equipment_id,
        data.start_date,
        data.end_date,
        data.start_time,
        data.end_time,
    )

    if conflicts:
        conflict_info = [
            {
                "id": c.id,
                "start_date": c.start_date.isoformat(),
                "end_date": c.end_date.isoformat(),
                "start_time": c.start_time.isoformat(),
                "end_time": c.end_time.isoformat(),
                "user_name": c.user.name if c.user else "Unknown",
            }
            for c in conflicts
        ]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Booking conflicts with existing reservations",
                "conflicts": conflict_info,
            },
        )

    # Check daily booking limit
    today_bookings = (
        db.query(Booking)
        .filter(
            Booking.user_id == current_user.id,
            Booking.created_at >= datetime.combine(today, time.min),
            Booking.created_at < datetime.combine(today + timedelta(days=1), time.min),
        )
        .count()
    )

    if today_bookings >= settings.rate_limit.max_bookings_per_user_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily booking limit ({settings.rate_limit.max_bookings_per_user_per_day}) reached",
        )

    # Create booking
    booking = Booking(
        user_id=current_user.id,
        equipment_id=data.equipment_id,
        start_date=data.start_date,
        end_date=data.end_date,
        start_time=data.start_time,
        end_time=data.end_time,
        description=sanitize_input(data.description, settings.booking.max_description_length)
        if data.description
        else None,
        status="active",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # Queue notifications (if email enabled)
    from app.services.notifications import (
        queue_booking_notification,
        queue_manager_new_booking_notification,
    )

    try:
        queue_booking_notification(db, booking, "created")
        queue_manager_new_booking_notification(db, booking)
    except Exception as e:
        print(f"Failed to queue notification: {e}")

    return {
        "success": True,
        "booking": booking.to_dict(),
        "message": f"Booking created for {equipment.name}",
    }


@router.put("/{booking_id}")
async def update_booking(
    booking_id: int,
    data: BookingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a booking."""
    settings = get_settings()

    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    # Check permissions
    can_edit = (
        booking.user_id == current_user.id
        or current_user.is_admin
        or check_equipment_manager(current_user, booking.equipment_id, db)
    )

    if not can_edit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit this booking",
        )

    # Can't edit cancelled bookings
    if booking.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit cancelled booking",
        )

    # Prepare updated values
    new_start_date = data.start_date if data.start_date else booking.start_date
    new_end_date = data.end_date if data.end_date else booking.end_date
    new_start_time = data.start_time if data.start_time else booking.start_time
    new_end_time = data.end_time if data.end_time else booking.end_time

    # Validate dates
    if new_end_date < new_start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be on or after start date",
        )

    # Validate duration
    duration = (new_end_date - new_start_date).days + 1
    if duration > settings.booking.max_duration_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking duration cannot exceed {settings.booking.max_duration_days} days",
        )

    # Check for conflicts (excluding this booking)
    if data.start_date or data.end_date or data.start_time or data.end_time:
        conflicts = check_booking_conflicts(
            db,
            booking.equipment_id,
            new_start_date,
            new_end_date,
            new_start_time,
            new_end_time,
            exclude_booking_id=booking_id,
        )

        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Updated booking would conflict with existing reservations",
            )

    # Apply updates
    if data.start_date:
        booking.start_date = data.start_date
    if data.end_date:
        booking.end_date = data.end_date
    if data.start_time:
        booking.start_time = data.start_time
    if data.end_time:
        booking.end_time = data.end_time
    if data.description is not None:
        booking.description = sanitize_input(
            data.description, settings.booking.max_description_length
        ) if data.description else None

    db.commit()
    db.refresh(booking)

    return {
        "success": True,
        "booking": booking.to_dict(),
        "message": "Booking updated",
    }


@router.patch("/{booking_id}/description")
async def update_booking_description(
    booking_id: int,
    data: BookingDescriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update only booking description."""
    settings = get_settings()

    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    # Check permissions
    can_edit = (
        booking.user_id == current_user.id
        or current_user.is_admin
        or check_equipment_manager(current_user, booking.equipment_id, db)
    )

    if not can_edit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit this booking",
        )

    booking.description = sanitize_input(
        data.description, settings.booking.max_description_length
    )
    db.commit()
    db.refresh(booking)

    return {
        "success": True,
        "booking": booking.to_dict(),
        "message": "Description updated",
    }


@router.delete("/{booking_id}")
async def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a booking."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    # Check permissions
    can_cancel = (
        booking.user_id == current_user.id
        or current_user.is_admin
        or check_equipment_manager(current_user, booking.equipment_id, db)
    )

    if not can_cancel:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot cancel this booking",
        )

    # Can't cancel already cancelled bookings
    if booking.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is already cancelled",
        )

    booking.status = "cancelled"
    db.commit()

    # Queue cancellation notifications
    from app.services.notifications import (
        queue_booking_notification,
        queue_short_notice_cancellation_alert,
    )

    try:
        queue_booking_notification(db, booking, "cancelled")
        queue_short_notice_cancellation_alert(db, booking)
    except Exception as e:
        print(f"Failed to queue cancellation notification: {e}")

    return {
        "success": True,
        "message": "Booking cancelled",
    }
