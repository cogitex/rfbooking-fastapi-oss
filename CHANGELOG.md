# Changelog

All notable changes to RFBooking FastAPI OSS will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2025-12-31

### Added

- **Authentication**
  - Passwordless magic link authentication
  - HTTP-only cookie sessions (30-day expiry)
  - CSRF protection with double submit cookie
  - Role-based access control (Admin/Manager/User)

- **Equipment Management**
  - Equipment CRUD operations
  - Equipment types with categorization
  - Type-based access control
  - Equipment manager assignments
  - Calibration date tracking

- **Booking System**
  - Create, update, cancel bookings
  - Conflict detection with time overlap validation
  - Multi-day booking support
  - Booking reminders (24h before)

- **AI Assistant**
  - Ollama integration with Llama 3.1 8B
  - Natural language equipment recommendations
  - Specification matching rules (frequency, power, temperature, etc.)
  - Auto-download of AI model on first startup

- **Email Notifications** (Optional)
  - Resend API integration
  - Magic link emails
  - Booking confirmations
  - Booking reminders
  - Cancellation notifications
  - Weekly manager reports

- **Scheduled Tasks**
  - APScheduler integration
  - Daily notifications processing
  - Daily cleanup (old tokens, logs)
  - Weekly manager reports (Fridays)

- **Frontend**
  - Jinja2 templates with Tailwind CSS
  - Dashboard with bookings, equipment, reports tabs
  - AI assistant interface
  - Admin panel for user management

- **Deployment**
  - Single Docker container with Supervisor
  - FastAPI + Ollama in one container
  - SQLite database
  - Docker Compose support

- **Documentation**
  - CLAUDE.md developer reference
  - README.md quick start
  - DEPLOYMENT.md production guide
  - CONTRIBUTING.md guidelines
  - SECURITY.md policy

### Technical Details

- Python 3.10+ / FastAPI 0.109+
- SQLAlchemy 2.0 with SQLite
- Ollama with Llama 3.1 8B model
- AGPLv3 license

---

Copyright (C) 2025 Oleg Tokmakov
