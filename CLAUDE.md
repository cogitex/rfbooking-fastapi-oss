# RFBooking FastAPI OSS - Developer Reference

Self-hosted Equipment Booking System with AI Assistant.

**Copyright (C) 2025 Oleg Tokmakov** | **License: AGPL-3.0-or-later**

---

## Quick Start

### Docker (Recommended)

```bash
# 1. Create installation directory and download docker-compose.yml
mkdir rfbooking && cd rfbooking
curl -O https://raw.githubusercontent.com/yourrepo/rfbooking-fastapi-oss/main/docker-compose.yml

# 2. Start container (first run downloads AI model ~4.7GB)
docker-compose up -d

# 3. Open browser - you'll be redirected to setup wizard
open http://localhost:8000
```

### Windows (Docker Desktop)

1. Create folder: `C:\rfbooking`
2. Download `docker-compose.yml` to that folder
3. Right-click → Open with Docker Desktop, or run `docker-compose up -d`
4. Open http://localhost:8000 - complete setup wizard

### Development

```bash
cp config/config.example.yaml config/config.yaml
pip install -r requirements.txt
python -m app.main
```

---

## Project Structure

```
rfbooking-fastapi-oss/
├── app/
│   ├── __init__.py              # Package init, version
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Pydantic settings
│   ├── database.py              # SQLAlchemy setup
│   ├── models/
│   │   ├── __init__.py          # Model exports
│   │   ├── user.py              # User, Role models
│   │   ├── auth.py              # AuthToken, MagicLink, CronJob, NotificationLog
│   │   ├── equipment.py         # Equipment, EquipmentType, AI models
│   │   └── booking.py           # Booking model
│   ├── routes/
│   │   ├── __init__.py          # Router setup
│   │   ├── auth.py              # /api/auth/* endpoints
│   │   ├── equipment.py         # /api/equipment/* endpoints
│   │   ├── bookings.py          # /api/bookings/* endpoints
│   │   ├── admin.py             # /api/admin/* endpoints
│   │   ├── manager.py           # /api/manager/* endpoints
│   │   ├── reports.py           # /api/reports/* endpoints
│   │   ├── ai_assistant.py      # /api/ai/* endpoints
│   │   ├── setup.py             # /api/setup/* endpoints (initial config)
│   │   └── pages.py             # HTML page routes
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_service.py        # Ollama integration
│   │   ├── email.py             # Email (SMTP or Resend)
│   │   ├── notifications.py     # Notification queue
│   │   └── scheduler.py         # APScheduler cron jobs
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── auth.py              # Auth dependencies, CSRF
│   └── utils/
│       ├── __init__.py
│       └── helpers.py           # Utility functions
├── templates/                   # Jinja2 templates
│   ├── base.html
│   ├── index.html               # Landing page
│   ├── login.html               # Login form
│   ├── dashboard.html           # Main dashboard
│   └── setup.html               # Setup/installation guide
├── static/
│   ├── css/styles.css
│   └── js/dashboard.js
├── config/
│   └── config.example.yaml      # Example configuration
├── scripts/
│   ├── entrypoint.sh            # Docker entrypoint
│   └── init_db.py               # DB initialization script
├── Dockerfile
├── docker-compose.yml
├── supervisord.conf
├── requirements.txt
├── pyproject.toml
├── rfbctl.sh                    # Linux/Mac management script
├── rfbctl.bat                   # Windows management script
├── LICENSE                      # AGPL-3.0
└── README.md
```

---

## Database Schema (SQLite)

### Core Tables

#### `roles`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | 1=admin, 2=manager, 3=user |
| name | TEXT UNIQUE | Role name |
| description | TEXT | Description |

#### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| email | TEXT UNIQUE | User email |
| name | TEXT | Display name |
| role_id | INTEGER FK | References roles(id) |
| is_active | BOOLEAN | Default TRUE |
| email_notifications_enabled | BOOLEAN | Default TRUE |
| created_at | DATETIME | Creation timestamp |
| last_login_at | DATETIME | Last login |

#### `auth_tokens`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | References users(id) CASCADE |
| token | TEXT UNIQUE | Session token |
| expires_at | DATETIME | Expiration (30 days) |
| created_at | DATETIME | Creation timestamp |
| last_used_at | DATETIME | Last access |
| ip_address | TEXT | Client IP |
| user_agent | TEXT | Browser info |
| is_revoked | BOOLEAN | Revocation flag |

#### `magic_links`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| email | TEXT | Target email |
| name | TEXT | User name |
| token | TEXT UNIQUE | One-time token |
| expires_at | DATETIME | Expiration (15 min) |
| used | BOOLEAN | Usage flag |
| used_at | DATETIME | When used |
| created_at | DATETIME | Creation timestamp |
| ip_address | TEXT | Source IP |
| user_id | INTEGER FK | References users(id) |

