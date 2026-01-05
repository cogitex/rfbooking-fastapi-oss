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

"""API routes package."""

from fastapi import APIRouter

from app.routes import auth, equipment, bookings, admin, manager, reports, ai_assistant, pages

# Create main API router
api_router = APIRouter()

# Include all API routes
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(equipment.router, tags=["Equipment"])
api_router.include_router(bookings.router, tags=["Bookings"])
api_router.include_router(admin.router, tags=["Admin"])
api_router.include_router(manager.router, tags=["Manager"])
api_router.include_router(reports.router, tags=["Reports"])
api_router.include_router(ai_assistant.router, tags=["AI Assistant"])

# Page routes (HTML templates)
pages_router = pages.router

__all__ = ["api_router", "pages_router"]
