# Production Deployment Guide

RFBooking FastAPI OSS - Self-hosted Equipment Booking System

---

## Table of Contents

1. [Requirements](#requirements)
2. [Docker Deployment (Recommended)](#docker-deployment-recommended)
3. [Manual Deployment](#manual-deployment)
4. [Reverse Proxy Setup](#reverse-proxy-setup)
5. [SSL/TLS Configuration](#ssltls-configuration)
6. [Environment Variables](#environment-variables)
7. [Backup & Restore](#backup--restore)
8. [Monitoring](#monitoring)
9. [Updating](#updating)
10. [Troubleshooting](#troubleshooting)

---

## Requirements

### Hardware (Minimum)
| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 8 GB | 16 GB |
| Storage | 20 GB | 50 GB+ |
| GPU | Not required | NVIDIA GPU (faster AI) |

> **Note:** The Llama 3.1 8B model requires ~5GB disk space and ~6GB RAM during inference.

### Software
- Docker 20.10+ and Docker Compose 2.0+
- OR Python 3.10+ with Ollama installed
- Linux (Ubuntu 22.04 LTS recommended)

---

## Docker Deployment (Recommended)

### Step 1: Clone Repository

```bash
git clone https://github.com/otokmakov/rfbooking-fastapi-oss.git
cd rfbooking-fastapi-oss
```

### Step 2: Configure

```bash
# Create configuration
cp config/config.example.yaml config/config.yaml

# Edit configuration
nano config/config.yaml
```

**Important settings to change:**

```yaml
app:
  secret_key: "generate-a-random-32-char-string"  # REQUIRED: Change this!
  base_url: "https://booking.yourdomain.com"      # Your public URL

admin:
  email: "admin@yourdomain.com"                   # Admin email
  name: "Your Name"

organization:
  name: "Your Organization"

email:
  enabled: true                                    # Enable for production
  api_key: "re_xxxxxxxxxxxx"                      # Resend API key
  from_address: "booking@yourdomain.com"
```

### Step 3: Create Data Directory

```bash
mkdir -p data
chmod 755 data
```

### Step 4: Start Services

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# First startup takes 5-10 minutes (downloading AI model)
```

### Step 5: Verify

```bash
# Check health
curl http://localhost:8000/health

# Expected: {"status":"healthy","version":"1.0.0"}
```

---

## Manual Deployment

### Step 1: Install Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip curl

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama
systemctl enable ollama
systemctl start ollama

# Pull model
ollama pull llama3.1:8b
```

### Step 2: Setup Application

```bash
# Clone repository
git clone https://github.com/otokmakov/rfbooking-fastapi-oss.git
cd rfbooking-fastapi-oss

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp config/config.example.yaml config/config.yaml
nano config/config.yaml
```

### Step 3: Create Systemd Service

```bash
sudo nano /etc/systemd/system/rfbooking.service
```

```ini
[Unit]
Description=RFBooking FastAPI OSS
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/rfbooking-fastapi-oss
Environment="PATH=/opt/rfbooking-fastapi-oss/venv/bin"
Environment="RFBOOKING_CONFIG=/opt/rfbooking-fastapi-oss/config/config.yaml"
ExecStart=/opt/rfbooking-fastapi-oss/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable rfbooking
sudo systemctl start rfbooking
```

---

## Reverse Proxy Setup

### Nginx

```bash
sudo apt install nginx
sudo nano /etc/nginx/sites-available/rfbooking
```

```nginx
server {
    listen 80;
    server_name booking.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name booking.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/booking.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/booking.yourdomain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Proxy settings
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Static files (optional optimization)
    location /static/ {
        alias /opt/rfbooking-fastapi-oss/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/rfbooking /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Caddy (Alternative)

```bash
# /etc/caddy/Caddyfile
booking.yourdomain.com {
    reverse_proxy localhost:8000
}
```

---

## SSL/TLS Configuration

### Let's Encrypt (Certbot)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d booking.yourdomain.com

# Auto-renewal (already configured by certbot)
sudo systemctl status certbot.timer
```

### Self-Signed (Development Only)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/rfbooking.key \
    -out /etc/ssl/certs/rfbooking.crt
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RFBOOKING_CONFIG` | Path to config file | `config/config.yaml` |
| `OLLAMA_HOST` | Ollama API URL (override config) | From config |

### Docker Compose Override

```yaml
# docker-compose.override.yml
version: '3.8'
services:
  rfbooking:
    environment:
      - RFBOOKING_CONFIG=/app/config/config.yaml
    ports:
      - "127.0.0.1:8000:8000"  # Bind to localhost only
```

---

## Backup & Restore

### Backup

```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/backups/rfbooking"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
cp /path/to/data/rfbooking.db "$BACKUP_DIR/rfbooking_$DATE.db"

# Backup config
cp /path/to/config/config.yaml "$BACKUP_DIR/config_$DATE.yaml"

# Compress
tar -czf "$BACKUP_DIR/rfbooking_$DATE.tar.gz" \
    "$BACKUP_DIR/rfbooking_$DATE.db" \
    "$BACKUP_DIR/config_$DATE.yaml"

# Cleanup individual files
rm "$BACKUP_DIR/rfbooking_$DATE.db" "$BACKUP_DIR/config_$DATE.yaml"

# Keep last 30 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup complete: rfbooking_$DATE.tar.gz"
```

```bash
# Add to crontab (daily at 2 AM)
0 2 * * * /opt/rfbooking-fastapi-oss/scripts/backup.sh
```

### Restore

```bash
# Stop service
docker-compose down
# OR: sudo systemctl stop rfbooking

# Extract backup
tar -xzf rfbooking_20250101_020000.tar.gz

# Restore files
cp rfbooking_20250101_020000.db /path/to/data/rfbooking.db
cp config_20250101_020000.yaml /path/to/config/config.yaml

# Start service
docker-compose up -d
# OR: sudo systemctl start rfbooking
```

---

## Monitoring

### Health Check Endpoint

```bash
# Simple check
curl -s http://localhost:8000/health | jq

# With alerting (example with curl + Slack)
#!/bin/bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$STATUS" != "200" ]; then
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"RFBooking is DOWN!"}' \
        YOUR_SLACK_WEBHOOK_URL
fi
```

### Docker Health

```bash
# Check container status
docker-compose ps

# View resource usage
docker stats rfbooking
```

### Log Monitoring

```bash
# Docker logs
docker-compose logs -f --tail=100

# Systemd logs
journalctl -u rfbooking -f
```

### Prometheus Metrics (Optional)

Add to `requirements.txt`:
```
prometheus-fastapi-instrumentator
```

Add to `app/main.py`:
```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

Access metrics at `/metrics`.

---

## Updating

### Docker Update

```bash
cd /path/to/rfbooking-fastapi-oss

# Backup first
./scripts/backup.sh

# Pull latest
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Verify
curl http://localhost:8000/health
```

### Manual Update

```bash
# Backup first
./scripts/backup.sh

# Stop service
sudo systemctl stop rfbooking

# Pull latest
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Start service
sudo systemctl start rfbooking
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs rfbooking

# Common issues:
# - Port 8000 already in use
# - Config file missing
# - Ollama model download failed
```

### AI Not Working

```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Pull model manually
docker exec -it rfbooking ollama pull llama3.1:8b
```

### Database Errors

```bash
# Check database file permissions
ls -la /path/to/data/

# Reset database (WARNING: deletes all data)
rm /path/to/data/rfbooking.db
docker-compose restart
```

### Email Not Sending

1. Check `email.enabled: true` in config
2. Verify Resend API key is correct
3. Check from_address domain is verified in Resend
4. View logs for email errors

### High Memory Usage

```bash
# Restart to clear memory
docker-compose restart

# Consider limiting Ollama memory
# Add to docker-compose.yml:
#   deploy:
#     resources:
#       limits:
#         memory: 8G
```

### Slow AI Responses

- Normal: 5-30 seconds depending on hardware
- GPU acceleration: Add NVIDIA Container Toolkit
- Consider smaller model: `llama3.2:3b` (less accurate)

---

## Security Checklist

- [ ] Changed default `secret_key` in config
- [ ] Using HTTPS with valid certificate
- [ ] Firewall configured (only 80/443 exposed)
- [ ] Regular backups configured
- [ ] Admin email is correct
- [ ] Resend domain verified (if using email)
- [ ] Log monitoring in place

---

## Support

- **Issues:** https://github.com/otokmakov/rfbooking-fastapi-oss/issues
- **License:** AGPL-3.0-or-later

Copyright (C) 2025 Oleg Tokmakov
