# RFBooking FastAPI OSS - Improvement Plan

**Source:** Ported from rfbooking-core (Cloudflare Workers multi-tenant)
**Target:** rfbooking-fastapi-oss (FastAPI single-tenant, Docker-based)
**Created:** 2025-01-07
**Last Updated:** 2025-01-07

---

## Overview

This document tracks the implementation of missing features from rfbooking-core to rfbooking-fastapi-oss. The FastAPI OSS version is a single-tenant implementation designed for self-hosted Docker deployment.

### Legend
- [ ] Not started
- [x] Completed
- [~] In progress
- [N/A] Not applicable (multi-tenant only)

---

## Feature Comparison Summary

| Category | Core Features | OSS Implemented | Missing |
|----------|---------------|-----------------|---------|
| Authentication | 7 | 4 | 3 |
| User Management | 6 | 4 | 2 |
| Equipment | 6 | 6 | 0 |
| Bookings | 6 | 5 | 1 |
| Notifications | 8 | 4 | 4 |
| AI Assistant | 6 | 3 | 3 |
| Reports | 4 | 3 | 1 |
| Admin | 5 | 3 | 2 |
| UI/UX | 8 | 4 | 4 |
| **Total** | **56** | **36** | **20** |

---

## Phase 1: Critical Missing Features

### 1.1 Registration Settings (Email Allowlist)
- **Status:** [x] Completed (2025-01-07)
- **Priority:** High
- **Effort:** Medium
- **Description:** Add ability to restrict registration to specific email addresses or domains

**Requirements:**
- [x] Add `registration_settings` table (mode: open/restricted, allowed_domains)
- [x] Add `allowed_emails` table (email, added_by, added_at)
- [x] API: GET/PUT /api/admin/registration-settings
- [x] API: GET/POST/DELETE /api/admin/registration/allowed-emails
- [x] API: POST /api/admin/registration/allowed-emails/import (bulk)
- [x] Update auth/register to check allowlist when restricted mode
- [ ] Admin UI for managing registration settings (deferred to Phase 4)

**Files modified:**
- `app/models/auth.py` - RegistrationSettings, AllowedEmail tables
- `app/routes/admin.py` - Registration settings endpoints
- `app/routes/auth.py` - Allowlist check in register

---

### 1.2 Chrome Mobile Auth Fix
- **Status:** [x] Completed (2025-01-07)
- **Priority:** High
- **Effort:** Low
- **Description:** Fix magic link verification for Chrome mobile (prefetch issues)

**Requirements:**
- [x] Create HTML redirect template instead of HTTP 302
- [x] Add 100ms delay before JavaScript redirect
- [x] Handle Chrome mobile email client prefetching
- [x] Set cookies without Domain attribute for first-party behavior

**Files modified:**
- `app/routes/auth.py` - Returns HTML template instead of redirect
- `templates/auth_redirect.html` - Delayed JavaScript redirect page

---

### 1.3 Token Reuse Logic
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Low
- **Description:** Prevent duplicate sessions when magic link is prefetched

**Requirements:**
- [x] Check if magic link was used within last 2 minutes
- [x] If recently used, return existing session token
- [x] Add `last_auth_token_id` field to magic_links table
- [x] Return same auth token for prefetch scenarios

**Files modified:**
- `app/models/auth.py` - Added last_auth_token_id field to MagicLink
- `app/routes/auth.py` - Token reuse logic in verify endpoint

---

### 1.4 CSV Export for Reports
- **Status:** [x] Completed (2025-01-07)
- **Priority:** High
- **Effort:** Low
- **Description:** Add CSV export functionality to all reports

**Requirements:**
- [x] API: GET /api/reports/equipment-usage?format=csv
- [x] API: GET /api/reports/user-activity?format=csv
- [x] API: GET /api/reports/booking-stats?format=csv
- [x] Proper CSV headers and formatting
- [x] Date range support in exports
- [ ] UI export buttons in reports section (deferred to Phase 4)

**Files modified:**
- `app/routes/reports.py` - Added format parameter, CSV generation with StreamingResponse

---

### 1.5 Service/Maintenance Mode
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Low
- **Description:** Admin-only access during maintenance

**Requirements:**
- [x] Add `service_mode` to app config or database
- [x] API: GET/PUT /api/admin/service-mode
- [x] Middleware to check service mode
- [x] Return 503 for non-admin users when enabled
- [x] Show maintenance message on login page
- [x] Admin can still access all features

**Files modified:**
- `app/models/auth.py` - Added SystemSettings table
- `app/middleware/auth.py` - Service mode check in get_current_user
- `app/routes/admin.py` - Service mode endpoints (GET/PUT)
- `app/routes/auth.py` - Public service mode status endpoint
- `templates/login.html` - Maintenance banner

---

## Phase 2: Enhanced Notifications

### 2.1 Working Hours Enforcement
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Low
- **Description:** Send notification emails only during business hours

