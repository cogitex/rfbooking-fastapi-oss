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

"""Authentication middleware and dependencies."""

import secrets
from datetime import datetime
from functools import wraps
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.auth import AuthToken, SystemSettings
from app.models.user import User


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract auth token from request cookies or header."""
    # Try cookie first
    token = request.cookies.get("auth_token")
    if token:
        return token

    # Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    return None


def check_service_mode(db: Session) -> dict:
    """Check if service mode (maintenance mode) is enabled.

    Returns dict with 'enabled' and 'message' keys.
    """
    enabled_setting = db.query(SystemSettings).filter(
        SystemSettings.setting_key == "service_mode_enabled"
    ).first()

    if not enabled_setting or enabled_setting.setting_value != "true":
        return {"enabled": False, "message": None}

    message_setting = db.query(SystemSettings).filter(
        SystemSettings.setting_key == "service_mode_message"
    ).first()

    return {
        "enabled": True,
        "message": message_setting.setting_value if message_setting else "System is under maintenance. Please try again later.",
    }


def check_demo_mode() -> bool:
    """Check if demo mode is enabled.

    Returns True if demo mode is active.
    """
    settings = get_settings()
    return settings.app.demo_mode


def require_write_access():
    """Dependency that blocks write operations in demo mode.

    Use this dependency on POST/PUT/DELETE endpoints that should be
    blocked in demo mode.
    """
    if check_demo_mode():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is not available in demo mode. This is a read-only demonstration instance.",
        )


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Get the current authenticated user.

    Raises HTTPException if not authenticated.
    """
    token = get_token_from_request(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Find token in database
    auth_token = db.query(AuthToken).filter(AuthToken.token == token).first()

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    if not auth_token.is_valid():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token expired or revoked",
        )

    # Get user
    user = auth_token.user

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Update last used timestamp
    auth_token.last_used_at = datetime.utcnow()
    db.commit()

    # Check service mode - only admins can access during maintenance
    if not user.is_admin:
        service_mode = check_service_mode(db)
        if service_mode["enabled"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=service_mode["message"],
            )

    return user


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Get the current user if authenticated, otherwise None."""
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require admin role."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_manager(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require manager or admin role."""
    if not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )
    return current_user


def get_csrf_token(request: Request) -> str:
    """Get or generate CSRF token for the request."""
    # Check if token exists in cookie
    csrf_token = request.cookies.get("csrf_token")

    if not csrf_token:
        # Generate new token
        csrf_token = secrets.token_urlsafe(32)

    return csrf_token


async def verify_csrf_token(
    request: Request,
    csrf_token: Optional[str] = Cookie(None),
) -> None:
    """Verify CSRF token for mutation requests.

    Compares the token from cookie with the X-CSRF-Token header.
    """
    settings = get_settings()

    if not settings.security.csrf_enabled:
        return

    # Only check for mutation methods
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return

    # Get token from cookie
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing from cookie",
        )

    # Get token from header
    header_token = request.headers.get("X-CSRF-Token")
    if not header_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing from header",
        )

    # Compare tokens
    if not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token mismatch",
        )


def check_equipment_access(user: User, equipment_id: int, db: Session) -> bool:
    """Check if user has access to specific equipment via type access."""
    from app.models.equipment import Equipment, EquipmentTypeUser

    # Admins have access to everything
    if user.is_admin:
        return True

    # Get equipment
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        return False

    # Check type access
    if equipment.type_id:
        access = (
            db.query(EquipmentTypeUser)
            .filter(
                EquipmentTypeUser.type_id == equipment.type_id,
                EquipmentTypeUser.user_id == user.id,
            )
            .first()
        )
        return access is not None

    # No type assigned - allow access
    return True


def check_equipment_manager(user: User, equipment_id: int, db: Session) -> bool:
    """Check if user is a manager of specific equipment."""
    from app.models.equipment import EquipmentManager

    # Admins are considered managers of all equipment
    if user.is_admin:
        return True

    # Check manager assignment
    manager = (
        db.query(EquipmentManager)
        .filter(
            EquipmentManager.equipment_id == equipment_id,
            EquipmentManager.manager_id == user.id,
        )
        .first()
    )
    return manager is not None
