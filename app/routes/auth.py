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
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user, get_csrf_token, check_service_mode
from app.models.auth import AuthToken, MagicLink, RegistrationSettings, AllowedEmail
from app.models.user import User
from app.models.equipment import EquipmentType, EquipmentTypeUser
from app.utils.helpers import generate_token, is_valid_email

router = APIRouter(prefix="/api/auth")

# Templates for auth redirects
templates = Jinja2Templates(directory="templates")


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

    # If user doesn't exist, check registration settings
    if not user:
        reg_settings = db.query(RegistrationSettings).first()

        # Check if registration is restricted
        if reg_settings and reg_settings.registration_mode == "restricted":
            email_domain = email.split("@")[1].lower()

            # Check allowed domains
            domain_allowed = False
            if reg_settings.allowed_domains:
                allowed_domains = [d.strip().lower() for d in reg_settings.allowed_domains.split(",")]
                domain_allowed = email_domain in allowed_domains

            # Check specific email allowlist
            email_allowed = db.query(AllowedEmail).filter(AllowedEmail.email == email).first() is not None

            # Also allow the configured admin email
            is_admin_email = email.lower() == settings.admin.email.lower()

            if not domain_allowed and not email_allowed and not is_admin_email:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Registration is restricted. Your email is not in the allowlist.",
                )

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
    verify_url = f"{settings.app.base_url}/api/auth/verify?token={token}"

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
        # Log error and fall back to showing the link (for dev/misconfigured email)
        print(f"Failed to send email: {e}")
        return RegisterResponse(
            success=True,
            message=f"Email sending failed. Use the verification link below. Error: {str(e)[:100]}",
            dev_mode=True,
            verify_link=verify_url,
        )


@router.get("/verify", response_class=HTMLResponse)
async def verify_magic_link(
    request: Request,
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

    # Token reuse logic for Chrome mobile prefetch
    # If magic link was used within 2 minutes and has a valid auth token, reuse it
    if magic_link.used and magic_link.used_at:
        time_since_use = (datetime.utcnow() - magic_link.used_at).total_seconds()
        if time_since_use < 120:  # 2 minutes
            # Check if we have a valid auth token to reuse
            if magic_link.last_auth_token_id:
                existing_token = db.query(AuthToken).filter(
                    AuthToken.id == magic_link.last_auth_token_id
                ).first()
                if existing_token and existing_token.is_valid():
                    # Reuse existing token - return same session
                    html_response = templates.TemplateResponse(
                        "auth_redirect.html",
                        {
                            "request": request,
                            "app_name": settings.app.name,
                            "redirect_url": "/dashboard",
                        },
                    )
                    html_response.set_cookie(
                        key="auth_token",
                        value=existing_token.token,
                        httponly=True,
                        secure=not settings.app.debug,
                        samesite="lax",
                        max_age=settings.security.auth_token_days * 24 * 60 * 60,
                    )
                    csrf_token = secrets.token_urlsafe(32)
                    html_response.set_cookie(
                        key="csrf_token",
                        value=csrf_token,
                        httponly=False,
                        secure=not settings.app.debug,
                        samesite="lax",
                        max_age=settings.security.auth_token_days * 24 * 60 * 60,
                    )
                    return html_response

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
    db.refresh(auth_token)

    # Store auth token ID in magic link for reuse within 2 minutes
    magic_link.last_auth_token_id = auth_token.id
    db.commit()

    # Create HTML response with redirect page
    # This fixes Chrome mobile email client prefetching issues
    # The delayed JavaScript redirect ensures cookies are properly set
    html_response = templates.TemplateResponse(
        "auth_redirect.html",
        {
            "request": request,
            "app_name": settings.app.name,
            "redirect_url": "/dashboard",
        },
    )

    # Set auth cookie
    html_response.set_cookie(
        key="auth_token",
        value=auth_token.token,
        httponly=True,
        secure=not settings.app.debug,
        samesite="lax",
        max_age=settings.security.auth_token_days * 24 * 60 * 60,
    )

    # Set CSRF token
    csrf_token = secrets.token_urlsafe(32)
    html_response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # JavaScript needs to read this
        secure=not settings.app.debug,
        samesite="lax",
        max_age=settings.security.auth_token_days * 24 * 60 * 60,
    )

    return html_response


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


@router.get("/service-mode")
async def get_service_mode_status(
    db: Session = Depends(get_db),
):
    """Get current service mode status (public endpoint for login page)."""
    status = check_service_mode(db)
    return {
        "enabled": status["enabled"],
        "message": status["message"] if status["enabled"] else None,
    }