**Requirements:**
- [x] Define working hours in config (default: 9:00-17:00 UTC)
- [x] Queue notifications outside working hours
- [x] Process queued notifications when working hours start
- [x] Skip enforcement for urgent notifications (cancellations)

**Files modified:**
- `app/config.py` - Added NotificationConfig with working hours
- `app/services/notifications.py` - is_within_working_hours(), get_next_working_hours_start()

---

### 2.2 Manager Booking Notification
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Low
- **Description:** Notify equipment managers when bookings are created

**Requirements:**
- [x] Send email to all managers when booking created on their equipment
- [x] Include booking details (user, dates, times, description)
- [x] Respect manager_notifications_enabled per equipment type
- [x] Add notification_type: 'manager_new_booking'

**Files modified:**
- `app/services/notifications.py` - queue_manager_new_booking_notification()
- `app/services/email.py` - send_manager_new_booking()
- `app/routes/bookings.py` - Trigger on create_booking

---

### 2.3 Short-Notice Cancellation Alert
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Low
- **Description:** Alert managers when booking cancelled with short notice

**Requirements:**
- [x] Define short notice threshold (default: 8 days)
- [x] Send alert to managers when booking cancelled within threshold
- [x] Include original booking details and cancellation time
- [x] Add notification_type: 'short_notice_cancellation'

**Files modified:**
- `app/config.py` - Added short_notice_days to BookingConfig
- `app/services/notifications.py` - queue_short_notice_cancellation_alert()
- `app/services/email.py` - send_short_notice_cancellation()
- `app/routes/bookings.py` - Trigger on cancel_booking

---

### 2.4 Enhanced Weekly Manager Reports
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Medium
- **Description:** Detailed HTML reports with booking lists

**Requirements:**
- [x] List all upcoming bookings for next 7 days
- [x] Group by equipment with formatted tables
- [x] Include user details and booking times
- [x] Show equipment specs and location
- [x] Send even if no bookings (helpful null state)
- [x] Professional HTML email design

**Files modified:**
- `app/services/scheduler.py` - Enhanced _run_weekly_reports()
- `app/services/email.py` - send_weekly_manager_report()

---

## Phase 3: AI Enhancements

### 3.1 Specification Extraction from Prompts
- **Status:** [x] Completed (2025-01-07)
- **Priority:** High
- **Effort:** Medium
- **Description:** Extract technical specs from natural language requests

**Requirements:**
- [x] Parse power requirements (e.g., "800W", "1kW")
- [x] Parse frequency requirements (e.g., "2.4GHz", "5.8 GHz")
- [x] Parse temperature requirements (e.g., "85°C", "-40C")
- [x] Parse voltage/current (e.g., "28V", "10A")
- [x] Use regex patterns with unit normalization
- [x] Pre-filter equipment before sending to AI

**Files modified:**
- `app/services/ai_service.py` - SpecificationExtractor class with SPEC_PATTERNS

---

### 3.2 Two-Stage AI Pipeline
- **Status:** [x] Completed (2025-01-07)
- **Priority:** High
- **Effort:** Medium
- **Description:** Pre-filter equipment before AI processing

**Requirements:**
- [x] Stage 1: Filter equipment by extracted specs (description matching)
- [x] Stage 2: AI matches from filtered list
- [x] Reduces AI context size and improves accuracy
- [x] Fall back to full list if no specs extracted

**Files modified:**
- `app/services/ai_service.py` - filter_equipment_by_specs(), updated analyze_booking_request()
- `app/routes/ai_assistant.py` - Returns extracted_specs and filter_info

---

### 3.3 Equipment Context Caching
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Low
- **Description:** Cache equipment context for AI requests

**Requirements:**
- [x] Cache equipment list for 4 hours
- [x] Invalidate on equipment changes (create/update/delete)
- [x] Use in-memory cache (global dict)
- [x] Reduces database queries for AI requests

**Files modified:**
- `app/services/ai_service.py` - _equipment_cache, invalidate_equipment_cache(), get_cached_equipment()
- `app/routes/equipment.py` - Cache invalidation on create/update/delete

---

### 3.4 Better Availability Checking
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Medium
- **Description:** SQL-based real-time availability in AI responses

**Requirements:**
- [x] Check actual availability before recommending
- [x] Return alternative dates if requested dates unavailable
- [x] Include availability info in AI response
- [x] Handle multi-day availability checks

**Files modified:**
- `app/services/ai_service.py` - _find_alternative_dates(), enhanced availability in analyze_booking_request()

---

## Phase 4: UI/UX Improvements

### 4.1 Enhanced Calendar View
- **Status:** [x] Completed (2025-01-07)
- **Priority:** High
- **Effort:** Medium
- **Description:** Improved booking calendar with visual indicators

**Requirements:**
- [x] Color-coded bookings by user (green = my bookings)
- [x] Partial day indicator (< 5 hours = khaki/yellow)
- [x] Show booking times on hover (title attribute)
- [x] Equipment filtering dropdown
- [x] Month navigation with prev/next buttons
- [x] Quick booking from calendar click

