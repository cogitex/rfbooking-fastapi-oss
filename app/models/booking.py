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

"""Booking model."""

from datetime import datetime, date, time
from typing import Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Booking(Base):
    """Equipment booking model."""

    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        String(50),
        nullable=False,
        default="active",
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("status IN ('active', 'cancelled', 'completed')", name="ck_booking_status"),
    )

    # Relationships
    user = relationship("User", back_populates="bookings")
    equipment = relationship("Equipment", back_populates="bookings")

    def to_dict(self, include_user: bool = True, include_equipment: bool = True) -> dict:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "equipment_id": self.equipment_id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_user and self.user:
            result["user_name"] = self.user.name
            result["user_email"] = self.user.email

        if include_equipment and self.equipment:
            result["equipment_name"] = self.equipment.name
            result["equipment_location"] = self.equipment.location

        return result

    def overlaps_with(self, other_start_date: date, other_end_date: date,
                      other_start_time: time, other_end_time: time) -> bool:
        """Check if this booking overlaps with another time range."""
        # First check date overlap
        if self.end_date < other_start_date or self.start_date > other_end_date:
            return False

        # If dates overlap, check time overlap for same-day scenarios
        if self.start_date == self.end_date and other_start_date == other_end_date:
            # Single-day bookings on the same day
            if self.start_date == other_start_date:
                # Check time overlap
                if self.end_time <= other_start_time or self.start_time >= other_end_time:
                    return False

        return True

    def __repr__(self):
        return (
            f"<Booking(id={self.id}, user_id={self.user_id}, "
            f"equipment_id={self.equipment_id}, status='{self.status}')>"
        )
