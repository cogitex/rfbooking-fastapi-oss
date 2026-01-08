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

"""Scheduler service using APScheduler."""

import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session_local
from app.models.auth import AuthToken, MagicLink, CronJob, NotificationLog
from app.models.equipment import AIQueryLog


# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    """Get the global scheduler instance."""
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler()
    return scheduler


async def run_cron_job(job_key: str, db: Session) -> Dict[str, Any]:
    """Run a cron job by key.

    Args:
        job_key: The job identifier
        db: Database session

    Returns:
        Result of the job execution.
    """
    start_time = time.time()
    result = {}

    try:
        if job_key == "daily_notifications":
            result = await _run_daily_notifications(db)
        elif job_key == "daily_cleanup":
            result = await _run_daily_cleanup(db)
        elif job_key == "weekly_manager_reports":
            result = await _run_weekly_reports(db)
        else:
            raise ValueError(f"Unknown job key: {job_key}")

        # Update job status
        job = db.query(CronJob).filter(CronJob.job_key == job_key).first()
        if job:
            job.last_run_at = datetime.utcnow()
            job.last_run_status = "success"
            job.last_run_duration_ms = int((time.time() - start_time) * 1000)
            job.total_runs += 1
            db.commit()

        return result

    except Exception as e:
        # Update job with error status
        job = db.query(CronJob).filter(CronJob.job_key == job_key).first()
        if job:
            job.last_run_at = datetime.utcnow()
            job.last_run_status = "error"
            job.last_run_duration_ms = int((time.time() - start_time) * 1000)
            job.total_errors += 1
            db.commit()

        raise e


async def _run_daily_notifications(db: Session) -> Dict[str, Any]:
    """Process daily notifications."""
    from app.services.notifications import (
        process_pending_notifications,
        queue_daily_reminders,
        queue_calibration_reminders,
    )

    results = {}

    # Queue reminders for tomorrow
    results["reminders"] = await queue_daily_reminders(db)

    # Queue calibration reminders
    results["calibration"] = await queue_calibration_reminders(db)

    # Process pending notifications
    results["processed"] = await process_pending_notifications(db)

    return results


async def _run_daily_cleanup(db: Session) -> Dict[str, Any]:
    """Clean up old records."""
    settings = get_settings()
    results = {}

    # Calculate cutoff dates
    token_cutoff = datetime.utcnow() - timedelta(days=settings.cleanup.auth_token_retention_days)
    magic_cutoff = datetime.utcnow() - timedelta(days=settings.cleanup.magic_link_retention_days)
    ai_cutoff = datetime.utcnow() - timedelta(days=settings.cleanup.ai_query_log_retention_days)
    notif_cutoff = datetime.utcnow() - timedelta(days=settings.cleanup.notification_log_retention_days)

    # Delete old expired tokens
    expired_tokens = (
        db.query(AuthToken)
        .filter(AuthToken.expires_at < token_cutoff)
        .delete(synchronize_session=False)
    )
    results["expired_tokens_deleted"] = expired_tokens

    # Delete old revoked tokens
    revoked_tokens = (
        db.query(AuthToken)
        .filter(
            AuthToken.is_revoked == True,
            AuthToken.created_at < token_cutoff,
        )
        .delete(synchronize_session=False)
    )
    results["revoked_tokens_deleted"] = revoked_tokens

    # Delete old magic links
    magic_links = (
        db.query(MagicLink)
        .filter(MagicLink.expires_at < magic_cutoff)
        .delete(synchronize_session=False)
    )
    results["magic_links_deleted"] = magic_links

    # Delete old AI query logs
    ai_logs = (
        db.query(AIQueryLog)
        .filter(AIQueryLog.created_at < ai_cutoff)
        .delete(synchronize_session=False)
    )
    results["ai_logs_deleted"] = ai_logs

    # Delete old notification logs
    notif_logs = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.created_at < notif_cutoff,
            NotificationLog.status.in_(["sent", "skipped", "failed"]),
        )
        .delete(synchronize_session=False)
    )
    results["notification_logs_deleted"] = notif_logs

    db.commit()
    return results


