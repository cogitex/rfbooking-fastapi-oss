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

"""Authentication and system models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class AuthToken(Base):
    """Authentication token model for session management."""

    __tablename__ = "auth_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    user_agent = Column(Text, nullable=True)
    is_revoked = Column(Boolean, nullable=False, default=False)

    # Relationships
    user = relationship("User", back_populates="auth_tokens")

    def is_valid(self) -> bool:
        """Check if token is still valid."""
        if self.is_revoked:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True

    def __repr__(self):
        return f"<AuthToken(id={self.id}, user_id={self.user_id}, valid={self.is_valid()})>"


class MagicLink(Base):
    """Magic link model for passwordless authentication."""

    __tablename__ = "magic_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=True)  # Name provided during registration
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="magic_links")

    def is_valid(self) -> bool:
        """Check if magic link is still valid."""
        if self.used:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True

    def __repr__(self):
        return f"<MagicLink(id={self.id}, email='{self.email}', valid={self.is_valid()})>"


class CronJob(Base):
    """Cron job configuration and status tracking."""

    __tablename__ = "cron_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_key = Column(String(100), unique=True, nullable=False)
    job_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    cron_schedule = Column(String(50), nullable=False)  # e.g., "0 9 * * *"
    is_enabled = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(50), nullable=True)  # success, error, skipped
    last_run_duration_ms = Column(Integer, nullable=True)
    total_runs = Column(Integer, nullable=False, default=0)
    total_errors = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "job_key": self.job_key,
            "job_name": self.job_name,
            "description": self.description,
            "cron_schedule": self.cron_schedule,
            "is_enabled": self.is_enabled,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_status": self.last_run_status,
            "last_run_duration_ms": self.last_run_duration_ms,
            "total_runs": self.total_runs,
            "total_errors": self.total_errors,
        }

    def __repr__(self):
        return f"<CronJob(id={self.id}, key='{self.job_key}', enabled={self.is_enabled})>"


class NotificationLog(Base):
    """Email notification tracking."""

    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_type = Column(String(100), nullable=False, index=True)
    recipient_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reference_id = Column(Integer, nullable=True)  # booking_id or equipment_id
    reference_type = Column(String(50), nullable=True)  # 'booking' or 'equipment'
    scheduled_for = Column(DateTime, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, sent, failed, skipped
    error_message = Column(Text, nullable=True)
    send_attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    recipient = relationship("User")

    def __repr__(self):
        return f"<NotificationLog(id={self.id}, type='{self.notification_type}', status='{self.status}')>"
