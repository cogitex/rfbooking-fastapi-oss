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
    # For token reuse within 2 minutes (Chrome mobile prefetch fix)
    last_auth_token_id = Column(Integer, ForeignKey("auth_tokens.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="magic_links")
    last_auth_token = relationship("AuthToken", foreign_keys=[last_auth_token_id])

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


class SystemSettings(Base):
    """System-wide settings including service mode."""

    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self):
        return f"<SystemSettings(key='{self.setting_key}', value='{self.setting_value}')>"


class RegistrationSettings(Base):
    """Registration settings for controlling user sign-ups."""

    __tablename__ = "registration_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Domain-based registration: allow users from specified domains
    allow_domain_registration = Column(Boolean, nullable=False, default=True)
    # Email-based registration: allow only specific pre-approved emails
    allow_email_registration = Column(Boolean, nullable=False, default=False)
    # Comma-separated list of allowed email domains (e.g., "company.com,partner.org")
    allowed_domains = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        domains = self.allowed_domains.split(",") if self.allowed_domains else []
        return {
            "id": self.id,
            "allow_domain_registration": self.allow_domain_registration,
            "allow_email_registration": self.allow_email_registration,
            "allowed_domains": domains,
            "domain": self.allowed_domains or "",  # For compatibility with rfbooking-core
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<RegistrationSettings(domain={self.allow_domain_registration}, email={self.allow_email_registration})>"


class AllowedEmail(Base):
    """Allowed email addresses for restricted registration."""

    __tablename__ = "allowed_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)  # Optional name for the invited user
    added_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    added_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def to_dict(self, registered_user=None) -> dict:
        """Convert to dictionary.

        Args:
            registered_user: Optional User object if this email has registered
        """
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "status": "registered" if registered_user else "pending",
            "is_active": registered_user.is_active if registered_user else False,
        }

    def __repr__(self):
        return f"<AllowedEmail(email='{self.email}')>"


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


class AuditLog(Base):
    """Audit log for tracking admin actions."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_email = Column(String(255), nullable=True)  # Store email in case user is deleted
    action = Column(String(100), nullable=False, index=True)  # create, update, delete, login, etc.
    resource_type = Column(String(100), nullable=False, index=True)  # user, equipment, booking, etc.
    resource_id = Column(Integer, nullable=True)
    resource_name = Column(String(255), nullable=True)  # Human-readable identifier
    details = Column(Text, nullable=True)  # JSON string with change details
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Relationships
    user = relationship("User")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "details": self.details,
            "ip_address": self.ip_address,
        }

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', resource='{self.resource_type}')>"
