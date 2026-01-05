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

"""Database models for RFBooking FastAPI OSS."""

from app.models.user import Role, User
from app.models.auth import AuthToken, MagicLink, CronJob, NotificationLog
from app.models.equipment import (
    Equipment,
    EquipmentType,
    EquipmentTypeUser,
    EquipmentManager,
    AISpecificationRule,
    AIUsage,
    AIQueryLog,
)
from app.models.booking import Booking

__all__ = [
    "Role",
    "User",
    "AuthToken",
    "MagicLink",
    "CronJob",
    "NotificationLog",
    "Equipment",
    "EquipmentType",
    "EquipmentTypeUser",
    "EquipmentManager",
    "AISpecificationRule",
    "AIUsage",
    "AIQueryLog",
    "Booking",
]
