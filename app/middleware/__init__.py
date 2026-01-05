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

"""Middleware package."""

from app.middleware.auth import (
    get_current_user,
    get_current_user_optional,
    require_admin,
    require_manager,
    verify_csrf_token,
    get_csrf_token,
)

__all__ = [
    "get_current_user",
    "get_current_user_optional",
    "require_admin",
    "require_manager",
    "verify_csrf_token",
    "get_csrf_token",
]
