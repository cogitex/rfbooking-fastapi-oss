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

"""Admin routes for user and system management."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import require_admin, require_manager, get_current_user
from app.models.auth import AuthToken, MagicLink, CronJob, RegistrationSettings, AllowedEmail, SystemSettings, AuditLog
from app.models.user import User
from app.models.equipment import AISpecificationRule
import json

router = APIRouter(prefix="/api/admin")


class UserRoleUpdate(BaseModel):
    """User role update request."""

    role_id: int


class UserStatusUpdate(BaseModel):
    """User status update request."""

    is_active: bool


class CronJobUpdate(BaseModel):
    """Cron job update request."""

    is_enabled: Optional[bool] = None


class AIRuleCreate(BaseModel):
    """AI specification rule creation request."""

    rule_type: str
    parameter_name: Optional[str] = None
    parameter_unit: Optional[str] = None
    prompt_text: str
    user_prompt_patterns: Optional[str] = None
    equipment_patterns: Optional[str] = None
    display_order: int = 0


class AIRuleUpdate(BaseModel):
    """AI specification rule update request."""

    rule_type: Optional[str] = None
    parameter_name: Optional[str] = None
    parameter_unit: Optional[str] = None
    is_enabled: Optional[bool] = None
    prompt_text: Optional[str] = None
    user_prompt_patterns: Optional[str] = None
    equipment_patterns: Optional[str] = None
    display_order: Optional[int] = None


class RegistrationSettingsUpdate(BaseModel):
    """Registration settings update request."""

    allow_domain_registration: Optional[bool] = None
    allow_email_registration: Optional[bool] = None
    allowed_domains: Optional[list[str]] = None


class AllowedEmailCreate(BaseModel):
    """Allowed email creation request."""

    email: str
    name: Optional[str] = None


class AllowedEmailsImport(BaseModel):
    """Bulk import of allowed emails."""

    emails: list[dict]  # List of {email: str, name: str}


class TokenDeleteRequest(BaseModel):
    """Token deletion request with configurable days."""

    days: int = 7


class ServiceModeUpdate(BaseModel):
    """Service mode update request."""

    enabled: bool
    message: Optional[str] = None  # Custom maintenance message


# User Management Routes
@router.get("/users")
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """List all users."""
    users = db.query(User).order_by(User.name).all()
    return {
        "success": True,
        "users": [u.to_dict() for u in users],
    }


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update user role (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if data.role_id not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role ID. Must be 1 (admin), 2 (manager), or 3 (user)",
        )

    user.role_id = data.role_id
    db.commit()
    db.refresh(user)

    role_names = {1: "admin", 2: "manager", 3: "user"}
    return {
        "success": True,
        "user": user.to_dict(),
        "message": f"User role updated to {role_names[data.role_id]}",
    }


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Activate or deactivate user (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own status",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_active = data.is_active
    db.commit()

    # Revoke all tokens if deactivating
    if not data.is_active:
        db.query(AuthToken).filter(AuthToken.user_id == user_id).update(
            {"is_revoked": True}
        )
        db.commit()

    return {
        "success": True,
        "user": user.to_dict(),
        "message": f"User {'activated' if data.is_active else 'deactivated'}",
    }


# Token Management Routes
@router.post("/tokens/delete-old")
async def delete_old_tokens(
    data: Optional[TokenDeleteRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete expired and revoked tokens older than specified days.

    Args:
        data: Optional request body with 'days' parameter (0-180, default 7)
    """
    # Get days from request body or use default
    days = data.days if data else 7

    # Validate days range (0-180)
    if days < 0 or days > 180:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days must be between 0 and 180",
        )

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Count affected users before deletion
    affected_users = (
        db.query(AuthToken.user_id)
        .filter(AuthToken.created_at < cutoff)
        .distinct()
        .count()
    )

    # Delete old tokens (by creation date, not expiry)
    tokens_deleted = (
        db.query(AuthToken)
        .filter(AuthToken.created_at < cutoff)
        .delete(synchronize_session=False)
    )

    # Delete old magic links
    magic_deleted = (
        db.query(MagicLink)
        .filter(MagicLink.created_at < cutoff)
        .delete(synchronize_session=False)
    )

    db.commit()

    return {
        "success": True,
        "deleted_count": tokens_deleted,
        "affected_users": affected_users,
        "magic_links_deleted": magic_deleted,
        "days": days,
        "message": f"Deleted {tokens_deleted} tokens older than {days} days",
    }


