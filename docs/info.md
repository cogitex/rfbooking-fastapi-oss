

  | File               | Purpose                                     | Priority |
  |--------------------|---------------------------------------------|----------|
  | CONTRIBUTING.md    | How to contribute (issues, PRs, code style) | High     |
  | SECURITY.md        | Security policy, vulnerability reporting    | High     |
  | CHANGELOG.md       | Version history                             | Medium   |
  | docs/DEPLOYMENT.md | Production deployment guide                 | Medium   |
  | docs/API.md        | OpenAPI/Swagger export instructions         | Low      |

  Would you like me to create these? I'd suggest at minimum:

  1. CONTRIBUTING.md - Essential for OSS projects
  2. SECURITY.md - Standard for projects handling user data



 Plan saved to: ~/.claude/plans/harmonic-puzzling-quiche.md · /plan to edit
     RFBooking FastAPI OSS - Implementation Plan

     Project Overview

     Create a self-hosted equipment booking system at /home/oto/cf/rfbooking-fastapi-oss based on rfbooking-core, using:
     - FastAPI web framework with Jinja2 templates
     - SQLite database (single-tenant)
     - Ollama with Llama 3.1 8B for AI assistant
     - Single Docker container with Supervisor
     - AGPLv3 license, Copyright Oleg Tokmakov 31.12.2025
     - Optional email via Resend API (configurable)

     ---
     Phase 1: Project Scaffold & Configuration

     1.1 Create Project Structure

     /home/oto/cf/rfbooking-fastapi-oss/
     ├── app/
     │   ├── __init__.py
     │   ├── main.py                 # FastAPI app entry point
     │   ├── config.py               # Settings from config file
     │   ├── database.py             # SQLite connection & models
     │   ├── models/                 # SQLAlchemy models
     │   │   ├── __init__.py
     │   │   ├── user.py
     │   │   ├── equipment.py
     │   │   ├── booking.py
     │   │   └── auth.py
     │   ├── routes/                 # API & page routes
     │   │   ├── __init__.py
     │   │   ├── auth.py
     │   │   ├── equipment.py
     │   │   ├── bookings.py
     │   │   ├── admin.py
     │   │   ├── manager.py
     │   │   ├── reports.py
     │   │   ├── ai_assistant.py
     │   │   └── pages.py            # HTML page routes
     │   ├── services/               # Business logic
     │   │   ├── __init__.py
     │   │   ├── email.py            # Resend integration
     │   │   ├── notifications.py
     │   │   ├── ai_service.py       # Ollama integration
     │   │   └── scheduler.py        # APScheduler for cron jobs
     │   ├── middleware/
     │   │   ├── __init__.py
     │   │   └── auth.py             # Auth & CSRF middleware
     │   └── utils/
     │       ├── __init__.py
     │       └── helpers.py
     ├── templates/                  # Jinja2 templates
     │   ├── base.html
     │   ├── index.html              # Landing page
     │   ├── dashboard.html          # Main dashboard
     │   ├── login.html
     │   └── components/             # Reusable components
     ├── static/                     # CSS, JS, images
     │   ├── css/
     │   │   └── styles.css
     │   └── js/
     │       └── dashboard.js
     ├── migrations/                 # Alembic migrations
     ├── config/
     │   └── config.example.yaml     # Example config file
     ├── scripts/
     │   ├── entrypoint.sh           # Docker entrypoint
     │   └── init_db.py              # Database initialization
     ├── Dockerfile
     ├── supervisord.conf
     ├── requirements.txt
     ├── pyproject.toml
     ├── LICENSE                     # AGPLv3
     ├── README.md
     └── .env.example

     1.2 Configuration File (config/config.example.yaml)

     # RFBooking FastAPI OSS Configuration
     app:
       name: "RFBooking"
       secret_key: "change-this-to-random-string"
       debug: false
       host: "0.0.0.0"
       port: 8000

     # Admin user (created on first startup)
     admin:
       email: "admin@example.com"
       name: "Administrator"

     # Organization settings
     organization:
       name: "My Organization"
       work_day_start: "08:00"
       work_day_end: "18:00"

     # Database
     database:
       path: "/data/rfbooking.db"

     # Email (optional)
     email:
       enabled: false                 # Set to true to enable email notifications
       provider: "resend"
       api_key: ""                    # Resend API key
       from_address: "noreply@example.com"
       from_name: "RFBooking System"

     # AI Assistant
     ai:
       enabled: true
       model: "llama3.1:8b"
       ollama_host: "http://localhost:11434"
       max_tokens: 800
       temperature: 0.3

     # Security
     security:
       auth_token_days: 30
       magic_link_minutes: 15
       max_tokens_per_user: 10
       csrf_enabled: true

     1.3 License Header Template

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

     ---
     Phase 2: Database Schema (SQLite with SQLAlchemy)

     2.1 Tables to Create (simplified single-tenant)

     | Table                  | Purpose                                 |
     |------------------------|-----------------------------------------|
     | roles                  | Role definitions (admin, manager, user) |
     | users                  | User accounts                           |
     | auth_tokens            | Session tokens                          |
     | magic_links            | Passwordless auth links                 |
     | equipment_types        | Equipment categories                    |
     | equipment              | Equipment inventory                     |
     | equipment_type_users   | Type-based access control               |
     | equipment_managers     | Equipment manager assignments           |
     | bookings               | Equipment reservations                  |
     | notification_log       | Email notification tracking             |
     | cron_jobs              | Scheduled task config                   |
     | ai_usage               | AI usage tracking                       |
     | ai_query_log           | AI query details                        |
     | ai_specification_rules | AI prompt rules                         |
     | settings               | Organization settings                   |

     2.2 Key Model: User (app/models/user.py)

     class User(Base):
         __tablename__ = "users"

         id = Column(Integer, primary_key=True)
         email = Column(String, unique=True, nullable=False)
         name = Column(String, nullable=False)
         role_id = Column(Integer, ForeignKey("roles.id"), default=3)
         is_active = Column(Boolean, default=True)
         email_notifications_enabled = Column(Boolean, default=True)
         created_at = Column(DateTime, default=datetime.utcnow)
         last_login_at = Column(DateTime, nullable=True)

     ---
     Phase 3: Authentication System

     3.1 Passwordless Magic Link Flow

     1. User submits email → Generate token → Store in magic_links
     2. If email enabled: Send email with verification link
     3. If email disabled: Display link directly (dev/testing mode)
     4. User clicks link → Validate token → Create auth_token
     5. Set HTTP-only cookie with token

     3.2 Middleware (app/middleware/auth.py)

     - get_current_user() - Dependency to get authenticated user
     - require_role(role) - Role-based access decorator
     - csrf_protect() - CSRF validation for mutations

     ---
     Phase 4: API Routes (FastAPI)

     4.1 Route Files to Create

     | File            | Endpoints                                                            |
     |-----------------|----------------------------------------------------------------------|
     | auth.py         | /api/auth/register, /api/auth/verify, /api/auth/me, /api/auth/logout |
     | equipment.py    | /api/equipment CRUD, /api/equipment-types CRUD                       |
     | bookings.py     | /api/bookings CRUD with conflict detection                           |
     | admin.py        | /api/admin/users, /api/admin/cron-jobs, settings                     |
     | manager.py      | /api/manager/equipment, /api/manager/bookings                        |
     | reports.py      | /api/reports/equipment-usage, /api/reports/user-activity             |
     | ai_assistant.py | /api/ai/analyze, /api/ai/chat, /api/ai/usage                         |
     | pages.py        | HTML page routes with Jinja2 templates                               |

     4.2 Example Route (app/routes/bookings.py)

     @router.post("/api/bookings")
     async def create_booking(
         booking: BookingCreate,
         current_user: User = Depends(get_current_user),
         db: Session = Depends(get_db)
     ):
         # Check equipment access
         # Detect conflicts
         # Create booking
         # Queue notification
         return {"success": True, "booking": booking_data}

     ---
     Phase 5: AI Assistant (Ollama Integration)

     5.1 AI Service (app/services/ai_service.py)

     import ollama

     class AIService:
         def __init__(self, config):
             self.model = config.ai.model
             self.client = ollama.Client(host=config.ai.ollama_host)

         async def analyze_booking_request(self, prompt: str, equipment_list: list):
             # Stage 0: Parse temporal expressions
             # Stage 1: Equipment matching with Ollama
             # Stage 2: SQL availability search
             pass

     5.2 Specification Rules

     - Port ai_specification_rules table and logic
     - Pre-filter equipment before AI call
     - Validate AI responses against rules

     ---
     Phase 6: Email Notifications (Optional)

     6.1 Email Service (app/services/email.py)

     class EmailService:
         def __init__(self, config):
             self.enabled = config.email.enabled
             if self.enabled:
                 self.resend = resend
                 resend.api_key = config.email.api_key

         async def send_magic_link(self, email: str, token: str, name: str):
             if not self.enabled:
                 return {"dev_mode": True, "link": f"/auth/verify?token={token}"}
             # Send via Resend

     6.2 Notification Types

     - Booking confirmations
     - Booking reminders (24h before)
     - Cancellation notifications
     - Calibration reminders
     - Weekly manager reports

     ---
     Phase 7: Scheduled Tasks (APScheduler)

     7.1 Cron Jobs (app/services/scheduler.py)

     from apscheduler.schedulers.asyncio import AsyncIOScheduler

     scheduler = AsyncIOScheduler()

     # Daily at 8 AM: Process notifications
     @scheduler.scheduled_job('cron', hour=8)
     async def daily_notifications():
         pass

     # Daily at 8 AM: Cleanup old tokens
     @scheduler.scheduled_job('cron', hour=8)
     async def daily_cleanup():
         pass

     # Friday at 9 AM: Weekly reports
     @scheduler.scheduled_job('cron', day_of_week='fri', hour=9)
     async def weekly_reports():
         pass

     ---
     Phase 8: Frontend (Jinja2 Templates)

     8.1 Templates to Create

     - base.html - Base layout with navigation
     - index.html - Landing page (port from existing)
     - login.html - Email input form
     - dashboard.html - Main dashboard with tabs
     - components/ - Reusable UI components

     8.2 JavaScript (static/js/dashboard.js)

     - Port existing dashboard.js logic
     - Update API endpoints
     - Keep CSRF token handling

     8.3 Styling

     - Port existing Tailwind CSS
     - Keep brand color palette

     ---
     Phase 9: Docker Configuration

     9.1 Dockerfile

     FROM python:3.11-slim

     # Install Ollama
     RUN curl -fsSL https://ollama.com/install.sh | sh

     # Install supervisor
     RUN apt-get update && apt-get install -y supervisor curl && rm -rf /var/lib/apt/lists/*

     # Create app directory
     WORKDIR /app

     # Install Python dependencies
     COPY requirements.txt .
     RUN pip install --no-cache-dir -r requirements.txt

     # Copy application
     COPY . .

     # Create data directory
     RUN mkdir -p /data

     # Copy supervisor config
     COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

     # Expose port
     EXPOSE 8000

     # Entrypoint
     COPY scripts/entrypoint.sh /entrypoint.sh
     RUN chmod +x /entrypoint.sh

     CMD ["/entrypoint.sh"]

     9.2 supervisord.conf

     [supervisord]
     nodaemon=true

     [program:ollama]
     command=ollama serve
     autostart=true
     autorestart=true
     stdout_logfile=/dev/stdout
     stdout_logfile_maxbytes=0

     [program:fastapi]
     command=uvicorn app.main:app --host 0.0.0.0 --port 8000
     directory=/app
     autostart=true
     autorestart=true
     stdout_logfile=/dev/stdout
     stdout_logfile_maxbytes=0

     9.3 entrypoint.sh

     #!/bin/bash
     set -e

     # Start supervisord in background
     /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf &

     # Wait for Ollama to start
     echo "Waiting for Ollama to start..."
     until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
         sleep 2
     done

     # Pull model if not exists
     echo "Checking for Llama 3.1 8B model..."
     ollama pull llama3.1:8b

     echo "RFBooking FastAPI OSS is ready!"

     # Keep container running
     wait

     ---
     Phase 10: Documentation & License

     10.1 Files to Create

     - LICENSE - Full AGPLv3 text
     - README.md - Installation, configuration, usage
     - CONTRIBUTING.md - Contribution guidelines
     - docs/ - API documentation, deployment guide

     10.2 README.md Structure

     1. Project description
     2. Features
     3. Quick start (Docker)
     4. Configuration
     5. Development setup
     6. API reference
     7. License

     ---
     Implementation Order

     1. Project scaffold - Create directory structure, pyproject.toml, requirements.txt
     2. Configuration - Config file loading with Pydantic
     3. Database models - SQLAlchemy models and Alembic migrations
     4. Authentication - Magic links, tokens, middleware
     5. Core routes - Equipment, bookings with conflict detection
     6. Admin/Manager routes - User management, role-based access
     7. AI assistant - Ollama integration, specification rules
     8. Email service - Optional Resend integration
     9. Scheduler - APScheduler for cron jobs
     10. Frontend - Jinja2 templates, port dashboard.js
     11. Docker - Dockerfile, supervisor, entrypoint
     12. Documentation - README, LICENSE, docs

     ---
     Dependencies (requirements.txt)

     fastapi>=0.109.0
     uvicorn[standard]>=0.27.0
     sqlalchemy>=2.0.0
     alembic>=1.13.0
     pydantic>=2.0.0
     pydantic-settings>=2.0.0
     python-multipart>=0.0.6
     jinja2>=3.1.0
     aiofiles>=23.0.0
     httpx>=0.26.0
     ollama>=0.1.0
     resend>=0.7.0
     apscheduler>=3.10.0
     pyyaml>=6.0.0
     python-jose[cryptography]>=3.3.0
     passlib>=1.7.4

     ---
     Key Differences from rfbooking-core

     | Aspect             | rfbooking-core        | rfbooking-fastapi-oss  |
     |--------------------|-----------------------|------------------------|
     | Runtime            | Cloudflare Workers    | Docker + Uvicorn       |
     | Language           | JavaScript            | Python                 |
     | Database           | D1 (multi-tenant)     | SQLite (single-tenant) |
     | AI                 | Cloudflare Workers AI | Ollama (local)         |
     | Deployment         | Cloudflare            | Self-hosted Docker     |
     | Multi-tenancy      | Yes                   | No (single org)        |
     | Subscription tiers | Yes                   | No (unlimited)         |
     | License            | Proprietary           | AGPLv3                 |

     ---
     Estimated File Count

     - Python files: ~25
     - HTML templates: ~10
     - JavaScript: ~2
     - CSS: ~1
     - Config/Docker: ~8
     - Documentation: ~5