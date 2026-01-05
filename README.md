# RFBooking FastAPI OSS

Self-hosted Equipment Booking System with AI Assistant.

**Copyright (C) 2025 Oleg Tokmakov** | Licensed under [AGPLv3](https://www.gnu.org/licenses/agpl-3.0.html)

## Features

- **Equipment Management** - Track and organize laboratory equipment
- **Booking System** - Book equipment with conflict detection
- **AI Assistant** - Get intelligent equipment recommendations (Ollama + Llama 3.1 8B)
- **Role-Based Access** - Admin, Manager, and User roles
- **Email Notifications** - Optional email via Resend API
- **Self-Hosted** - Your data stays on your servers

## Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/otokmakov/rfbooking-fastapi-oss.git
cd rfbooking-fastapi-oss

# Copy and edit configuration
cp config/config.example.yaml config/config.yaml
# Edit config/config.yaml with your settings

# Start with Docker Compose
docker-compose up -d

# Access the application at http://localhost:8000
```

**Note:** On first startup, the container will download the Llama 3.1 8B model (~4.7GB).

## Configuration

Edit `config/config.yaml`:

```yaml
# Application settings
app:
  name: "RFBooking"
  secret_key: "your-secret-key-here"  # Change this!
  base_url: "http://localhost:8000"

# Admin user (created on first startup)
admin:
  email: "admin@example.com"
  name: "Administrator"

# Email (optional)
email:
  enabled: false  # Set to true and add API key to enable
  api_key: "your-resend-api-key"

# AI Assistant
ai:
  enabled: true
  model: "llama3.1:8b"
```

## Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy config
cp config/config.example.yaml config/config.yaml

# Run development server
python -m app.main
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Request magic link |
| `/api/auth/me` | GET | Get current user |
| `/api/equipment` | GET/POST | List/create equipment |
| `/api/bookings` | GET/POST | List/create bookings |
| `/api/ai/analyze` | POST | AI equipment recommendations |
| `/api/reports/booking-stats` | GET | Booking statistics |

## Project Structure

```
rfbooking-fastapi-oss/
├── app/
│   ├── main.py          # FastAPI application
│   ├── config.py        # Configuration
│   ├── database.py      # SQLite setup
│   ├── models/          # SQLAlchemy models
│   ├── routes/          # API endpoints
│   ├── services/        # Business logic
│   └── middleware/      # Auth middleware
├── templates/           # Jinja2 HTML templates
├── static/              # CSS/JS files
├── config/              # Configuration files
├── Dockerfile
└── docker-compose.yml
```

## License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0).

See [LICENSE](LICENSE) or https://www.gnu.org/licenses/agpl-3.0.html

## Author

**Oleg Tokmakov** - 2025
