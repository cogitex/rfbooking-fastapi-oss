# RFBooking Setup Guide

Self-hosted Equipment Booking System with AI Assistant.
Online Demo version - www.rfbooking.com

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install Docker](#2-install-docker)
3. [Download and Start RFBooking](#3-download-and-start-rfbooking)
4. [Setup Wizard](#4-setup-wizard)
5. [First Login](#5-first-login)
6. [Verify Everything Works](#6-verify-everything-works)
7. [Manage Your Installation](#7-manage-your-installation)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Prerequisites

- A machine with at least **4 GB RAM** (8 GB recommended for AI features)
- **Docker** and **Docker Compose** installed
- A working **email service** (SMTP server or [Resend](https://resend.com) account) — required for passwordless login
- Network access on **port 8000** (configurable)

---

## 2. Install Docker

### Windows

1. Download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. Run the installer and follow the prompts
3. Restart your computer when prompted
4. Open Docker Desktop and wait for it to start (whale icon in the system tray turns steady)
5. Open **PowerShell** or **Command Prompt** and verify:
   ```
   docker --version
   docker compose version
   ```


### Linux (Ubuntu/Debian)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Add your user to the docker group (avoids needing sudo)
sudo usermod -aG docker $USER

# Log out and back in, then verify
docker --version
docker compose version
```

---

## 3. Start RFBooking

### Single Command Start

No files to download — everything is inside the Docker image. Just run:

```bash
docker run -d \
  --name rfbooking \
  -p 8000:8000 \
  -v rfbooking-data:/data \
  -v rfbooking-config:/app/config \
  -v rfbooking-ollama:/root/.ollama \
  --restart unless-stopped \
  olegtok/rfbooking:latest
```

**Windows (PowerShell):**
```powershell
docker run -d `
  --name rfbooking `
  -p 8000:8000 `
  -v rfbooking-data:/data `
  -v rfbooking-config:/app/config `
  -v rfbooking-ollama:/root/.ollama `
  --restart unless-stopped `
  olegtok/rfbooking:latest
```

This will:
- Pull the image from Docker Hub (first time only)
- Create named volumes for database, config, and AI model
- Auto-generate a default config on first run
- Start downloading the AI model (~4.7 GB) in the background (~5-10 min)

### Watch Startup Progress

```bash
docker logs -f rfbooking
```

Wait until you see:
```
============================================
  RFBooking FastAPI OSS is ready!
============================================

  Open in browser: http://localhost:8000

  First time? You will be redirected to the
  setup wizard to configure your installation.

============================================
```

Open your browser and go to **http://localhost:8000**

> **Note:** The first startup takes several minutes while the AI model downloads. Subsequent starts are fast since the model is cached.

### With NVIDIA GPU (Optional)

If you have an NVIDIA GPU and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) installed, add `--gpus all` for faster AI responses:

```bash
docker run -d \
  --name rfbooking \
  --gpus all \
  -p 8000:8000 \
  -v rfbooking-data:/data \
  -v rfbooking-config:/app/config \
  -v rfbooking-ollama:/root/.ollama \
  --restart unless-stopped \
  olegtok/rfbooking:latest
```

### Custom Port

To run on a different port (e.g., 9000):

```bash
docker run -d \
  --name rfbooking \
  -p 9000:8000 \
  -v rfbooking-data:/data \
  -v rfbooking-config:/app/config \
  -v rfbooking-ollama:/root/.ollama \
  --restart unless-stopped \
  olegtok/rfbooking:latest
```

Then access at `http://localhost:9000`.

---

## 4. Setup Wizard

On first visit, you will be automatically redirected to the **Setup Wizard** at `http://localhost:8000/setup`. The wizard has 3 steps:

### Step 1: Organization Settings

| Field | Description | Example |
|-------|-------------|---------|
| **Organization Name** | Your company or lab name (shown in emails and UI) | `Ampleon` |
| **Work Day Start** | Default start time for bookings | `08:00` |
| **Work Day End** | Default end time for bookings | `18:00` |

Click **Next** to continue.

### Step 2: Administrator Account

| Field | Description | Example |
|-------|-------------|---------|
| **Admin Email** | Your email address — used to log in | `admin@yourcompany.com` |
| **Admin Name** | Display name for the admin account | `John Smith` |

This email will receive the first magic link to log in. Make sure it is a real, accessible email address.

Click **Next** to continue.

### Step 3: Email Configuration

Email is **required** — RFBooking uses passwordless magic link authentication, so it needs to be able to send emails.

Choose one of two providers:

#### Option A: SMTP Server

Best for organizations with an existing mail server.

| Field | Description | Example |
|-------|-------------|---------|
| **From Email Address** | Sender address shown in emails | `booking@yourcompany.com` |
| **SMTP Host** | Your mail server hostname | `smtp.yourcompany.com` |
| **SMTP Port** | Server port (587 for TLS, 465 for SSL) | `587` |
| **SMTP Username** | Mail server username | `booking@yourcompany.com` |
| **SMTP Password** | Mail server password or app password | `••••••••` |
| **Use TLS** | Enable STARTTLS encryption (recommended) | Checked |

> **Warning:** Consumer email providers (Gmail, Outlook.com, Yahoo) have sending limits and may require app-specific passwords. They are not recommended for production use.

#### Option B: Resend API

Best for quick setup without managing an SMTP server. Free tier available at [resend.com](https://resend.com). Domain is needed.

| Field | Description | Example |
|-------|-------------|---------|
| **Resend API Key** | API key from your Resend dashboard | `re_xxxxxxxxx` |
| **From Email Address** | Must use a domain verified in Resend | `booking@yourverifieddomain.com` |

**Resend setup steps:**
1. Sign up at [resend.com](https://resend.com)
2. Add and verify your domain (requires DNS records)
3. Create an API key at [resend.com/api-keys](https://resend.com/api-keys)

### Test Your Email

Before saving, click **Test Email Configuration** to send a test email to the admin address. Verify it arrives in your inbox.

### Save Configuration

Click **Save & Start**. The system will:
- Save your configuration
- Create the admin account
- Restart the service
- Redirect you to the login page

---

## 5. First Login

1. On the login page (`http://localhost:8000/login`), enter your **admin email** address (the one from Step 2 of the wizard)

2. Optionally enter your name, then click **Send Magic Link**

3. Check your email inbox for a message from RFBooking with the subject "Your Login Link"

4. Click the **magic link** in the email — you will be logged in and redirected to the dashboard

5. Your session lasts **30 days**. After that, you simply request a new magic link.

> **If the email doesn't arrive:**
> - Check your spam/junk folder
> - Verify email settings in the setup wizard
> - If email delivery fails, the login page will display a **direct verification link** you can click to log in (useful for testing)

---

## 6. Verify Everything Works

Once logged in to the dashboard:

1. **Your Information** card shows your name, role (Admin), and organization
2. Navigate to **Equipment** to add your first piece of equipment
3. Navigate to **New Booking** to create a test booking
4. Check the **AI Assistant** tab — if the AI model finished downloading, you can ask equipment-related questions

---

## 7. Manage Your Installation

### Common Commands

```bash
# View logs
docker logs rfbooking

# Follow logs in real-time
docker logs -f rfbooking

# Stop the service
docker stop rfbooking

# Start the service
docker start rfbooking

# Restart the service
docker restart rfbooking

# Update to latest version
docker pull olegtok/rfbooking:latest
docker stop rfbooking
docker rm rfbooking
# Then run the same docker run command from Step 3
```

### Data Volumes

All data is stored in named Docker volumes and persists across container restarts and updates.

| Volume | Container Path | Contents |
|--------|----------------|----------|
| `rfbooking-data` | `/data/` | SQLite database (`rfbooking.db`) |
| `rfbooking-config` | `/app/config/` | Configuration (`config.yaml`) |
| `rfbooking-ollama` | `/root/.ollama/` | AI model files (~4.7 GB) |

### Backup

```bash
# Backup database
docker cp rfbooking:/data/rfbooking.db ./rfbooking.db.backup

# Backup configuration
docker cp rfbooking:/app/config/config.yaml ./config.yaml.backup
```

### Edit Configuration

```bash
# Copy config out, edit, copy back
docker cp rfbooking:/app/config/config.yaml ./config.yaml
# ... edit config.yaml with your text editor ...
docker cp ./config.yaml rfbooking:/app/config/config.yaml
docker restart rfbooking
```

---

## 8. Troubleshooting

### Container won't start

```bash
# Check logs for errors
docker logs rfbooking

# Verify Docker is running
docker info
```

### "Setup required" keeps appearing

The setup wizard wasn't completed. Visit `http://localhost:8000/setup` and complete all 3 steps.

### Magic link email not received

1. Check spam/junk folder
2. Verify email settings: look at `./config/config.yaml` under the `email:` section
3. Test email delivery:
   ```bash
   docker exec rfbooking curl -s http://localhost:8000/health
   ```
4. Check logs for SMTP errors:
   ```bash
   docker logs rfbooking | grep -i "smtp\|email\|error"
   ```

### AI assistant not responding

The AI model (~4.7 GB) may still be downloading. Check progress:
```bash
docker logs rfbooking | grep -i "ollama\|model\|pull"
```

### Port already in use

Another service is using port 8000. Stop the container and re-create it with a different port:
```bash
docker stop rfbooking && docker rm rfbooking
# Then run docker run with -p 8080:8000 instead of -p 8000:8000
```

---

## License

RFBooking FastAPI OSS is licensed under [AGPL-3.0-or-later](https://www.gnu.org/licenses/agpl-3.0.html).

Copyright (C) 2025 Oleg Tokmakov
