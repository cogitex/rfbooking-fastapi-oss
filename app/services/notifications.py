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

"""Notification service for booking reminders and alerts."""

from datetime import datetime, timedelta, date, time
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.auth import NotificationLog
from app.models.booking import Booking
from app.models.equipment import Equipment, EquipmentManager, EquipmentType
from app.models.user import User
from app.services.email import get_email_service


def is_within_working_hours(dt: datetime = None) -> bool:
    """Check if a datetime is within configured working hours (UTC).

    Args:
        dt: Datetime to check. Defaults to now.

    Returns:
        True if within working hours, False otherwise.
    """
    settings = get_settings()

    if not settings.notification.enforce_working_hours:
        return True

    if dt is None:
        dt = datetime.utcnow()

    # Parse working hours
    start_parts = settings.notification.working_hours_start.split(":")
    end_parts = settings.notification.working_hours_end.split(":")

    start_time = time(int(start_parts[0]), int(start_parts[1]))
    end_time = time(int(end_parts[0]), int(end_parts[1]))

    current_time = dt.time()

    return start_time <= current_time <= end_time


def get_next_working_hours_start() -> datetime:
    """Get the next datetime when working hours start.

    Returns:
        Datetime of next working hours start.
    """
    settings = get_settings()
    now = datetime.utcnow()

    start_parts = settings.notification.working_hours_start.split(":")
    start_time = time(int(start_parts[0]), int(start_parts[1]))

    # Try today first
    today_start = datetime.combine(now.date(), start_time)

    if now < today_start:
        return today_start
    else:
        # Tomorrow
        return datetime.combine(now.date() + timedelta(days=1), start_time)


def queue_booking_notification(
    db: Session,
    booking: Booking,
    notification_type: str,
) -> None:
    """Queue a booking notification.

    Args:
        db: Database session
        booking: Booking object
        notification_type: 'created', 'cancelled', 'reminder'
    """
    user = booking.user
    if not user or not user.email_notifications_enabled:
        return

    # Determine scheduled time
    if notification_type == "created":
        scheduled_for = datetime.utcnow()
        notif_type = "booking_confirmation_user"
    elif notification_type == "cancelled":
        scheduled_for = datetime.utcnow()
        notif_type = "booking_cancellation"
    elif notification_type == "reminder":
        # Schedule for reminder_hours before booking
        reminder_time = datetime.combine(
            booking.start_date, booking.start_time
        ) - timedelta(hours=settings.booking.reminder_hours)
        scheduled_for = reminder_time
        notif_type = "booking_reminder"
    else:
        return

    # Check for duplicate
    existing = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.notification_type == notif_type,
            NotificationLog.recipient_user_id == user.id,
            NotificationLog.reference_id == booking.id,
            NotificationLog.reference_type == "booking",
        )
        .first()
    )

    if existing:
        return

    # Create notification log
    notification = NotificationLog(
        notification_type=notif_type,
        recipient_user_id=user.id,
        reference_id=booking.id,
        reference_type="booking",
        scheduled_for=scheduled_for,
        status="pending",
    )
    db.add(notification)


