#!/usr/bin/env python3
# RFBooking FastAPI OSS - Self-hosted Equipment Booking System
# Copyright (C) 2025 Oleg Tokmakov
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Database initialization script."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import init_settings
from app.database import init_database


def main():
    """Initialize the database."""
    print("Initializing RFBooking database...")

    # Load configuration
    init_settings()

    # Initialize database
    init_database()

    print("Database initialization complete!")


if __name__ == "__main__":
    main()