**Files modified:**
- `templates/dashboard.html` - Calendar view with list/calendar toggle
- `static/css/styles.css` - Calendar grid, booking colors, tooltip styles

---

### 4.2 Booking Modal Improvements
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Medium
- **Description:** Better date/time picker and validation

**Requirements:**
- [x] Date inputs with validation
- [x] Real-time conflict checking (checkConflicts)
- [x] Equipment details shown on selection
- [x] Description field with character count (10,240 max)
- [x] Conflict warning banner

**Files modified:**
- `templates/dashboard.html` - Enhanced modal with equipment details, conflict warning, char count
- `static/css/styles.css` - Conflict warning, character count, equipment details styles

---

### 4.3 Dashboard Usage Widget
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Low
- **Description:** Show usage statistics on dashboard

**Requirements:**
- [x] Upcoming bookings count
- [x] This month bookings count
- [x] Equipment count
- [x] Active bookings count
- [x] Gradient widget design

**Files modified:**
- `templates/dashboard.html` - Usage widget with 4 stats
- `static/css/styles.css` - Widget styling with gradient background

---

### 4.4 Role Color Badges
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Low
- **Effort:** Low
- **Description:** Visual role indicators

**Requirements:**
- [x] Admin: Red badge
- [x] Manager: Blue badge
- [x] User: Green badge
- [x] Show in sidebar user info
- [x] Show in admin users list

**Files modified:**
- `static/css/styles.css` - role-badge, role-badge-admin/manager/user classes
- `templates/dashboard.html` - Badge in sidebar and admin table
- `static/js/dashboard.js` - Badge rendering

---

## Phase 5: Nice to Have

### 5.1 Möbius Animation
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Low
- **Effort:** Low
- **Description:** 3D animation on landing page

**Requirements:**
- [x] Canvas-based 3D Möbius strip
- [x] Greenish gradient coloring
- [x] Smooth rotation animation
- [x] Responsive sizing

**Files modified:**
- `templates/index.html` - Canvas element and inline JavaScript animation

---

### 5.2 Demo Mode Protection
- **Status:** [-] Skipped (per user request)
- **Priority:** Low
- **Effort:** Low
- **Description:** Read-only demo instance

**Note:** Feature skipped as not needed by user. Partial implementation exists (config flag, middleware check, banner) but not integrated into routes.

---

### 5.3 Detailed Audit Logging
- **Status:** [x] Completed (2025-01-07)
- **Priority:** Medium
- **Effort:** Medium
- **Description:** Track all admin actions

**Requirements:**
- [x] New audit_log table
- [x] Log helper function (log_audit_event)
- [x] GET /api/admin/audit-log - View logs with filtering
- [x] GET /api/admin/audit-log/summary - Statistics by action/resource/user
- [x] DELETE /api/admin/audit-log/cleanup - Retention cleanup

**Files modified:**
- `app/models/auth.py` - AuditLog model
- `app/models/__init__.py` - Export AuditLog
- `app/routes/admin.py` - Audit log endpoints and log_audit_event helper

---

## Implementation Progress

### Summary

| Phase | Total | Completed | Skipped | Remaining |
|-------|-------|-----------|---------|-----------|
| Phase 1 | 5 | 5 | 0 | 0 |
| Phase 2 | 4 | 4 | 0 | 0 |
| Phase 3 | 4 | 4 | 0 | 0 |
| Phase 4 | 4 | 4 | 0 | 0 |
| Phase 5 | 3 | 2 | 1 | 0 |
| **Total** | **20** | **19** | **1** | **0** |

### Changelog

| Date | Item | Status | Notes |
|------|------|--------|-------|
| 2025-01-07 | Plan created | - | Initial version |
| 2025-01-07 | Phase 1 completed | Complete | All critical features implemented |
| 2025-01-07 | Phase 2 completed | Complete | Enhanced notifications implemented |
| 2025-01-07 | Phase 3 completed | Complete | AI enhancements: spec extraction, two-stage pipeline, caching, availability |
| 2025-01-07 | Phase 4 completed | Complete | UI/UX: calendar view, modal improvements, usage widget, role badges |
| 2025-01-07 | Phase 5 completed | Complete | Möbius animation, audit logging (demo mode skipped)

---

## Notes

### Single-Tenant Adaptations
The following multi-tenant features from rfbooking-core are NOT applicable:
- Subdomain-based routing
- Separate database per organization
- META database for org routing
- Subscription tier enforcement
- Cross-organization isolation
- Organization suspension

### Configuration Changes Made
1. Removed `secret_key` (unused)
2. Set `email.enabled = true` by default
3. Reorganized config sections (Required/Automatic/Optional)
4. Added LAN IP auto-detection in rfbctl.sh

### Bug Fixes Applied
1. Fixed `/auth/verify` → `/api/auth/verify` URL path
2. Fixed volume mount issue in docker-compose
3. Added SMTP provider support alongside Resend