async def process_pending_notifications(db: Session) -> dict:
    """Process all pending notifications.

    Respects working hours for non-urgent notifications.

    Returns:
        Statistics about processed notifications.
    """
    settings = get_settings()
    email_service = get_email_service()

    now = datetime.utcnow()
    within_working_hours = is_within_working_hours(now)
    urgent_types = settings.notification.urgent_types

    # Get pending notifications scheduled for now or earlier
    pending = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.status == "pending",
            NotificationLog.scheduled_for <= now,
        )
        .limit(100)  # Process in batches
        .all()
    )

    stats = {"sent": 0, "failed": 0, "skipped": 0, "deferred": 0}

    for notification in pending:
        try:
            # Check working hours for non-urgent notifications
            if not within_working_hours and notification.notification_type not in urgent_types:
                # Defer to next working hours
                notification.scheduled_for = get_next_working_hours_start()
                stats["deferred"] += 1
                continue

            # Get recipient
            user = db.query(User).filter(User.id == notification.recipient_user_id).first()

            if not user or not user.is_active or not user.email_notifications_enabled:
                notification.status = "skipped"
                notification.error_message = "User inactive or notifications disabled"
                stats["skipped"] += 1
                continue

            # Get booking if reference
            booking = None
            booking_data = {}
            if notification.reference_type == "booking" and notification.reference_id:
                booking = db.query(Booking).filter(Booking.id == notification.reference_id).first()
                if booking:
                    booking_data = booking.to_dict()

            # Get equipment if reference
            equipment_data = {}
            if notification.reference_type == "equipment" and notification.reference_id:
                equipment = db.query(Equipment).filter(Equipment.id == notification.reference_id).first()
                if equipment:
                    equipment_data = equipment.to_dict()

            # Send notification based on type
            if notification.notification_type == "booking_confirmation_user":
                await email_service.send_booking_confirmation(
                    email=user.email,
                    name=user.name,
                    booking_data=booking_data,
                )
            elif notification.notification_type == "booking_reminder":
                await email_service.send_booking_reminder(
                    email=user.email,
                    name=user.name,
                    booking_data=booking_data,
                )
            elif notification.notification_type == "booking_cancellation":
                await email_service.send_booking_cancellation(
                    email=user.email,
                    name=user.name,
                    booking_data=booking_data,
                )
            elif notification.notification_type == "manager_new_booking":
                await email_service.send_manager_new_booking(
                    email=user.email,
                    name=user.name,
                    booking_data=booking_data,
                    booker_name=booking.user.name if booking and booking.user else "Unknown",
                )
            elif notification.notification_type == "short_notice_cancellation":
                await email_service.send_short_notice_cancellation(
                    email=user.email,
                    name=user.name,
                    booking_data=booking_data,
                    booker_name=booking.user.name if booking and booking.user else "Unknown",
                )
            elif notification.notification_type == "calibration_reminder":
                await email_service.send_calibration_reminder(
                    email=user.email,
                    name=user.name,
                    equipment_data=equipment_data,
                )

            notification.status = "sent"
            notification.sent_at = datetime.utcnow()
            stats["sent"] += 1

        except Exception as e:
            notification.status = "failed"
            notification.error_message = str(e)
            notification.send_attempts += 1
            stats["failed"] += 1

    db.commit()
    return stats


async def queue_daily_reminders(db: Session) -> dict:
    """Queue reminders for bookings starting tomorrow.

    Returns:
        Statistics about queued reminders.
    """
    settings = get_settings()
    tomorrow = date.today() + timedelta(days=1)

    # Find bookings starting tomorrow
    bookings = (
        db.query(Booking)
        .filter(
            Booking.start_date == tomorrow,
            Booking.status == "active",
        )
        .all()
    )

    queued = 0
    for booking in bookings:
        queue_booking_notification(db, booking, "reminder")
        queued += 1

    db.commit()
    return {"queued_reminders": queued}


async def queue_calibration_reminders(db: Session) -> dict:
    """Queue calibration reminders for equipment.

    Returns:
        Statistics about queued reminders.
    """
    settings = get_settings()
    reminder_date = date.today() + timedelta(days=settings.booking.calibration_reminder_days)

    # Find equipment with calibration due
    equipment_list = (
        db.query(Equipment)
        .filter(
            Equipment.next_calibration_date == reminder_date,
            Equipment.is_active == True,
        )
        .all()
    )

    queued = 0
    for equipment in equipment_list:
        # Get managers
        managers = (
            db.query(User)
            .join(EquipmentManager, EquipmentManager.manager_id == User.id)
            .filter(
                EquipmentManager.equipment_id == equipment.id,
                User.is_active == True,
                User.email_notifications_enabled == True,
            )
            .all()
        )

        for manager in managers:
            # Check for duplicate
            existing = (
                db.query(NotificationLog)
                .filter(
                    NotificationLog.notification_type == "calibration_reminder",
                    NotificationLog.recipient_user_id == manager.id,
                    NotificationLog.reference_id == equipment.id,
                    NotificationLog.reference_type == "equipment",
                )
                .first()
            )

            if not existing:
                notification = NotificationLog(
                    notification_type="calibration_reminder",
                    recipient_user_id=manager.id,
                    reference_id=equipment.id,
                    reference_type="equipment",
                    scheduled_for=datetime.utcnow(),
                    status="pending",
                )
                db.add(notification)
                queued += 1

    db.commit()
    return {"queued_calibration_reminders": queued}