# Cron Job Management Routes
@router.get("/cron-jobs")
async def list_cron_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all cron jobs."""
    jobs = db.query(CronJob).order_by(CronJob.job_key).all()
    return {
        "success": True,
        "jobs": [j.to_dict() for j in jobs],
    }


@router.put("/cron-jobs/{job_id}")
async def update_cron_job(
    job_id: int,
    data: CronJobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update cron job settings."""
    job = db.query(CronJob).filter(CronJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cron job not found",
        )

    if data.is_enabled is not None:
        job.is_enabled = data.is_enabled

    db.commit()
    db.refresh(job)

    return {
        "success": True,
        "job": job.to_dict(),
        "message": f"Cron job '{job.job_name}' {'enabled' if job.is_enabled else 'disabled'}",
    }


@router.post("/cron-jobs/{job_id}/trigger")
async def trigger_cron_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Manually trigger a cron job."""
    job = db.query(CronJob).filter(CronJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cron job not found",
        )

    if not job.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot trigger disabled cron job",
        )

    # Run the job
    from app.services.scheduler import run_cron_job

    try:
        result = await run_cron_job(job.job_key, db)
        return {
            "success": True,
            "message": f"Cron job '{job.job_name}' triggered successfully",
            "result": result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run cron job: {str(e)}",
        )


# AI Specification Rules Routes
@router.get("/ai-specification-rules")
async def list_ai_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all AI specification rules."""
    rules = (
        db.query(AISpecificationRule)
        .order_by(AISpecificationRule.display_order, AISpecificationRule.id)
        .all()
    )
    return {
        "success": True,
        "rules": [r.to_dict() for r in rules],
    }


