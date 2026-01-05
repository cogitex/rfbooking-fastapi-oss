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

"""Authentication routes."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user, get_csrf_token
from app.models.auth import AuthToken, MagicLink
from app.models.user import User
from app.models.equipment import EquipmentType, EquipmentTypeUser
from app.utils.helpers import generate_token, is_valid_email

router = APIRouter(prefix="/api/auth")


class RegisterRequest(BaseModel):
    """Registration/login request."""

    email: EmailStr
    name: Optional[str] = None


class RegisterResponse(BaseModel):
    """Registration response."""

    success: bool
    message: str
    dev_mode: bool = False
    verify_link: Optional[str] = None


class UserResponse(BaseModel):
    """User info response."""

    id: int
    email: str
    name: str
    role_id: int
    role_name: str
    is_active: bool
    email_notifications_enabled: bool


@router.post("/register", response_model=RegisterResponse)
async def register(
    request: Request,
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register or login user with email (passwordless magic link)."""
    settings = get_settings()

    email = data.email.lower().strip()
    name = data.name or email.split("@")[0]

    if not is_valid_email(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    # Check if user exists
    user = db.query(User).filter(User.email == email).first()

    if user and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Generate magic link token
    token = generate_token(32)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.security.magic_link_minutes)

    # Get client IP
    ip_address = request.client.host if request.client else None

    # Create magic link
    magic_link = MagicLink(
        email=email,
        name=name,
        token=token,
        expires_at=expires_at,
        ip_address=ip_address,
        user_id=user.id if user else None,
    )
    db.add(magic_link)
    db.commit()

    # Build verification URL
    verify_url = f"{settings.app.base_url}/auth/verify?token={token}"

    # Check if email is enabled
    if settings.email.enabled:
        # Send magic link email
        from app.services.email import get_email_service

        email_service = get_email_service()
        try:
            await email_service.send_magic_link(email, token, name)
            return RegisterResponse(
                success=True,
                message=f"Magic link sent to {email}. Check your inbox.",
                dev_mode=False,
            )
        except Exception as e:
            # Log error but don't expose details
            print(f"Failed to send email: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email",
            )
    else:
        # Dev mode - return link directly
        return RegisterResponse(
            success=True,
            message="Email disabled. Use the verification link below.",
            dev_mode=True,
            verify_link=verify_url,
        )


@router.get("/verify")
async def verify_magic_link(
    token: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """Verify magic link and create session."""
    settings = get_settings()

    # Find magic link
    magic_link = db.query(MagicLink).filter(MagicLink.token == token).first()

    if not magic_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired magic link",
        )

    if not magic_link.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Magic link has expired or already been used",
        )

    # Mark magic link as used
    magic_link.used = True
    magic_link.used_at = datetime.utcnow()

    # Get or create user
    user = db.query(User).filter(User.email == magic_link.email).first()

    if not user:
        # Create new user
        # Check if this should be admin
        is_admin = magic_link.email.lower() == settings.admin.email.lower()

        user = User(
            email=magic_link.email,
            name=magic_link.name or magic_link.email.split("@")[0],
            role_id=1 if is_admin else 3,  # Admin or regular user
            is_active=True,
            email_notifications_enabled=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Grant access to all equipment types for new user
        equipment_types = db.query(EquipmentType).filter(EquipmentType.is_active == True).all()
        for eq_type in equipment_types:
            type_access = EquipmentTypeUser(
                type_id=eq_type.id,
                user_id=user.id,
            )
            db.add(type_access)

    # Update last login
    user.last_login_at = datetime.utcnow()

    # Clean up old tokens if over limit
    user_tokens = (
        db.query(AuthToken)
        .filter(AuthToken.user_id == user.id, AuthToken.is_revoked == False)
        .order_by(AuthToken.created_at.desc())
        .all()
    )

    if len(user_tokens) >= settings.security.max_tokens_per_user:
        # Revoke oldest tokens
        for old_token in user_tokens[settings.security.max_tokens_per_user - 1 :]:
            old_token.is_revoked = True

    # Create auth token
    auth_token = AuthToken(
        user_id=user.id,
        token=generate_token(32),
        expires_at=datetime.utcnow() + timedelta(days=settings.security.auth_token_days),
    )
    db.add(auth_token)
    db.commit()

    # Set cookies
    response.set_cookie(
        key="auth_token",
        value=auth_token.token,
        httponly=True,
        secure=not settings.app.debug,
        samesite="lax",
        max_age=settings.security.auth_token_days * 24 * 60 * 60,
    )

    # Set CSRF token
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # JavaScript needs to read this
        secure=not settings.app.debug,
        samesite="lax",
        max_age=settings.security.auth_token_days * 24 * 60 * 60,
    )

    # Return redirect response
    response.status_code = status.HTTP_302_FOUND
    response.headers["Location"] = "/dashboard"
    return response


@router.get("/validate")
async def validate_session(
    request: Request,
    db: Session = Depends(get_db),
):
    """Check if current session is valid."""
    from app.middleware.auth import get_token_from_request

    token = get_token_from_request(request)

    if not token:
        return {"valid": False}

    auth_token = db.query(AuthToken).filter(AuthToken.token == token).first()

    if not auth_token or not auth_token.is_valid():
        return {"valid": False}

    if not auth_token.user or not auth_token.user.is_active:
        return {"valid": False}

    return {"valid": True, "user_id": auth_token.user_id}


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user info."""
    return {
        "success": True,
        "user": current_user.to_dict(),
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Logout and revoke current session."""
    from app.middleware.auth import get_token_from_request

    token = get_token_from_request(request)

    if token:
        auth_token = db.query(AuthToken).filter(AuthToken.token == token).first()
        if auth_token:
            auth_token.is_revoked = True
            db.commit()

    # Clear cookies
    response.delete_cookie("auth_token")
    response.delete_cookie("csrf_token")

    return {"success": True, "message": "Logged out successfully"}