### Equipment Tables

#### `equipment_types`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| name | TEXT UNIQUE | Type name |
| description | TEXT | Description |
| is_active | BOOLEAN | Soft delete flag |
| manager_notifications_enabled | BOOLEAN | Default TRUE |
| created_at | DATETIME | Creation timestamp |

#### `equipment`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| name | TEXT | Equipment name |
| description | TEXT | Technical specs |
| location | TEXT | Physical location |
| type_id | INTEGER FK | References equipment_types(id) |
| next_calibration_date | DATE | Calibration due date |
| is_active | BOOLEAN | Soft delete flag |
| created_at | DATETIME | Creation timestamp |

#### `equipment_type_users`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| type_id | INTEGER FK | References equipment_types(id) CASCADE |
| user_id | INTEGER FK | References users(id) CASCADE |
| granted_at | DATETIME | When access granted |
| granted_by | INTEGER FK | Who granted access |
| UNIQUE(type_id, user_id) | | Prevent duplicates |

#### `equipment_managers`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| equipment_id | INTEGER FK | References equipment(id) CASCADE |
| manager_id | INTEGER FK | References users(id) CASCADE |
| assigned_at | DATETIME | Assignment time |
| assigned_by | INTEGER FK | Who assigned |
| UNIQUE(equipment_id, manager_id) | | Prevent duplicates |

### Booking Tables

#### `bookings`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | References users(id) CASCADE |
| equipment_id | INTEGER FK | References equipment(id) CASCADE |
| start_date | DATE | Booking start |
| end_date | DATE | Booking end |
| start_time | TIME | Start time |
| end_time | TIME | End time |
| description | TEXT | Purpose (max 10KB) |
| status | TEXT | 'active', 'cancelled', 'completed' |
| created_at | DATETIME | Creation timestamp |
| updated_at | DATETIME | Last update |

### System Tables

#### `cron_jobs`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| job_key | TEXT UNIQUE | Job identifier |
| job_name | TEXT | Display name |
| description | TEXT | What job does |
| cron_schedule | TEXT | Cron expression |
| is_enabled | BOOLEAN | Enable/disable |
| last_run_at | DATETIME | Last execution |
| last_run_status | TEXT | success/error/skipped |
| last_run_duration_ms | INTEGER | Execution time |
| total_runs | INTEGER | Success count |
| total_errors | INTEGER | Error count |

#### `notification_log`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| notification_type | TEXT | Type of notification |
| recipient_user_id | INTEGER FK | References users(id) |
| reference_id | INTEGER | booking_id or equipment_id |
| reference_type | TEXT | 'booking' or 'equipment' |
| scheduled_for | DATETIME | When to send |
| sent_at | DATETIME | When sent |
| status | TEXT | pending/sent/failed/skipped |
| error_message | TEXT | Error details |
| send_attempts | INTEGER | Retry count |

### AI Tables

#### `ai_usage`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| date | DATE UNIQUE | Aggregation date |
| queries_count | INTEGER | Number of queries |
| input_tokens | INTEGER | Input token count |
| output_tokens | INTEGER | Output token count |

#### `ai_query_log`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | References users(id) |
| prompt | TEXT | User prompt |
| response | TEXT | AI response |
| input_tokens | INTEGER | Input tokens |
| output_tokens | INTEGER | Output tokens |
| model | TEXT | Model name |
| success | BOOLEAN | Success flag |
| error_message | TEXT | Error if failed |
| created_at | DATETIME | Query timestamp |

#### `ai_specification_rules`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| rule_type | TEXT | 'general', 'parameter', 'example' |
| parameter_name | TEXT | 'frequency', 'power', 'temperature', etc. |
| parameter_unit | TEXT | 'GHz', 'W', '°C', etc. |
| is_enabled | BOOLEAN | Enable/disable |
| prompt_text | TEXT | Prompt for AI |
| user_prompt_patterns | TEXT | JSON regex patterns |
| equipment_patterns | TEXT | JSON regex patterns |
| display_order | INTEGER | Sort order |
| UNIQUE(rule_type, parameter_name) | | Prevent duplicates |

---

## API Reference

### Authentication

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/register` | POST | No | Request magic link |
| `/api/auth/verify` | GET | No | Verify magic link, create session |
| `/api/auth/validate` | GET | No | Check session validity |
| `/api/auth/me` | GET | Yes | Get current user info |
| `/api/auth/logout` | POST | Yes | Revoke session |

### Setup (Initial Configuration)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/setup/status` | GET | No | Check if setup is required |
| `/api/setup/configure` | POST | No* | Save initial configuration |
| `/api/setup/test-email` | POST | No* | Test email settings |