@router.post("/ai-specification-rules")
async def create_ai_rule(
    data: AIRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new AI specification rule."""
    if data.rule_type not in ("general", "parameter", "example"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid rule type. Must be 'general', 'parameter', or 'example'",
        )

    # Check for duplicate
    existing = (
        db.query(AISpecificationRule)
        .filter(
            AISpecificationRule.rule_type == data.rule_type,
            AISpecificationRule.parameter_name == data.parameter_name,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rule with this type and parameter already exists",
        )

    rule = AISpecificationRule(
        rule_type=data.rule_type,
        parameter_name=data.parameter_name,
        parameter_unit=data.parameter_unit,
        prompt_text=data.prompt_text,
        user_prompt_patterns=data.user_prompt_patterns,
        equipment_patterns=data.equipment_patterns,
        display_order=data.display_order,
        is_enabled=True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return {
        "success": True,
        "rule": rule.to_dict(),
        "message": "AI specification rule created",
    }


@router.patch("/ai-specification-rules/{rule_id}")
async def update_ai_rule(
    rule_id: int,
    data: AIRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update an AI specification rule."""
    rule = db.query(AISpecificationRule).filter(AISpecificationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI specification rule not found",
        )

    if data.rule_type is not None:
        if data.rule_type not in ("general", "parameter", "example"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid rule type",
            )
        rule.rule_type = data.rule_type

    if data.parameter_name is not None:
        rule.parameter_name = data.parameter_name or None

    if data.parameter_unit is not None:
        rule.parameter_unit = data.parameter_unit or None

    if data.is_enabled is not None:
        rule.is_enabled = data.is_enabled

    if data.prompt_text is not None:
        rule.prompt_text = data.prompt_text

    if data.user_prompt_patterns is not None:
        rule.user_prompt_patterns = data.user_prompt_patterns or None

    if data.equipment_patterns is not None:
        rule.equipment_patterns = data.equipment_patterns or None

    if data.display_order is not None:
        rule.display_order = data.display_order

    db.commit()
    db.refresh(rule)

    return {
        "success": True,
        "rule": rule.to_dict(),
        "message": "AI specification rule updated",
    }


@router.delete("/ai-specification-rules/{rule_id}")
async def delete_ai_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete an AI specification rule."""
    rule = db.query(AISpecificationRule).filter(AISpecificationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI specification rule not found",
        )

    db.delete(rule)
    db.commit()

    return {
        "success": True,
        "message": "AI specification rule deleted",
    }


# Registration Settings Routes
def get_or_create_registration_settings(db: Session):
    """Get or create registration settings, handling schema migration."""
    from sqlalchemy import inspect, text

    # Check if table exists and has the right columns
    inspector = inspect(db.bind)
    if "registration_settings" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("registration_settings")]

        # Handle migration from old schema
        if "registration_mode" in columns and "allow_domain_registration" not in columns:
            # Old schema - migrate
            try:
                db.execute(text("ALTER TABLE registration_settings ADD COLUMN allow_domain_registration INTEGER DEFAULT 1"))
                db.execute(text("ALTER TABLE registration_settings ADD COLUMN allow_email_registration INTEGER DEFAULT 0"))
                db.commit()
            except Exception:
                db.rollback()

    settings = db.query(RegistrationSettings).first()

    # Create default settings if none exist
    if not settings:
        settings = RegistrationSettings(
            allow_domain_registration=True,
            allow_email_registration=False,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


@router.get("/registration-settings")
async def get_registration_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get current registration settings."""
    try:
        settings = get_or_create_registration_settings(db)

        # Count allowed emails and pending (not yet registered)
        allowed_emails = db.query(AllowedEmail).all()
        registered_emails = {u.email.lower() for u in db.query(User).filter(User.is_active == True).all()}
        pending_count = sum(1 for e in allowed_emails if e.email.lower() not in registered_emails)

        return {
            "success": True,
            **settings.to_dict(),
            "allowed_emails_count": len(allowed_emails),
            "pending_count": pending_count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load registration settings: {str(e)}",
        )


@router.put("/registration-settings")
async def update_registration_settings(
    data: RegistrationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update registration settings."""
    try:
        settings = get_or_create_registration_settings(db)

        # Get new values or keep existing
        new_domain = data.allow_domain_registration if data.allow_domain_registration is not None else settings.allow_domain_registration
        new_email = data.allow_email_registration if data.allow_email_registration is not None else settings.allow_email_registration

        # Validate: at least one must be enabled
        if not new_domain and not new_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one registration method must be enabled",
            )

        if data.allow_domain_registration is not None:
            settings.allow_domain_registration = data.allow_domain_registration

        if data.allow_email_registration is not None:
            settings.allow_email_registration = data.allow_email_registration

        if data.allowed_domains is not None:
            # Clean and validate domains
            cleaned_domains = [d.strip().lower() for d in data.allowed_domains if d.strip()]
            settings.allowed_domains = ",".join(cleaned_domains) if cleaned_domains else None

        settings.updated_by = current_user.id
        db.commit()
        db.refresh(settings)

        return {
            "success": True,
            **settings.to_dict(),
            "message": "Registration settings updated",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update registration settings: {str(e)}",
        )


@router.get("/registration/allowed-emails")
async def list_allowed_emails(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all allowed email addresses with registration status."""
    allowed_emails = db.query(AllowedEmail).order_by(AllowedEmail.added_at.desc()).all()

    # Get all registered users to check status
    users_by_email = {
        u.email.lower(): u
        for u in db.query(User).all()
    }

    emails_data = []
    for ae in allowed_emails:
        registered_user = users_by_email.get(ae.email.lower())
        emails_data.append({
            "id": ae.id,
            "email": ae.email,
            "name": ae.name,
            "status": "registered" if (registered_user and registered_user.is_active) else "pending",
            "is_active": registered_user.is_active if registered_user else False,
            "invited_at": ae.added_at.isoformat() if ae.added_at else None,
        })

    return {
        "success": True,
        "emails": emails_data,
        "total": len(emails_data),
    }


@router.post("/registration/allowed-emails")
async def add_allowed_email(
    data: AllowedEmailCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Add an email address to the allowlist."""
    email = data.email.strip().lower()
    name = data.name.strip() if data.name else None

    # Validate email format
    if "@" not in email or "." not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    # Check if already exists in allowlist
    existing = db.query(AllowedEmail).filter(AllowedEmail.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already in allowlist",
        )

    # Check if user already registered
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user and existing_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email is already registered",
        )

    allowed = AllowedEmail(email=email, name=name, added_by=current_user.id)
    db.add(allowed)
    db.commit()
    db.refresh(allowed)

    return {
        "success": True,
        "email": {
            "id": allowed.id,
            "email": allowed.email,
            "name": allowed.name,
            "status": "pending",
            "invited_at": allowed.added_at.isoformat() if allowed.added_at else None,
        },
        "message": f"Email '{email}' added to allowlist",
    }


@router.post("/registration/allowed-emails/import")
async def import_allowed_emails(
    data: AllowedEmailsImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Bulk import email addresses to the allowlist."""
    added = 0
    skipped = 0
    updated = 0
    errors = []

    # Get existing emails and users
    existing_allowed = {ae.email.lower(): ae for ae in db.query(AllowedEmail).all()}
    existing_users = {u.email.lower(): u for u in db.query(User).filter(User.is_active == True).all()}

    for item in data.emails:
        # Handle both dict format {email, name} and simple string
        if isinstance(item, dict):
            email = item.get("email", "").strip().lower()
            name = item.get("name", "").strip() or None
        else:
            email = str(item).strip().lower()
            name = None

        # Skip empty
        if not email:
            continue

        # Validate email format
        if "@" not in email or "." not in email:
            errors.append(f"Invalid format: {email}")
            continue

        # Skip if already registered
        if email in existing_users:
            skipped += 1
            continue

        # Check if already in allowlist
        if email in existing_allowed:
            # Update name if provided and different
            existing = existing_allowed[email]
            if name and existing.name != name:
                existing.name = name
                updated += 1
            else:
                skipped += 1
            continue

        allowed = AllowedEmail(email=email, name=name, added_by=current_user.id)
        db.add(allowed)
        added += 1

    db.commit()

    return {
        "success": True,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "message": f"Imported {added} emails, updated {updated}, skipped {skipped}",
    }


@router.delete("/registration/allowed-emails/{email_id}")
async def remove_allowed_email(
    email_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Remove an email address from the allowlist by ID."""
    allowed = db.query(AllowedEmail).filter(AllowedEmail.id == email_id).first()
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found in allowlist",
        )

    # Check if user is registered
    existing_user = db.query(User).filter(User.email == allowed.email).first()
    if existing_user and existing_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove: user is already registered. Deactivate the user instead.",
        )

    email = allowed.email
    db.delete(allowed)
    db.commit()

    return {
        "success": True,
        "message": f"Email '{email}' removed from allowlist",
    }


# Service Mode Routes
def get_service_mode(db: Session) -> dict:
    """Get current service mode status."""
    enabled_setting = db.query(SystemSettings).filter(
        SystemSettings.setting_key == "service_mode_enabled"
    ).first()
    message_setting = db.query(SystemSettings).filter(
        SystemSettings.setting_key == "service_mode_message"
    ).first()

    return {
        "enabled": enabled_setting.setting_value == "true" if enabled_setting else False,
        "message": message_setting.setting_value if message_setting else "System is under maintenance. Please try again later.",
    }


@router.get("/service-mode")
async def get_service_mode_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get current service mode status."""
    status_data = get_service_mode(db)
    return {
        "success": True,
        **status_data,
    }


@router.put("/service-mode")
async def update_service_mode(
    data: ServiceModeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Enable or disable service mode (maintenance mode)."""
    # Update enabled setting
    enabled_setting = db.query(SystemSettings).filter(
        SystemSettings.setting_key == "service_mode_enabled"
    ).first()

    if not enabled_setting:
        enabled_setting = SystemSettings(
            setting_key="service_mode_enabled",
            setting_value="false",
        )
        db.add(enabled_setting)

    enabled_setting.setting_value = "true" if data.enabled else "false"
    enabled_setting.updated_by = current_user.id

    # Update message setting if provided
    if data.message is not None:
        message_setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "service_mode_message"
        ).first()

        if not message_setting:
            message_setting = SystemSettings(
                setting_key="service_mode_message",
                setting_value=data.message,
            )
            db.add(message_setting)
        else:
            message_setting.setting_value = data.message
            message_setting.updated_by = current_user.id

    db.commit()

    return {
        "success": True,
        "enabled": data.enabled,
        "message": f"Service mode {'enabled' if data.enabled else 'disabled'}",
    }


# ============================================================================
# Audit Log Functions and Endpoints
# ============================================================================

def log_audit_event(
    db: Session,
    user: Optional[User],
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    resource_name: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Log an audit event.

    Args:
        db: Database session
        user: User performing the action (or None for system actions)
        action: Action type (create, update, delete, login, etc.)
        resource_type: Type of resource (user, equipment, booking, etc.)
        resource_id: ID of the resource
        resource_name: Human-readable name of the resource
        details: Additional details as dict (will be JSON serialized)
        ip_address: Client IP address
        user_agent: Client user agent
    """
    audit_entry = AuditLog(
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        details=json.dumps(details) if details else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit_entry)
    db.commit()


@router.get("/audit-log")
async def get_audit_log(
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get audit log entries (admin only).

    Supports filtering by action, resource_type, user_id, and date range.
    """
    query = db.query(AuditLog)

    if action:
        query = query.filter(AuditLog.action == action)

    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.filter(AuditLog.timestamp >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.filter(AuditLog.timestamp <= end)
        except ValueError:
            pass

    total = query.count()

    entries = (
        query.order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(min(limit, 500))
        .all()
    )

    return {
        "success": True,
        "total": total,
        "entries": [e.to_dict() for e in entries],
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit-log/summary")
async def get_audit_summary(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get audit log summary statistics (admin only)."""
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Count by action
    action_counts = (
        db.query(AuditLog.action, func.count(AuditLog.id))
        .filter(AuditLog.timestamp >= cutoff)
        .group_by(AuditLog.action)
        .all()
    )

    # Count by resource type
    resource_counts = (
        db.query(AuditLog.resource_type, func.count(AuditLog.id))
        .filter(AuditLog.timestamp >= cutoff)
        .group_by(AuditLog.resource_type)
        .all()
    )

    # Recent activity by user
    user_counts = (
        db.query(AuditLog.user_email, func.count(AuditLog.id))
        .filter(AuditLog.timestamp >= cutoff, AuditLog.user_email.isnot(None))
        .group_by(AuditLog.user_email)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
        .all()
    )

    return {
        "success": True,
        "period_days": days,
        "by_action": {action: count for action, count in action_counts},
        "by_resource": {resource: count for resource, count in resource_counts},
        "top_users": [{"email": email, "count": count} for email, count in user_counts],
    }


@router.delete("/audit-log/cleanup")
async def cleanup_audit_log(
    days: int = 90,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete audit log entries older than specified days (admin only)."""
    settings = get_settings()

    # Minimum 30 days retention
    days = max(30, days)
    cutoff = datetime.utcnow() - timedelta(days=days)

    deleted = db.query(AuditLog).filter(AuditLog.timestamp < cutoff).delete()
    db.commit()

    # Log the cleanup action itself
    log_audit_event(
        db=db,
        user=current_user,
        action="cleanup",
        resource_type="audit_log",
        details={"deleted_count": deleted, "older_than_days": days},
    )

    return {
        "success": True,
        "deleted": deleted,
        "message": f"Deleted {deleted} audit log entries older than {days} days",
    }
