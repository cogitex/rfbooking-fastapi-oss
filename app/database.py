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

"""Database setup and connection management."""

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import get_settings

# Base class for all models
Base = declarative_base()

# Global engine and session factory
_engine = None
_SessionLocal = None


def get_database_url() -> str:
    """Get the database URL from settings."""
    settings = get_settings()
    db_path = settings.database.path

    # Ensure directory exists
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    return f"sqlite:///{db_path}"


def init_engine():
    """Initialize the database engine."""
    global _engine, _SessionLocal

    database_url = get_database_url()

    _engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        echo=get_settings().app.debug,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    return _engine


def get_engine():
    """Get the database engine, initializing if needed."""
    global _engine
    if _engine is None:
        init_engine()
    return _engine


def get_session_local():
    """Get the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        init_engine()
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    # Import all models to ensure they're registered
    from app.models import auth, booking, equipment, user  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def init_database():
    """Initialize database with tables and seed data."""
    from app.models.user import Role, User
    from app.config import get_settings

    create_tables()

    settings = get_settings()
    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        # Seed roles if they don't exist
        roles_data = [
            (1, "admin", "Administrator - full access to all features"),
            (2, "manager", "Manager - can manage equipment and view all bookings"),
            (3, "user", "User - can create and manage own bookings"),
        ]

        for role_id, name, description in roles_data:
            existing = db.query(Role).filter(Role.id == role_id).first()
            if not existing:
                role = Role(id=role_id, name=name, description=description)
                db.add(role)

        db.commit()

        # Create admin user if doesn't exist
        admin_email = settings.admin.email
        admin_user = db.query(User).filter(User.email == admin_email).first()

        if not admin_user:
            admin_user = User(
                email=admin_email,
                name=settings.admin.name,
                role_id=1,  # Admin role
                is_active=True,
                email_notifications_enabled=True,
            )
            db.add(admin_user)
            db.commit()
            print(f"Created admin user: {admin_email}")

        # Seed default cron jobs
        from app.models.auth import CronJob

        cron_jobs_data = [
            (
                "daily_notifications",
                "Daily Notifications",
                "Send booking and calibration reminders",
                "0 8 * * *",
            ),
            (
                "daily_cleanup",
                "Daily Cleanup",
                "Clean up expired tokens and old records",
                "0 8 * * *",
            ),
            (
                "weekly_manager_reports",
                "Weekly Manager Reports",
                "Send weekly booking reports to managers",
                "0 9 * * 5",
            ),
        ]

        for job_key, job_name, description, cron_schedule in cron_jobs_data:
            existing = db.query(CronJob).filter(CronJob.job_key == job_key).first()
            if not existing:
                job = CronJob(
                    job_key=job_key,
                    job_name=job_name,
                    description=description,
                    cron_schedule=cron_schedule,
                    is_enabled=True,
                )
                db.add(job)

        db.commit()

        # Seed default AI specification rules
        from app.models.equipment import AISpecificationRule

        ai_rules_data = [
            {
                "rule_type": "general",
                "parameter_name": None,
                "parameter_unit": None,
                "prompt_text": "When selecting equipment, match user requirements to equipment specifications. Recommend equipment where the user's requirements fall within the equipment's operating range.",
                "display_order": 0,
            },
            {
                "rule_type": "parameter",
                "parameter_name": "frequency",
                "parameter_unit": "GHz",
                "prompt_text": "For frequency requirements: The user's required frequency must fall within the equipment's frequency range. Example: Equipment with 0.6-4.0 GHz range can handle 1.5 GHz requests.",
                "display_order": 1,
            },
            {
                "rule_type": "parameter",
                "parameter_name": "power",
                "parameter_unit": "W",
                "prompt_text": "For power requirements: Equipment maximum power (CW or Pulsed) MUST be greater than or equal to the user's required power. This is a strict requirement.",
                "display_order": 2,
            },
            {
                "rule_type": "parameter",
                "parameter_name": "temperature",
                "parameter_unit": "°C",
                "prompt_text": "For temperature requirements: The user's required temperature must fall within the equipment's operating temperature range. Support formats: 250°C, 250degC, 250 C.",
                "display_order": 3,
            },
            {
                "rule_type": "parameter",
                "parameter_name": "voltage",
                "parameter_unit": "V",
                "prompt_text": "For voltage requirements: The user's required voltage must fall within the equipment's voltage range.",
                "display_order": 4,
            },
            {
                "rule_type": "parameter",
                "parameter_name": "current",
                "parameter_unit": "A",
                "prompt_text": "For current requirements: The user's required current must fall within the equipment's current range. Support decimal precision.",
                "display_order": 5,
            },
        ]

        for rule_data in ai_rules_data:
            existing = db.query(AISpecificationRule).filter(
                AISpecificationRule.rule_type == rule_data["rule_type"],
                AISpecificationRule.parameter_name == rule_data["parameter_name"],
            ).first()
            if not existing:
                rule = AISpecificationRule(**rule_data, is_enabled=True)
                db.add(rule)

        db.commit()
        print("Database initialized successfully")

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