def queue_manager_new_booking_notification(
    db: Session,
    booking: Booking,
) -> int:
    """Queue notifications to managers when a new booking is created.

    Args:
        db: Database session
        booking: The newly created booking

    Returns:
        Number of notifications queued.
    """
    equipment = booking.equipment
    if not equipment:
        return 0

    # Check if equipment type has manager notifications enabled
    if equipment.type_id:
        equipment_type = db.query(EquipmentType).filter(
            EquipmentType.id == equipment.type_id
        ).first()
        if equipment_type and not equipment_type.manager_notifications_enabled:
            return 0

    # Get managers for this equipment
    managers = (
        db.query(User)
        .join(EquipmentManager, EquipmentManager.manager_id == User.id)
        .filter(
            EquipmentManager.equipment_id == equipment.id,
            User.is_active == True,
            User.email_notifications_enabled == True,
        )
        .all()
    )

    # Determine scheduled time based on working hours
    if is_within_working_hours():
        scheduled_for = datetime.utcnow()
    else:
        scheduled_for = get_next_working_hours_start()

    queued = 0
    for manager in managers:
        # Don't notify if manager is the one who created the booking
        if manager.id == booking.user_id:
            continue

        # Check for duplicate
        existing = (
            db.query(NotificationLog)
            .filter(
                NotificationLog.notification_type == "manager_new_booking",
                NotificationLog.recipient_user_id == manager.id,
                NotificationLog.reference_id == booking.id,
                NotificationLog.reference_type == "booking",
            )
            .first()
        )

        if not existing:
            notification = NotificationLog(
                notification_type="manager_new_booking",
                recipient_user_id=manager.id,
                reference_id=booking.id,
                reference_type="booking",
                scheduled_for=scheduled_for,
                status="pending",
            )
            db.add(notification)
            queued += 1

    if queued > 0:
        db.commit()

    return queued


def queue_short_notice_cancellation_alert(
    db: Session,
    booking: Booking,
) -> int:
    """Queue alerts to managers when a booking is cancelled with short notice.

    Short notice is defined as cancellation within X days of the booking start date.

    Args:
        db: Database session
        booking: The cancelled booking

    Returns:
        Number of alerts queued.
    """
    settings = get_settings()

    # Check if this is short notice
    days_until_booking = (booking.start_date - date.today()).days
    if days_until_booking > settings.booking.short_notice_days:
        return 0  # Not short notice

    equipment = booking.equipment
    if not equipment:
        return 0

    # Get managers for this equipment
    managers = (
        db.query(User)
        .join(EquipmentManager, EquipmentManager.manager_id == User.id)
        .filter(
            EquipmentManager.equipment_id == equipment.id,
            User.is_active == True,
            User.email_notifications_enabled == True,
        )
        .all()
    )

    # Short notice cancellations are urgent - send immediately (bypass working hours)
    scheduled_for = datetime.utcnow()

    queued = 0
    for manager in managers:
        # Check for duplicate
        existing = (
            db.query(NotificationLog)
            .filter(
                NotificationLog.notification_type == "short_notice_cancellation",
                NotificationLog.recipient_user_id == manager.id,
                NotificationLog.reference_id == booking.id,
                NotificationLog.reference_type == "booking",
            )
            .first()
        )

        if not existing:
            notification = NotificationLog(
                notification_type="short_notice_cancellation",
                recipient_user_id=manager.id,
                reference_id=booking.id,
                reference_type="booking",
                scheduled_for=scheduled_for,
                status="pending",
            )
            db.add(notification)
            queued += 1

    if queued > 0:
        db.commit()

    return queued
