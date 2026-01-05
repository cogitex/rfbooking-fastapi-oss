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

"""Reporting and analytics routes."""

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.booking import Booking
from app.models.equipment import Equipment, EquipmentType
from app.models.user import User

router = APIRouter(prefix="/api/reports")


@router.get("/equipment-usage")
async def get_equipment_usage(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    equipment_id: Optional[int] = None,
    type_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get equipment usage statistics."""
    # Default to last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    query = db.query(
        Equipment.id,
        Equipment.name,
        Equipment.location,
        EquipmentType.name.label("type_name"),
        func.count(Booking.id).label("total_bookings"),
        func.count(func.distinct(Booking.user_id)).label("unique_users"),
    ).outerjoin(
        Booking,
        (Booking.equipment_id == Equipment.id)
        & (Booking.status == "active")
        & (Booking.start_date >= start_date)
        & (Booking.end_date <= end_date),
    ).outerjoin(
        EquipmentType, Equipment.type_id == EquipmentType.id
    ).filter(
        Equipment.is_active == True
    )

    if equipment_id:
        query = query.filter(Equipment.id == equipment_id)

    if type_id:
        query = query.filter(Equipment.type_id == type_id)

    query = query.group_by(Equipment.id).order_by(Equipment.name)

    results = query.all()

    equipment_stats = []
    for row in results:
        equipment_stats.append({
            "equipment_id": row.id,
            "name": row.name,
            "location": row.location,
            "type_name": row.type_name,
            "total_bookings": row.total_bookings,
            "unique_users": row.unique_users,
        })

    return {
        "success": True,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "equipment": equipment_stats,
    }


@router.get("/user-activity")
async def get_user_activity(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user booking activity statistics."""
    # Default to last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Non-managers can only see their own activity
    if not current_user.is_manager and user_id and user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Cannot view other users' activity",
        )

    if not current_user.is_manager:
        user_id = current_user.id

    query = db.query(
        User.id,
        User.name,
        User.email,
        func.count(Booking.id).label("total_bookings"),
        func.count(func.distinct(Booking.equipment_id)).label("unique_equipment"),
    ).outerjoin(
        Booking,
        (Booking.user_id == User.id)
        & (Booking.status.in_(["active", "completed"]))
        & (Booking.start_date >= start_date)
        & (Booking.end_date <= end_date),
    ).filter(
        User.is_active == True
    )

    if user_id:
        query = query.filter(User.id == user_id)

    query = query.group_by(User.id).order_by(User.name)

    results = query.all()

    user_stats = []
    for row in results:
        user_stats.append({
            "user_id": row.id,
            "name": row.name,
            "email": row.email,
            "total_bookings": row.total_bookings,
            "unique_equipment": row.unique_equipment,
        })

    return {
        "success": True,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "users": user_stats,
    }


@router.get("/booking-stats")
async def get_booking_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get overall booking statistics."""
    # Default to last 30 days
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Total bookings by status
    status_counts = (
        db.query(
            Booking.status,
            func.count(Booking.id).label("count"),
        )
        .filter(
            Booking.start_date >= start_date,
            Booking.end_date <= end_date,
        )
        .group_by(Booking.status)
        .all()
    )

    status_dict = {row.status: row.count for row in status_counts}

    # Bookings by day (for the period)
    daily_bookings = (
        db.query(
            Booking.start_date,
            func.count(Booking.id).label("count"),
        )
        .filter(
            Booking.start_date >= start_date,
            Booking.start_date <= end_date,
            Booking.status == "active",
        )
        .group_by(Booking.start_date)
        .order_by(Booking.start_date)
        .all()
    )

    daily_data = [
        {"date": row.start_date.isoformat(), "count": row.count}
        for row in daily_bookings
    ]

    # Most booked equipment
    top_equipment = (
        db.query(
            Equipment.id,
            Equipment.name,
            func.count(Booking.id).label("booking_count"),
        )
        .join(Booking, Booking.equipment_id == Equipment.id)
        .filter(
            Booking.start_date >= start_date,
            Booking.end_date <= end_date,
            Booking.status == "active",
        )
        .group_by(Equipment.id)
        .order_by(func.count(Booking.id).desc())
        .limit(10)
        .all()
    )

    top_equipment_data = [
        {"equipment_id": row.id, "name": row.name, "booking_count": row.booking_count}
        for row in top_equipment
    ]

    # Most active users
    top_users = (
        db.query(
            User.id,
            User.name,
            func.count(Booking.id).label("booking_count"),
        )
        .join(Booking, Booking.user_id == User.id)
        .filter(
            Booking.start_date >= start_date,
            Booking.end_date <= end_date,
            Booking.status == "active",
        )
        .group_by(User.id)
        .order_by(func.count(Booking.id).desc())
        .limit(10)
        .all()
    )

    top_users_data = [
        {"user_id": row.id, "name": row.name, "booking_count": row.booking_count}
        for row in top_users
    ]

    return {
        "success": True,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "summary": {
            "active": status_dict.get("active", 0),
            "completed": status_dict.get("completed", 0),
            "cancelled": status_dict.get("cancelled", 0),
            "total": sum(status_dict.values()),
        },
        "daily_bookings": daily_data,
        "top_equipment": top_equipment_data,
        "top_users": top_users_data,
    }
