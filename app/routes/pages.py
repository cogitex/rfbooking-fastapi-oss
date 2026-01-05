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

from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
        "email_enabled": settings.email.enabled,
    }


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Landing page."""
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
