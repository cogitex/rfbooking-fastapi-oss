# RFBooking FastAPI OSS

Self-hosted equipment booking system with AI assistant for engineering teams and laboratories.

**Copyright (C) 2025 Oleg Tokmakov** | Licensed under [AGPL-3.0-or-later](https://www.gnu.org/licenses/agpl-3.0.html)

## Documentation

- [Installation Guide](docs/SETUP_GUIDE.md) - most up-to-date installation instructions
- [Production Deployment](docs/DEPLOYMENT.md) - reverse proxy, TLS, backup, monitoring
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Source Code](https://github.com/cogitex/rfbooking-fastapi-oss)

## Features

- Equipment inventory with types, managers, and calibration tracking
- Booking workflow with conflict detection and role-based access
- AI assistant powered by Ollama for equipment recommendations
- Passwordless magic-link authentication
- Email notifications for bookings, reminders, and reports
- Self-hosted deployment with Docker and SQLite

## Quick Start

For most users, use the full [Installation Guide](docs/SETUP_GUIDE.md).

### Docker Compose

```bash
mkdir rfbooking && cd rfbooking
curl -O https://raw.githubusercontent.com/cogitex/rfbooking-fastapi-oss/main/docker-compose.yml
docker compose up -d
```

Then open `http://localhost:8000` and complete the setup wizard.

### From Repository

```bash
git clone https://github.com/cogitex/rfbooking-fastapi-oss.git
cd rfbooking-fastapi-oss
docker compose up -d
```

## First Start

- On the first launch the container creates the config and data directories automatically.
- Open `http://localhost:8000` and finish the web-based setup wizard.
- The default Ollama model is downloaded on first start, so the first boot can take several minutes.

## Development

```bash
git clone https://github.com/cogitex/rfbooking-fastapi-oss.git
cd rfbooking-fastapi-oss
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp config/config.example.yaml config/config.yaml
python -m app.main
```

For local debugging with Docker, `docker-compose.yml` includes commented bind mounts for `./app`, `./templates`, and `./static`. Uncomment them when you want live code or template reloads without rebuilding the image.

## License

RFBooking application code is licensed under **AGPL-3.0-or-later**.

See [LICENSE](LICENSE) for the full license text. Third-party components and AI models may have separate license terms.
