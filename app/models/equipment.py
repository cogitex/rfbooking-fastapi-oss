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

"""Equipment and AI-related models."""

from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class EquipmentType(Base):
    """Equipment type/category model."""

    __tablename__ = "equipment_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    manager_notifications_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    equipment = relationship("Equipment", back_populates="equipment_type")
    user_access = relationship(
        "EquipmentTypeUser", back_populates="equipment_type", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "manager_notifications_enabled": self.manager_notifications_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<EquipmentType(id={self.id}, name='{self.name}')>"


class Equipment(Base):
    """Equipment model."""

    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    type_id = Column(Integer, ForeignKey("equipment_types.id"), nullable=True)
    next_calibration_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    equipment_type = relationship("EquipmentType", back_populates="equipment")
    bookings = relationship("Booking", back_populates="equipment", cascade="all, delete-orphan")
    managers = relationship(
        "EquipmentManager", back_populates="equipment", cascade="all, delete-orphan"
    )

    def to_dict(self, include_type: bool = True) -> dict:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "location": self.location,
            "type_id": self.type_id,
            "next_calibration_date": (
                self.next_calibration_date.isoformat() if self.next_calibration_date else None
            ),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_type and self.equipment_type:
            result["type_name"] = self.equipment_type.name
        return result

    def __repr__(self):
        return f"<Equipment(id={self.id}, name='{self.name}')>"


class EquipmentTypeUser(Base):
    """Junction table for user access to equipment types."""

    __tablename__ = "equipment_type_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type_id = Column(
        Integer, ForeignKey("equipment_types.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    granted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    granted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (UniqueConstraint("type_id", "user_id", name="uq_type_user"),)

    # Relationships
    equipment_type = relationship("EquipmentType", back_populates="user_access")
    user = relationship("User", foreign_keys=[user_id], back_populates="equipment_type_access")
    granter = relationship("User", foreign_keys=[granted_by])

    def __repr__(self):
        return f"<EquipmentTypeUser(type_id={self.type_id}, user_id={self.user_id})>"


class EquipmentManager(Base):
    """Junction table for equipment managers."""

    __tablename__ = "equipment_managers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(
        Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    manager_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (UniqueConstraint("equipment_id", "manager_id", name="uq_equipment_manager"),)

    # Relationships
    equipment = relationship("Equipment", back_populates="managers")
    manager = relationship("User", foreign_keys=[manager_id], back_populates="managed_equipment")
    assigner = relationship("User", foreign_keys=[assigned_by])

    def __repr__(self):
        return f"<EquipmentManager(equipment_id={self.equipment_id}, manager_id={self.manager_id})>"


class AISpecificationRule(Base):
    """AI specification rules for equipment matching."""

    __tablename__ = "ai_specification_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_type = Column(String(50), nullable=False)  # 'general', 'parameter', 'example'
    parameter_name = Column(String(100), nullable=True)  # 'frequency', 'power', 'temperature', etc.
    parameter_unit = Column(String(20), nullable=True)  # 'GHz', 'W', '°C', 'V', 'A'
    is_enabled = Column(Boolean, nullable=False, default=True)
    prompt_text = Column(Text, nullable=False)
    user_prompt_patterns = Column(Text, nullable=True)  # JSON array of regex patterns
    equipment_patterns = Column(Text, nullable=True)  # JSON array of regex patterns
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("rule_type", "parameter_name", name="uq_rule_type_param"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "rule_type": self.rule_type,
            "parameter_name": self.parameter_name,
            "parameter_unit": self.parameter_unit,
            "is_enabled": self.is_enabled,
            "prompt_text": self.prompt_text,
            "user_prompt_patterns": self.user_prompt_patterns,
            "equipment_patterns": self.equipment_patterns,
            "display_order": self.display_order,
        }

    def __repr__(self):
        return f"<AISpecificationRule(id={self.id}, type='{self.rule_type}', param='{self.parameter_name}')>"


class AIUsage(Base):
    """Daily AI usage aggregation."""

    __tablename__ = "ai_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    queries_count = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AIUsage(date={self.date}, queries={self.queries_count})>"


class AIQueryLog(Base):
    """Detailed AI query logging."""

    __tablename__ = "ai_query_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    model = Column(String(100), nullable=False)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<AIQueryLog(id={self.id}, user_id={self.user_id}, success={self.success})>"
