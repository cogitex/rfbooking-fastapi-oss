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

"""User and Role models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Role(Base):
    """Role model for user permissions."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    users = relationship("User", back_populates="role")

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}')>"


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, default=3)
    is_active = Column(Boolean, nullable=False, default=True)
    email_notifications_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    role = relationship("Role", back_populates="users")
    auth_tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")
    magic_links = relationship("MagicLink", back_populates="user", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="user", cascade="all, delete-orphan")
    equipment_type_access = relationship(
        "EquipmentTypeUser", back_populates="user", cascade="all, delete-orphan"
    )
    managed_equipment = relationship(
        "EquipmentManager", back_populates="manager", cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.role_id == 1

    @property
    def is_manager(self) -> bool:
        """Check if user is manager or admin."""
        return self.role_id in (1, 2)

    @property
    def role_name(self) -> str:
        """Get role name."""
        role_names = {1: "admin", 2: "manager", 3: "user"}
        return role_names.get(self.role_id, "user")

    def to_dict(self) -> dict:
        """Convert user to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role_id": self.role_id,
            "role_name": self.role_name,
            "is_active": self.is_active,
            "email_notifications_enabled": self.email_notifications_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role_id={self.role_id})>"
