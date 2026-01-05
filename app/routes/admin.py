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
from app.models.auth import AuthToken, MagicLink, CronJob
from app.models.user import User
from app.models.equipment import AISpecificationRule

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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete expired and revoked tokens older than retention period."""
    settings = get_settings()
    cutoff = datetime.utcnow() - timedelta(days=settings.cleanup.auth_token_retention_days)

    # Delete old expired tokens
    expired_deleted = (
        db.query(AuthToken)
        .filter(AuthToken.expires_at < cutoff)
        .delete(synchronize_session=False)
    )

    # Delete old revoked tokens
    revoked_deleted = (
        db.query(AuthToken)
        .filter(
            AuthToken.is_revoked == True,
            AuthToken.created_at < cutoff,
        )
        .delete(synchronize_session=False)
    )

    # Delete old magic links
    magic_deleted = (
        db.query(MagicLink)
        .filter(MagicLink.expires_at < cutoff)
        .delete(synchronize_session=False)
    )

    db.commit()

    return {
        "success": True,
        "deleted": {
            "expired_tokens": expired_deleted,
            "revoked_tokens": revoked_deleted,
            "magic_links": magic_deleted,
        },
        "message": "Old authentication records cleaned up",
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