*Only available when system is not yet configured (`setup_completed: false`)

### Equipment

| Endpoint | Method | Auth | Role | Description |
|----------|--------|------|------|-------------|
| `/api/equipment` | GET | Yes | All | List equipment |
| `/api/equipment` | POST | Yes | Admin | Create equipment |
| `/api/equipment/{id}` | GET | Yes | All | Get equipment details |
| `/api/equipment/{id}` | PUT | Yes | Admin | Update equipment |
| `/api/equipment/{id}` | DELETE | Yes | Admin | Deactivate equipment |
| `/api/admin/equipment-types` | GET | Yes | All | List equipment types |
| `/api/admin/equipment-types` | POST | Yes | Admin | Create type |
| `/api/admin/equipment/{id}/managers` | GET/POST/DELETE | Yes | Admin | Manage equipment managers |
| `/api/equipment-types/{id}/users/{userId}/grant` | POST | Yes | Manager | Grant type access |
| `/api/equipment-types/{id}/users/{userId}/revoke` | DELETE | Yes | Manager | Revoke type access |

### Bookings

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/bookings` | GET | Yes | List bookings (filters: equipment_id, user_id, dates) |
| `/api/bookings` | POST | Yes | Create booking with conflict detection |
| `/api/bookings/{id}` | GET | Yes | Get booking details |
| `/api/bookings/{id}` | PUT | Yes | Update booking |
| `/api/bookings/{id}` | DELETE | Yes | Cancel booking |
| `/api/bookings/{id}/description` | PATCH | Yes | Update description only |

### Admin

| Endpoint | Method | Auth | Role | Description |
|----------|--------|------|------|-------------|
| `/api/admin/users` | GET | Yes | Manager | List all users |
| `/api/admin/users/{id}/role` | PUT | Yes | Admin | Change user role |
| `/api/admin/users/{id}/status` | PUT | Yes | Admin | Activate/deactivate user |
| `/api/admin/tokens/delete-old` | POST | Yes | Admin | Cleanup old tokens |
| `/api/admin/cron-jobs` | GET | Yes | Admin | List cron jobs |
| `/api/admin/cron-jobs/{id}` | PUT | Yes | Admin | Update cron job |
| `/api/admin/cron-jobs/{id}/trigger` | POST | Yes | Admin | Trigger cron job |
| `/api/admin/ai-specification-rules` | GET/POST | Yes | Admin | Manage AI rules |
| `/api/admin/ai-specification-rules/{id}` | PATCH/DELETE | Yes | Admin | Update/delete AI rule |

### Manager

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/manager/equipment` | GET | Yes | List managed equipment |
| `/api/manager/equipment/{id}/bookings` | GET | Yes | List bookings for equipment |
| `/api/manager/bookings/{id}` | PUT | Yes | Update booking |
| `/api/manager/bookings/{id}` | DELETE | Yes | Cancel booking |
| `/api/manager/controlled-types` | GET | Yes | List types where user is manager |

### Reports

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/reports/equipment-usage` | GET | Yes | Equipment usage statistics |
| `/api/reports/user-activity` | GET | Yes | User booking activity |
| `/api/reports/booking-stats` | GET | Yes | Overall booking statistics |

### AI Assistant

| Endpoint | Method | Auth | Role | Description |
|----------|--------|------|------|-------------|
| `/api/ai/analyze` | POST | Yes | All | Get equipment recommendations |
| `/api/ai/chat` | POST | Yes | Admin | Direct AI chat |
| `/api/ai/usage` | GET | Yes | Admin | AI usage statistics |

### Pages (HTML)

| Route | Auth | Description |
|-------|------|-------------|
| `/` | No | Landing page |
| `/login` | No | Login form |
| `/dashboard` | Yes | Main dashboard |
| `/bookings` | Yes | Bookings tab |
| `/equipment` | Yes | Equipment tab |
| `/reports` | Yes | Reports tab |
| `/admin` | Yes (Admin) | Admin panel |
| `/ai-assistant` | Yes | AI assistant |
| `/setup` | No | Setup guide & downloads |
| `/setup/download/{file}` | No | Download setup files |

---

## Configuration

### config/config.yaml

```yaml
# ============================================================================
# REQUIRED SETTINGS - You MUST change these before first use
# ============================================================================

organization:
  name: "My Organization"            # CHANGE: Your company name
  work_day_start: "08:00"
  work_day_end: "18:00"

