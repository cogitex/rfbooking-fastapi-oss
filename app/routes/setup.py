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

"""Setup API routes for initial configuration."""

import subprocess
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from app.config import get_settings, save_config, update_settings, Settings
from app.config import OrganizationConfig, AdminConfig, EmailConfig, AppConfig


router = APIRouter(prefix="/api/setup", tags=["setup"])


class OrganizationSetup(BaseModel):
    """Organization setup data."""
    name: str
    work_day_start: str = "08:00"
    work_day_end: str = "18:00"


class AdminSetup(BaseModel):
    """Admin setup data."""
    email: EmailStr
    name: str = "Administrator"


class EmailSetup(BaseModel):
    """Email setup data."""
    provider: str = "smtp"
    from_address: str = ""  # Sender email address
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    api_key: str = ""


class SetupRequest(BaseModel):
    """Complete setup request."""
    organization: OrganizationSetup
    admin: AdminSetup
    email: EmailSetup


class SetupStatus(BaseModel):
    """Setup status response."""
    needs_setup: bool
    message: str


@router.get("/status", response_model=SetupStatus)
async def get_setup_status():
    """Check if initial setup is required."""
    settings = get_settings()
    return SetupStatus(
        needs_setup=settings.needs_setup,
        message="Setup required" if settings.needs_setup else "System is configured"
    )


@router.post("/configure")
async def configure_system(request: Request, setup: SetupRequest):
    """Save initial configuration and trigger restart.

    This endpoint only works when the system has not been configured yet.
    """
    settings = get_settings()

    # Only allow setup if not already configured
    if not settings.needs_setup:
        raise HTTPException(
            status_code=403,
            detail="System is already configured. Use admin panel for changes."
        )

    # Validate required fields
    if not setup.organization.name or setup.organization.name == "My Organization":
        raise HTTPException(status_code=400, detail="Please enter your organization name")

    if not setup.admin.email or setup.admin.email == "admin@example.com":
        raise HTTPException(status_code=400, detail="Please enter a valid admin email")

    if not setup.email.from_address or "@" not in setup.email.from_address:
        raise HTTPException(status_code=400, detail="Please enter a valid From Email Address")

    if setup.email.provider == "smtp":
        if not setup.email.smtp_host or setup.email.smtp_host == "smtp.example.com":
            raise HTTPException(status_code=400, detail="Please enter a valid SMTP host")
    elif setup.email.provider == "resend":
        if not setup.email.api_key:
            raise HTTPException(status_code=400, detail="Please enter your Resend API key")

    # Build new settings
    new_settings = Settings(
        app=AppConfig(
            name=settings.app.name,
            debug=settings.app.debug,
            host=settings.app.host,
            port=settings.app.port,
            base_url=settings.app.base_url,
            demo_mode=settings.app.demo_mode,
            setup_completed=True,  # Mark as configured
        ),
        organization=OrganizationConfig(
            name=setup.organization.name,
            work_day_start=setup.organization.work_day_start,
            work_day_end=setup.organization.work_day_end,
        ),
        admin=AdminConfig(
            email=setup.admin.email,
            name=setup.admin.name,
        ),
        email=EmailConfig(
            provider=setup.email.provider,
            smtp_host=setup.email.smtp_host,
            smtp_port=setup.email.smtp_port,
            smtp_username=setup.email.smtp_username,
            smtp_password=setup.email.smtp_password,
            smtp_use_tls=setup.email.smtp_use_tls,
            smtp_use_ssl=False,
            api_key=setup.email.api_key,
            from_address=setup.email.from_address,
            from_name=f"{setup.organization.name} Booking System",
        ),
        database=settings.database,
        ai=settings.ai,
        security=settings.security,
        rate_limit=settings.rate_limit,
        booking=settings.booking,
        notification=settings.notification,
        cleanup=settings.cleanup,
    )

    # Save configuration to file
    try:
        save_config(new_settings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")

    # Update in-memory settings
    update_settings(new_settings)

    # Create admin user in database
    from app.database import get_session_local
    from app.models.user import User

    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == setup.admin.email).first()
        if not admin_user:
            admin_user = User(
                email=setup.admin.email,
                name=setup.admin.name,
                role_id=1,  # Admin role
                is_active=True,
                email_notifications_enabled=True,
            )
            db.add(admin_user)
            db.commit()
            print(f"Created admin user: {setup.admin.email}")
    finally:
        db.close()

    # Trigger restart (in background)
    try:
        # Try supervisorctl first (Docker environment)
        subprocess.Popen(
            ["supervisorctl", "restart", "fastapi"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        # Not in Docker, just continue (dev environment)
        pass

    return {
        "success": True,
        "message": "Configuration saved. System is restarting...",
    }


@router.post("/test-email")
async def test_email_configuration(setup: SetupRequest):
    """Test email configuration by sending a test email.

    This endpoint only works during initial setup.
    """
    settings = get_settings()

    # Only allow during setup
    if not settings.needs_setup:
        raise HTTPException(
            status_code=403,
            detail="System is already configured. Use admin panel for email testing."
        )

    # Import email service
    from app.services.email import send_email_direct

    # Validate from_address
    if not setup.email.from_address or "@" not in setup.email.from_address:
        raise HTTPException(status_code=400, detail="Please enter a valid From Email Address")

    # Build temporary email config
    email_config = EmailConfig(
        provider=setup.email.provider,
        smtp_host=setup.email.smtp_host,
        smtp_port=setup.email.smtp_port,
        smtp_username=setup.email.smtp_username,
        smtp_password=setup.email.smtp_password,
        smtp_use_tls=setup.email.smtp_use_tls,
        smtp_use_ssl=False,
        api_key=setup.email.api_key,
        from_address=setup.email.from_address,
        from_name=f"{setup.organization.name} Booking System",
    )

    # Send test email
    try:
        success = await send_email_direct(
            config=email_config,
            to_email=setup.admin.email,
            subject="RFBooking Test Email",
            html_content=f"""
            <h2>Email Configuration Test</h2>
            <p>This is a test email from your RFBooking installation.</p>
            <p>If you received this email, your email configuration is working correctly!</p>
            <hr>
            <p><small>Organization: {setup.organization.name}</small></p>
            """,
        )

        if success:
            return {"success": True, "message": f"Test email sent to {setup.admin.email}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test email")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email error: {str(e)}")
