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

"""HTML page routes using Jinja2 templates."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, Response
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user_optional
from app.models.user import User

router = APIRouter()

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")


def get_template_context(request: Request, user: Optional[User] = None) -> dict:
    """Get common template context."""
    settings = get_settings()
    return {
        "request": request,
        "user": user.to_dict() if user else None,
        "app_name": settings.app.name,
        "organization_name": settings.organization.name,
        "ai_enabled": settings.ai.enabled,
        "demo_mode": settings.app.demo_mode,
    }


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Landing page."""
    settings = get_settings()

    # Redirect to setup if not configured
    if settings.needs_setup:
        return RedirectResponse(url="/setup", status_code=302)

    if user:
        return RedirectResponse(url="/dashboard", status_code=302)

    context = get_template_context(request, user)
    return templates.TemplateResponse("index.html", context)


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Login page."""
    settings = get_settings()

    # Redirect to setup if not configured
    if settings.needs_setup:
        return RedirectResponse(url="/setup", status_code=302)

    if user:
        return RedirectResponse(url="/dashboard", status_code=302)

    context = get_template_context(request, user)
    return templates.TemplateResponse("login.html", context)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Main dashboard page."""
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    context = get_template_context(request, user)
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/bookings", response_class=HTMLResponse)
async def bookings_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Bookings management page."""
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    context = get_template_context(request, user)
    return templates.TemplateResponse("dashboard.html", {**context, "active_tab": "bookings"})


@router.get("/equipment", response_class=HTMLResponse)
async def equipment_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Equipment management page."""
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    context = get_template_context(request, user)
    return templates.TemplateResponse("dashboard.html", {**context, "active_tab": "equipment"})


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Reports page."""
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    context = get_template_context(request, user)
    return templates.TemplateResponse("dashboard.html", {**context, "active_tab": "reports"})


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Admin page."""
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=302)

    context = get_template_context(request, user)
    return templates.TemplateResponse("dashboard.html", {**context, "active_tab": "admin"})


@router.get("/ai-assistant", response_class=HTMLResponse)
async def ai_assistant_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """AI Assistant page."""
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    settings = get_settings()
    if not settings.ai.enabled:
        return RedirectResponse(url="/dashboard", status_code=302)

    context = get_template_context(request, user)
    return templates.TemplateResponse("dashboard.html", {**context, "active_tab": "ai"})


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Setup page with configuration wizard or download links."""
    settings = get_settings()
    context = {
        "request": request,
        "app_name": settings.app.name,
        "base_url": settings.app.base_url,
        "needs_setup": settings.needs_setup,
        "current_config": {
            "organization_name": settings.organization.name,
            "admin_email": settings.admin.email,
            "admin_name": settings.admin.name,
            "email_provider": settings.email.provider,
            "smtp_host": settings.email.smtp_host,
            "smtp_port": settings.email.smtp_port,
            "smtp_username": settings.email.smtp_username,
            "smtp_use_tls": settings.email.smtp_use_tls,
            "work_day_start": settings.organization.work_day_start,
            "work_day_end": settings.organization.work_day_end,
        },
    }
    return templates.TemplateResponse("setup.html", context)


@router.get("/setup/download/{filename}")
async def download_setup_file(filename: str):
    """Download setup files (rfbctl.sh, rfbctl.bat, config.yaml, docker-compose.yml)."""
    # Define allowed files and their paths
    allowed_files = {
        "rfbctl.sh": Path("/app/rfbctl.sh"),
        "rfbctl.bat": Path("/app/rfbctl.bat"),
        "config.yaml": Path("/app/config/config.example.yaml"),
        "docker-compose.yml": Path("/app/docker-compose.yml"),
    }

    # Also check local paths for development
    local_paths = {
        "rfbctl.sh": Path("rfbctl.sh"),
        "rfbctl.bat": Path("rfbctl.bat"),
        "config.yaml": Path("config/config.example.yaml"),
        "docker-compose.yml": Path("docker-compose.yml"),
    }

    if filename not in allowed_files:
        raise HTTPException(status_code=404, detail="File not found")

    # Try container path first, then local path
    file_path = allowed_files[filename]
    if not file_path.exists():
        file_path = local_paths[filename]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Set content type based on file
    media_type = "text/plain"
    if filename.endswith(".yaml") or filename.endswith(".yml"):
        media_type = "text/yaml"
    elif filename.endswith(".sh"):
        media_type = "text/x-shellscript"
    elif filename.endswith(".bat"):
        media_type = "application/x-bat"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )
