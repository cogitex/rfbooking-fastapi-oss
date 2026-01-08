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

import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.booking import Booking
from app.models.equipment import Equipment, EquipmentType
from app.models.user import User

router = APIRouter(prefix="/api/reports")


def generate_csv(headers: list, rows: list, filename: str) -> StreamingResponse:
    """Generate a CSV file response."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/equipment-usage")
async def get_equipment_usage(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    equipment_id: Optional[int] = None,
    type_id: Optional[int] = None,
    format: Optional[str] = None,  # 'csv' for CSV export
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get equipment usage statistics. Add ?format=csv for CSV export."""
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

    # CSV export
    if format and format.lower() == "csv":
        headers = ["Equipment ID", "Name", "Location", "Type", "Total Bookings", "Unique Users"]
        rows = [
            [row.id, row.name, row.location or "", row.type_name or "", row.total_bookings, row.unique_users]
            for row in results
        ]
        filename = f"equipment_usage_{start_date}_{end_date}.csv"
        return generate_csv(headers, rows, filename)

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
    format: Optional[str] = None,  # 'csv' for CSV export
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user booking activity statistics. Add ?format=csv for CSV export."""
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

    # Query with status breakdown (aligned with rfbooking-core)
    query = db.query(
        User.id,
        User.name,
        User.email,
        func.sum(case((Booking.status == "active", 1), else_=0)).label("active_bookings"),
        func.sum(case((Booking.status == "cancelled", 1), else_=0)).label("cancelled_bookings"),
        func.sum(case((Booking.status == "completed", 1), else_=0)).label("completed_bookings"),
        func.count(func.distinct(Booking.equipment_id)).label("unique_equipment"),
    ).outerjoin(
        Booking,
        (Booking.user_id == User.id)
        & (Booking.start_date >= start_date)
        & (Booking.end_date <= end_date),
    ).filter(
        User.is_active == True
    )

    if user_id:
        query = query.filter(User.id == user_id)

    query = query.group_by(User.id).order_by(User.name)

    results = query.all()

    # Calculate hours per user by fetching their bookings
    user_hours = {}
    for row in results:
        bookings = db.query(Booking).filter(
            Booking.user_id == row.id,
            Booking.status.in_(["active", "completed"]),
            Booking.start_date >= start_date,
            Booking.end_date <= end_date,
        ).all()

        total_hours = 0
        for b in bookings:
            # Calculate hours based on dates and times
            days = (b.end_date - b.start_date).days + 1
            if b.start_time and b.end_time:
                # Use actual times
                start_dt = datetime.combine(b.start_date, b.start_time)
                end_dt = datetime.combine(b.end_date, b.end_time)
                total_hours += (end_dt - start_dt).total_seconds() / 3600
            else:
                # Assume 8 hours per day
                total_hours += days * 8

        user_hours[row.id] = round(total_hours, 1)

    # CSV export
    if format and format.lower() == "csv":
        headers = ["User ID", "Name", "Email", "Active", "Cancelled", "Completed", "Avg Hrs/Booking", "Total Hours"]
        rows = []
        for row in results:
            total_bookings = (row.active_bookings or 0) + (row.completed_bookings or 0)
            total_hours = user_hours.get(row.id, 0)
            avg_hours = round(total_hours / total_bookings, 1) if total_bookings > 0 else 0
            rows.append([
                row.id, row.name, row.email, row.active_bookings or 0,
                row.cancelled_bookings or 0, row.completed_bookings or 0,
                avg_hours, total_hours
            ])
        filename = f"user_activity_{start_date}_{end_date}.csv"
        return generate_csv(headers, rows, filename)

    user_stats = []
    for row in results:
        total_bookings = (row.active_bookings or 0) + (row.completed_bookings or 0)
        total_hours = user_hours.get(row.id, 0)
        avg_hours = round(total_hours / total_bookings, 1) if total_bookings > 0 else 0

        user_stats.append({
            "user_id": row.id,
            "name": row.name,
            "email": row.email,
            "active_bookings": row.active_bookings or 0,
            "cancelled_bookings": row.cancelled_bookings or 0,
            "completed_bookings": row.completed_bookings or 0,
            "avg_hours_per_booking": avg_hours,
            "total_hours": total_hours,
            "unique_equipment": row.unique_equipment or 0,
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
    format: Optional[str] = None,  # 'csv' for CSV export
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get overall booking statistics. Add ?format=csv for CSV export (daily bookings)."""
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

    # CSV export (daily bookings)
    if format and format.lower() == "csv":
        headers = ["Date", "Booking Count"]
        rows = [[row.start_date.isoformat(), row.count] for row in daily_bookings]
        filename = f"booking_stats_{start_date}_{end_date}.csv"
        return generate_csv(headers, rows, filename)

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
