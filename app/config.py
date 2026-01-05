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

"""Configuration management for RFBooking FastAPI OSS."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Application configuration."""

    name: str = "RFBooking"
    secret_key: str = Field(default="change-this-to-a-random-secret-key")
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = "http://localhost:8000"


class AdminConfig(BaseModel):
    """Admin user configuration."""

    email: str = "admin@example.com"
    name: str = "Administrator"


class OrganizationConfig(BaseModel):
    """Organization configuration."""

    name: str = "My Organization"
    work_day_start: str = "08:00"
    work_day_end: str = "18:00"


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: str = "/data/rfbooking.db"


class EmailConfig(BaseModel):
    """Email configuration."""

    enabled: bool = False
    provider: str = "resend"
    api_key: str = ""
    from_address: str = "noreply@example.com"
    from_name: str = "RFBooking System"


class AIConfig(BaseModel):
    """AI Assistant configuration."""

    enabled: bool = True
    model: str = "llama3.1:8b"
    ollama_host: str = "http://localhost:11434"
    max_tokens: int = 800
    temperature: float = 0.3


class SecurityConfig(BaseModel):
    """Security configuration."""

    auth_token_days: int = 30
    magic_link_minutes: int = 15
    max_tokens_per_user: int = 10
    csrf_enabled: bool = True


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    max_bookings_per_user_per_day: int = 20
    max_ai_requests_per_5min: int = 10


class BookingConfig(BaseModel):
    """Booking constraints configuration."""

    max_duration_days: int = 30
    max_description_length: int = 10240
    reminder_hours: int = 24
    calibration_reminder_days: int = 7


class CleanupConfig(BaseModel):
    """Cleanup settings configuration."""

    auth_token_retention_days: int = 7
    magic_link_retention_days: int = 7
    ai_query_log_retention_days: int = 7
    notification_log_retention_days: int = 30


class Settings(BaseModel):
    """Main settings container."""

    app: AppConfig = Field(default_factory=AppConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    organization: OrganizationConfig = Field(default_factory=OrganizationConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    booking: BookingConfig = Field(default_factory=BookingConfig)
    cleanup: CleanupConfig = Field(default_factory=CleanupConfig)


def load_config(config_path: Optional[str] = None) -> Settings:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, tries default locations.

    Returns:
        Settings object with loaded configuration.
    """
    # Default config paths to try
    default_paths = [
        Path("config/config.yaml"),
        Path("config.yaml"),
        Path("/app/config/config.yaml"),
        Path("/etc/rfbooking/config.yaml"),
    ]

    # Allow override via environment variable
    if config_path is None:
        config_path = os.environ.get("RFBOOKING_CONFIG")

    config_file = None

    if config_path:
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
    else:
        for path in default_paths:
            if path.exists():
                config_file = path
                break

    if config_file is None:
        print("No config file found, using defaults")
        return Settings()

    print(f"Loading config from: {config_file}")

    with open(config_file, "r") as f:
        config_data = yaml.safe_load(f) or {}

    return Settings(**config_data)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = load_config()
    return _settings


def init_settings(config_path: Optional[str] = None) -> Settings:
    """Initialize settings from config file."""
    global _settings
    _settings = load_config(config_path)
    return _settings