admin:
  email: "admin@example.com"         # CHANGE: Your administrator email
  name: "Administrator"

email:
  enabled: false                     # CHANGE: Set to true
  provider: "smtp"                   # "smtp" or "resend"
  from_address: "noreply@example.com"
  from_name: "RFBooking System"
  smtp_host: "smtp.example.com"      # CHANGE: Your SMTP server
  smtp_port: 587
  smtp_username: ""
  smtp_password: ""
  smtp_use_tls: true
  smtp_use_ssl: false
  api_key: ""                        # For Resend provider

# ============================================================================
# AUTOMATIC SETTINGS - Usually auto-configured by rfbctl.sh
# ============================================================================

app:
  name: "RFBooking"
  debug: false
  host: "0.0.0.0"
  port: 8000
  base_url: "http://localhost:8000"  # Auto-detected by rfbctl.sh init

database:
  path: "/data/rfbooking.db"

# ============================================================================
# OPTIONAL SETTINGS - Defaults work for most installations
# ============================================================================

ai:
  enabled: true
  model: "llama3.1:8b"
  ollama_host: "http://localhost:11434"
  max_tokens: 800
  temperature: 0.1

security:
  auth_token_days: 30
  magic_link_minutes: 15
  max_tokens_per_user: 10
  csrf_enabled: true

rate_limit:
  max_bookings_per_user_per_day: 20
  max_ai_requests_per_5min: 10

booking:
  max_duration_days: 30
  max_description_length: 10240
  reminder_hours: 24
  calibration_reminder_days: 7

cleanup:
  auth_token_retention_days: 7
  magic_link_retention_days: 7
  ai_query_log_retention_days: 7
  notification_log_retention_days: 30
```

---

## Role Hierarchy

```
admin (role_id=1) > manager (role_id=2) > user (role_id=3)
```

| Role | Permissions |
|------|-------------|
| **Admin** | Full access, user management, settings, AI rules |
| **Manager** | Manage assigned equipment, view all bookings, grant type access |
| **User** | Create/view own bookings, view accessible equipment |

---

## Cron Jobs

| Job Key | Schedule | Description |
|---------|----------|-------------|
| `daily_notifications` | 0 8 * * * | Send booking/calibration reminders |
| `daily_cleanup` | 0 8 * * * | Clean expired tokens, old logs |
| `weekly_manager_reports` | 0 9 * * 5 | Friday manager reports |

---

## Docker Deployment

### Single Command
```bash
docker-compose up -d
```

### Architecture
```
┌─────────────────────────────────────────┐
│         Docker Container                │
│  ┌─────────────┐   ┌─────────────────┐  │
│  │   FastAPI   │──▶│     Ollama      │  │
│  │   :8000     │   │   llama3.1:8b   │  │
│  └─────────────┘   └─────────────────┘  │
│         │                   │           │
│         ▼                   ▼           │
│  ┌─────────────┐   ┌─────────────────┐  │
│  │   SQLite    │   │  Model Storage  │  │
│  │   /data/    │   │  ~/.ollama/     │  │
│  └─────────────┘   └─────────────────┘  │
└─────────────────────────────────────────┘
        Port: 8000
```

### Volumes
- `/data` - SQLite database
- `/app/config` - Configuration file
- `ollama-data` - AI model storage

---

## Security Features

- **Passwordless Auth**: Magic links (no passwords stored)
- **HTTP-only Cookies**: Tokens not accessible to JavaScript
- **CSRF Protection**: Double submit cookie pattern
- **Input Sanitization**: HTML escape, length limits
- **Rate Limiting**: Daily booking limits, AI request limits
- **Role-Based Access**: Admin/Manager/User hierarchy
- **Type-Based Equipment Access**: Users access equipment by type

---

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python -m app.main

# Initialize database manually
python scripts/init_db.py

# Build Docker image
docker build -t rfbooking .

# Run with Docker
docker run -p 8000:8000 -v $(pwd)/data:/data rfbooking
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Web Framework | FastAPI |
| Database | SQLite + SQLAlchemy |
| Templates | Jinja2 |
| Styling | Tailwind CSS |
| AI | Ollama + Llama 3.1 8B |
| Email | Resend API (optional) |
| Scheduler | APScheduler |
| Container | Docker + Supervisor |

---

## File Metrics

- **Python files**: 22
- **Total Python lines**: ~5,960
- **HTML templates**: 4
- **Configuration files**: 5
- **Docker files**: 3

---

## License

GNU Affero General Public License v3.0 (AGPL-3.0-or-later)

Copyright (C) 2025 Oleg Tokmakov

https://www.gnu.org/licenses/agpl-3.0.html
