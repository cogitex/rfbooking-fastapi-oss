# RFBooking Setup Implementation Plan

## Overview

Implement a cross-platform, web-based installation and configuration flow that works identically on Windows and Linux with minimal command-line interaction.

## Target User Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  CROSS-PLATFORM INSTALLATION FLOW                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User creates installation folder:                          │
│     Windows: C:\rfbooking\                                      │
│     Linux:   ~/rfbooking/                                       │
│                                                                 │
│  2. User downloads docker-compose.yml to that folder            │
│     (from GitHub releases or documentation site)               │
│                                                                 │
│  3. User runs container:                                        │
│     Windows: Docker Desktop GUI (open/import compose file)     │
│     Linux:   docker-compose up -d                               │
│                                                                 │
│  4. Container auto-creates:                                     │
│     ./data/           (database directory)                     │
│     ./config/         (configuration directory)                │
│                                                                 │
│  5. User visits http://localhost:8000                          │
│     └─► Redirected to /setup (first-run detected)              │
│     └─► Web wizard: org name, admin email, SMTP settings       │
│     └─► Click "Save & Apply"                                   │
│                                                                 │
│  6. System ready! Redirected to login page.                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration Ownership

| Setting | Configured By | When |
|---------|---------------|------|
| Database location | docker-compose.yml placement | Before container start |
| Config file location | docker-compose.yml placement | Before container start |
| Organization name | Web UI | After container start |
| Admin email | Web UI | After container start |
| SMTP settings | Web UI | After container start |
| AI settings | Web UI | After container start |

---

## Implementation Phases

### Phase 1: First-Run Detection & Redirect
- [x] Add `setup_completed` flag to AppConfig in config.py
- [x] Add `needs_setup` property to Settings class
- [x] Add `save_config()` and `update_settings()` functions
- [x] Redirect `/` and `/login` to `/setup` if not configured
- [x] Pass `needs_setup` and `current_config` to setup template
- [x] Update config.example.yaml with `setup_completed: false`

**Status**: COMPLETED

---

### Phase 2: Setup Wizard UI
- [x] Redesign /setup page as multi-step wizard
- [x] Step 1: Organization settings (name, work hours)
- [x] Step 2: Admin account (email, name)
- [x] Step 3: Email/SMTP configuration with test button
- [x] Add form validation (client-side)
- [x] Show "Setup Complete" page when already configured
- [x] Add download links for rfbctl.sh and rfbctl.bat

**Status**: COMPLETED

---

### Phase 3: Configuration API Endpoints
- [x] `POST /api/setup/configure` - Save configuration
- [x] `POST /api/setup/test-email` - Test SMTP settings
- [x] `GET /api/setup/status` - Check if configured
- [x] Add validation (server-side)
- [x] Security: Only allow setup API when not yet configured
- [x] Add `send_email_direct()` function for testing email config
- [x] Register setup router in routes/__init__.py

**Status**: COMPLETED

---

### Phase 4: Graceful Restart Mechanism
- [x] Use supervisorctl restart from within container (in setup.py)
- [x] Show "Restarting..." UI feedback in setup wizard
- [x] Auto-redirect to login after restart (3 second delay)
- [x] Graceful fallback for dev environment (no supervisorctl)

**Status**: COMPLETED

---

### Phase 5: Windows Support (rfbctl.bat)
- [x] Create rfbctl.bat with interactive menu interface
- [x] Commands: start, stop, restart, status, logs, browser, backup
- [x] Works with Docker Desktop
- [x] Added to download endpoint in pages.py
- [x] Added download link in setup.html

**Status**: COMPLETED

---

### Phase 6: Docker Compose Improvements
- [x] Add environment variable support for custom paths (RFBOOKING_DATA, RFBOOKING_CONFIG_DIR, RFBOOKING_PORT)
- [x] Update docker-compose.yml with helpful comments
- [x] Ensure data/config directories created in entrypoint.sh
- [x] Update entrypoint messages for setup wizard flow

**Status**: COMPLETED

---

### Phase 7: Documentation & Polish
- [x] Update CLAUDE.md with new Quick Start section
- [x] Add Setup API to API Reference in CLAUDE.md
- [x] Update project structure in CLAUDE.md
- [ ] Test complete flow on fresh Windows install
- [ ] Test complete flow on fresh Linux install

**Status**: COMPLETED (pending testing)

---

## Progress Log

| Date | Phase | Status | Notes |
|------|-------|--------|-------|
| 2026-01-07 | Phase 1 | DONE | Added setup_completed flag, needs_setup property, redirects |
| 2026-01-07 | Phase 2 | DONE | Created 3-step setup wizard UI with validation |
| 2026-01-07 | Phase 3 | DONE | Created /api/setup/* endpoints, email testing |
| 2026-01-07 | Phase 4 | DONE | Restart via supervisorctl, UI feedback |
| 2026-01-07 | Phase 5 | DONE | Created rfbctl.bat with interactive menu |
| 2026-01-07 | Phase 6 | DONE | Added env var support for paths in docker-compose.yml |
| 2026-01-07 | Phase 7 | DONE | Updated CLAUDE.md documentation |

---

## Technical Notes

### First-Run Detection Strategy
Check if config.yaml has been customized:
- Option A: Check for `_setup_completed: true` flag
- Option B: Check if admin.email != "admin@example.com"
- Option C: Check for `.setup_complete` marker file in /data

Recommended: Option A - explicit flag in config

### Restart Mechanism Options
1. **supervisorctl** - `docker exec rfbooking supervisorctl restart fastapi`
2. **Touch file** - Watch for `/tmp/restart-fastapi` file
3. **API signal** - Internal endpoint that calls os.kill()

Recommended: supervisorctl via subprocess from Python

### Security Considerations
- Setup API endpoints only work when `_setup_completed: false`
- After setup complete, /setup shows "Already configured" message
- No authentication required for initial setup (container is fresh)
- CSRF protection still applies
