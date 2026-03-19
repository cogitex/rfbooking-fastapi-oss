# Project Structure: rfbooking-fastapi-oss

This document outlines the file structure of the `rfbooking-fastapi-oss` project, a FastAPI-based implementation of the booking system.

## Root Directory

| File/Directory | Description |
| :--- | :--- |
| `pyproject.toml` | Python project configuration and dependency management. |
| `docker-compose.yml` | Docker Compose configuration for container orchestration. |
| `Dockerfile` | Instructions for building the application container image. |
| `supervisord.conf` | Configuration for process control system (likely managing app & background tasks). |
| `rfbctl.sh` / `rfbctl.bat` | Control scripts for managing the application (Linux/Windows). |
| `requirements.txt` | Python package dependencies. |
| `CLAUDE.md` | Developer guide and cheat sheet. |
| `README.md` | General project documentation. |

## app/

Main application source code.

| File | Description |
| :--- | :--- |
| `main.py` | Application entry point, initializes FastAPI app and includes routers. |
| `database.py` | Database connection setup and session management. |
| `config.py` | Application configuration loading and validation. |

### app/routes/
API endpoints and route handlers.

| File | Description |
| :--- | :--- |
| `admin.py` | Administrative endpoints. |
| `auth.py` | Authentication logic (login, logout, registration). |
| `bookings.py` | Booking management endpoints. |
| `equipment.py` | Equipment CRUD operations. |
| `manager.py` | Manager-specific functionality. |
| `ai_assistant.py` | Endpoints for AI interactions. |
| `reports.py` | Reporting and data export endpoints. |
| `setup.py` | Initial system setup routes. |
| `pages.py` | Routes serving HTML templates (frontend views). |

### app/models/
Pydantic models or ORM definitions (SQLAlchemy).

| File | Description |
| :--- | :--- |
| `auth.py` | Authentication-related models (Tokens, Credentials). |
| `booking.py` | Booking entity models. |
| `equipment.py` | Equipment entity models. |
| `user.py` | User entity models. |

### app/services/
Business logic layer.

| File | Description |
| :--- | :--- |
| `ai_service.py` | Core AI service integration. |
| `ai_equipment.py` | AI logic specific to equipment queries. |
| `ai_temporal.py` | AI logic for time/scheduling understanding. |
| `email.py` | Email sending service. |
| `notifications.py` | System notification logic. |
| `scheduler.py` | Background task scheduling service. |

### app/middleware/
| File | Description |
| :--- | :--- |
| `auth.py` | Authentication middleware (JWT verification, etc.). |

### app/utils/
| File | Description |
| :--- | :--- |
| `helpers.py` | General utility functions. |

## templates/

Jinja2 HTML templates for the frontend interface.

| File | Description |
| :--- | :--- |
| `base.html` | Base layout template. |
| `index.html` | Home page template. |
| `dashboard.html` | Main user dashboard. |
| `login.html` | Login page. |
| `setup.html` | Setup wizard page. |
| `auth_redirect.html` | Template for handling auth redirects. |

## static/

Static assets served by the application.

| File | Description |
| :--- | :--- |
| `css/styles.css` | Global stylesheets. |
| `js/dashboard.js` | Frontend JavaScript for the dashboard. |

## config/

Configuration files.

| File | Description |
| :--- | :--- |
| `config.yaml` | Main application configuration (often created from example). |
| `config.example.yaml` | Template configuration file. |

## data/

Directory for persistent data.

| File | Description |
| :--- | :--- |
| `rfbooking.db` | SQLite database file (if using SQLite). |

## docs/

Project documentation.

| File | Description |
| :--- | :--- |
| `DEPLOYMENT.md` | Deployment guides. |
| `IMPROVEMENT_PLAN.md` | Planned improvements and roadmap. |
| `SETUP_IMPLEMENTATION_PLAN.md` | Details on the setup process implementation. |

## scripts/

Utility scripts.

| File | Description |
| :--- | :--- |
| `init_db.py` | Database initialization script. |
| `entrypoint.sh` | Docker entrypoint script. |

## migrations/

Database migration files (likely Alembic).