async def _run_weekly_reports(db: Session) -> Dict[str, Any]:
    """Generate and send enhanced weekly manager reports.

    Reports include:
    - All upcoming bookings for next 7 days
    - Grouped by equipment with formatted tables
    - User details and booking times
    - Equipment location and specs
    - Sent even if no bookings (helpful null state)
    """
    from app.models.equipment import Equipment, EquipmentManager
    from app.models.booking import Booking
    from app.models.user import User
    from app.services.email import get_email_service
    from datetime import date

    settings = get_settings()
    email_service = get_email_service()

    # Get the date range for the report (next 7 days)
    today = date.today()
    week_ahead = today + timedelta(days=7)
    week_start = today.strftime("%Y-%m-%d")
    week_end = week_ahead.strftime("%Y-%m-%d")

    # Get all managers with email notifications enabled
    managers = (
        db.query(User)
        .filter(
            User.role_id.in_([1, 2]),  # Admin or Manager
            User.is_active == True,
            User.email_notifications_enabled == True,
        )
        .all()
    )

    reports_sent = 0

    for manager in managers:
        # Get managed equipment
        if manager.role_id == 1:  # Admin sees all
            managed_equipment = db.query(Equipment).filter(Equipment.is_active == True).all()
        else:
            managed_equipment = (
                db.query(Equipment)
                .join(EquipmentManager, EquipmentManager.equipment_id == Equipment.id)
                .filter(
                    EquipmentManager.manager_id == manager.id,
                    Equipment.is_active == True,
                )
                .all()
            )

        # Build equipment bookings dict grouped by equipment
        equipment_bookings = {}

        for equipment in managed_equipment:
            # Get upcoming bookings for this equipment
            bookings = (
                db.query(Booking)
                .filter(
                    Booking.equipment_id == equipment.id,
                    Booking.status == "active",
                    Booking.start_date >= today,
                    Booking.start_date <= week_ahead,
                )
                .order_by(Booking.start_date, Booking.start_time)
                .all()
            )

            equipment_bookings[equipment.name] = {
                "location": equipment.location or "N/A",
                "bookings": [
                    {
                        "user_name": b.user.name if b.user else "Unknown",
                        "start_date": b.start_date.strftime("%Y-%m-%d"),
                        "start_time": b.start_time.strftime("%H:%M") if b.start_time else "N/A",
                        "end_time": b.end_time.strftime("%H:%M") if b.end_time else "N/A",
                    }
                    for b in bookings
                ],
            }

        # Send report (even if no bookings - helpful null state)
        try:
            await email_service.send_weekly_manager_report(
                email=manager.email,
                name=manager.name,
                equipment_bookings=equipment_bookings,
                week_start=week_start,
                week_end=week_end,
            )
            reports_sent += 1
        except Exception as e:
            print(f"Failed to send weekly report to {manager.email}: {e}")

    return {"reports_sent": reports_sent}


def setup_scheduler():
    """Set up the scheduler with cron jobs."""
    sched = get_scheduler()

    # Get database session
    SessionLocal = get_session_local()

    async def run_job(job_key: str):
        """Wrapper to run job with database session."""
        db = SessionLocal()
        try:
            # Check if job is enabled
            job = db.query(CronJob).filter(CronJob.job_key == job_key).first()
            if job and job.is_enabled:
                await run_cron_job(job_key, db)
        finally:
            db.close()

    # Daily notifications - 8 AM UTC
    sched.add_job(
        lambda: run_job("daily_notifications"),
        CronTrigger(hour=8, minute=0),
        id="daily_notifications",
        replace_existing=True,
    )

    # Daily cleanup - 8 AM UTC
    sched.add_job(
        lambda: run_job("daily_cleanup"),
        CronTrigger(hour=8, minute=0),
        id="daily_cleanup",
        replace_existing=True,
    )

    # Weekly reports - Friday 9 AM UTC
    sched.add_job(
        lambda: run_job("weekly_manager_reports"),
        CronTrigger(day_of_week="fri", hour=9, minute=0),
        id="weekly_manager_reports",
        replace_existing=True,
    )

    return sched


def start_scheduler():
    """Start the scheduler."""
    sched = setup_scheduler()
    if not sched.running:
        sched.start()
    return sched


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
