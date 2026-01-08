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

"""Email service using Resend API or SMTP."""

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any

from app.config import get_settings


class EmailService:
    """Email service for sending notifications via Resend or SMTP."""

    def __init__(self):
        self.settings = get_settings()
        self._resend_client = None

    @property
    def provider(self) -> str:
        """Get the configured email provider."""
        return self.settings.email.provider.lower()

    @property
    def resend_client(self):
        """Lazy-load Resend client."""
        if self._resend_client is None and self.provider == "resend":
            import resend
            resend.api_key = self.settings.email.api_key
            self._resend_client = resend
        return self._resend_client

    async def _send_via_smtp(
        self,
        to: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send email via SMTP."""
        import aiosmtplib

        email_config = self.settings.email

        # Create message
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{email_config.from_name} <{email_config.from_address}>"
        msg["To"] = to
        msg["Subject"] = subject

        # Add text and HTML parts
        if text:
            msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        # Send via SMTP
        try:
            await aiosmtplib.send(
                msg,
                hostname=email_config.smtp_host,
                port=email_config.smtp_port,
                username=email_config.smtp_username or None,
                password=email_config.smtp_password or None,
                start_tls=email_config.smtp_use_tls,
                use_tls=email_config.smtp_use_ssl,
            )
            return {"success": True, "provider": "smtp"}
        except Exception as e:
            print(f"[SMTP ERROR] Failed to send email to {to}: {e}")
            raise

    async def _send_via_resend(
        self,
        to: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send email via Resend API."""
        params = {
            "from": f"{self.settings.email.from_name} <{self.settings.email.from_address}>",
            "to": [to],
            "subject": subject,
            "html": html,
        }

        if text:
            params["text"] = text

        result = self.resend_client.Emails.send(params)
        return {"id": result.get("id"), "success": True, "provider": "resend"}

    async def send_email(
        self,
        to: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an email via configured provider.

        Args:
            to: Recipient email address
            subject: Email subject
            html: HTML content
            text: Plain text content (optional)

        Returns:
            Response from email provider or dev mode info
        """
        if self.provider == "smtp":
            return await self._send_via_smtp(to, subject, html, text)
        else:
            # Default to Resend
            return await self._send_via_resend(to, subject, html, text)

    async def send_magic_link(
        self,
        email: str,
        token: str,
        name: str,
    ) -> Dict[str, Any]:
        """Send magic link email for authentication.

        Args:
            email: Recipient email address
            token: Magic link token
            name: User's name

        Returns:
            Response from email provider
        """
        verify_url = f"{self.settings.app.base_url}/api/auth/verify?token={token}"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Welcome to {self.settings.app.name}</h2>
        <p>Hi {name},</p>
        <p>Click the button below to sign in to your account:</p>
        <a href="{verify_url}" class="button">Sign In</a>
        <p>Or copy and paste this link into your browser:</p>
        <p><a href="{verify_url}">{verify_url}</a></p>
        <p>This link will expire in {self.settings.security.magic_link_minutes} minutes.</p>
        <div class="footer">
            <p>If you didn't request this email, you can safely ignore it.</p>
            <p>{self.settings.organization.name}</p>
        </div>
    </div>
</body>
</html>
"""

        text = f"""
Welcome to {self.settings.app.name}

Hi {name},

Click the link below to sign in to your account:
{verify_url}

This link will expire in {self.settings.security.magic_link_minutes} minutes.

If you didn't request this email, you can safely ignore it.

{self.settings.organization.name}
"""

        return await self.send_email(
            to=email,
            subject=f"Sign in to {self.settings.app.name}",
            html=html,
            text=text,
        )

    async def send_booking_confirmation(
        self,
        email: str,
        name: str,
        booking_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send booking confirmation email."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .details {{ background: #f5f5f5; padding: 15px; border-radius: 6px; margin: 20px 0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Booking Confirmed</h2>
        <p>Hi {name},</p>
        <p>Your equipment booking has been confirmed:</p>
        <div class="details">
            <p><strong>Equipment:</strong> {booking_data.get('equipment_name', 'N/A')}</p>
            <p><strong>Date:</strong> {booking_data.get('start_date')} to {booking_data.get('end_date')}</p>
            <p><strong>Time:</strong> {booking_data.get('start_time')} - {booking_data.get('end_time')}</p>
            <p><strong>Location:</strong> {booking_data.get('equipment_location', 'N/A')}</p>
        </div>
        <p>You can view and manage your booking in the dashboard.</p>
        <div class="footer">
            <p>{self.settings.organization.name}</p>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"Booking Confirmed: {booking_data.get('equipment_name', 'Equipment')}",
            html=html,
        )

    async def send_booking_reminder(
        self,
        email: str,
        name: str,
        booking_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send booking reminder email."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .details {{ background: #fff3cd; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #ffc107; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Booking Reminder</h2>
        <p>Hi {name},</p>
        <p>This is a reminder about your upcoming equipment booking:</p>
        <div class="details">
            <p><strong>Equipment:</strong> {booking_data.get('equipment_name', 'N/A')}</p>
            <p><strong>Date:</strong> {booking_data.get('start_date')}</p>
            <p><strong>Time:</strong> {booking_data.get('start_time')} - {booking_data.get('end_time')}</p>
            <p><strong>Location:</strong> {booking_data.get('equipment_location', 'N/A')}</p>
        </div>
        <div class="footer">
            <p>{self.settings.organization.name}</p>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"Reminder: {booking_data.get('equipment_name', 'Equipment')} booking tomorrow",
            html=html,
        )

    async def send_booking_cancellation(
        self,
        email: str,
        name: str,
        booking_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send booking cancellation email."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .details {{ background: #f8d7da; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #dc3545; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Booking Cancelled</h2>
        <p>Hi {name},</p>
        <p>Your equipment booking has been cancelled:</p>
        <div class="details">
            <p><strong>Equipment:</strong> {booking_data.get('equipment_name', 'N/A')}</p>
            <p><strong>Date:</strong> {booking_data.get('start_date')} to {booking_data.get('end_date')}</p>
            <p><strong>Time:</strong> {booking_data.get('start_time')} - {booking_data.get('end_time')}</p>
        </div>
        <div class="footer">
            <p>{self.settings.organization.name}</p>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"Booking Cancelled: {booking_data.get('equipment_name', 'Equipment')}",
            html=html,
        )

    async def send_manager_new_booking(
        self,
        email: str,
        name: str,
        booking_data: Dict[str, Any],
        booker_name: str,
    ) -> Dict[str, Any]:
        """Send notification to manager about new booking."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .details {{ background: #e8f4fd; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #2563eb; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>New Booking Created</h2>
        <p>Hi {name},</p>
        <p>A new booking has been created for equipment you manage:</p>
        <div class="details">
            <p><strong>Equipment:</strong> {booking_data.get('equipment_name', 'N/A')}</p>
            <p><strong>Booked by:</strong> {booker_name}</p>
            <p><strong>Date:</strong> {booking_data.get('start_date')} to {booking_data.get('end_date')}</p>
            <p><strong>Time:</strong> {booking_data.get('start_time')} - {booking_data.get('end_time')}</p>
            <p><strong>Location:</strong> {booking_data.get('equipment_location', 'N/A')}</p>
            {f"<p><strong>Description:</strong> {booking_data.get('description')}</p>" if booking_data.get('description') else ""}
        </div>
        <p>You can view and manage this booking in the dashboard.</p>
        <div class="footer">
            <p>{self.settings.organization.name}</p>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"New Booking: {booking_data.get('equipment_name', 'Equipment')} by {booker_name}",
            html=html,
        )

    async def send_short_notice_cancellation(
        self,
        email: str,
        name: str,
        booking_data: Dict[str, Any],
        booker_name: str,
    ) -> Dict[str, Any]:
        """Send alert to manager about short-notice cancellation."""
        settings = get_settings()
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .alert {{ background: #fef3cd; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #ffc107; }}
        .details {{ background: #f8d7da; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #dc3545; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Short-Notice Cancellation Alert</h2>
        <p>Hi {name},</p>
        <div class="alert">
            <p><strong>Alert:</strong> A booking was cancelled with less than {settings.booking.short_notice_days} days notice.</p>
        </div>
        <p>The following booking has been cancelled:</p>
        <div class="details">
            <p><strong>Equipment:</strong> {booking_data.get('equipment_name', 'N/A')}</p>
            <p><strong>Originally booked by:</strong> {booker_name}</p>
            <p><strong>Date:</strong> {booking_data.get('start_date')} to {booking_data.get('end_date')}</p>
            <p><strong>Time:</strong> {booking_data.get('start_time')} - {booking_data.get('end_time')}</p>
            <p><strong>Location:</strong> {booking_data.get('equipment_location', 'N/A')}</p>
        </div>
        <p>This time slot is now available for other users to book.</p>
        <div class="footer">
            <p>{self.settings.organization.name}</p>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"[ALERT] Short-Notice Cancellation: {booking_data.get('equipment_name', 'Equipment')}",
            html=html,
        )

    async def send_calibration_reminder(
        self,
        email: str,
        name: str,
        equipment_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send calibration reminder to equipment manager."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .details {{ background: #fff3cd; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #ffc107; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Calibration Reminder</h2>
        <p>Hi {name},</p>
        <p>Equipment you manage is due for calibration:</p>
        <div class="details">
            <p><strong>Equipment:</strong> {equipment_data.get('name', 'N/A')}</p>
            <p><strong>Location:</strong> {equipment_data.get('location', 'N/A')}</p>
            <p><strong>Calibration Due:</strong> {equipment_data.get('next_calibration_date', 'N/A')}</p>
        </div>
        <p>Please schedule the calibration to ensure continued equipment accuracy.</p>
        <div class="footer">
            <p>{self.settings.organization.name}</p>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"Calibration Due: {equipment_data.get('name', 'Equipment')}",
            html=html,
        )

    async def send_weekly_manager_report(
        self,
        email: str,
        name: str,
        equipment_bookings: Dict[str, Any],
        week_start: str,
        week_end: str,
    ) -> Dict[str, Any]:
        """Send weekly report to equipment manager with upcoming bookings."""
        # Build equipment sections
        equipment_sections = ""
        total_bookings = 0

        for eq_name, data in equipment_bookings.items():
            bookings = data.get("bookings", [])
            total_bookings += len(bookings)

            if bookings:
                rows = ""
                for b in bookings:
                    rows += f"""
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{b.get('user_name', 'N/A')}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{b.get('start_date')}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{b.get('start_time')} - {b.get('end_time')}</td>
                    </tr>
                    """
                equipment_sections += f"""
                <div style="margin-bottom: 25px;">
                    <h3 style="color: #2563eb; margin-bottom: 10px;">{eq_name}</h3>
                    <p style="color: #666; font-size: 14px; margin-bottom: 10px;">Location: {data.get('location', 'N/A')}</p>
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #f5f5f5;">
                                <th style="padding: 8px; text-align: left;">User</th>
                                <th style="padding: 8px; text-align: left;">Date</th>
                                <th style="padding: 8px; text-align: left;">Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows}
                        </tbody>
                    </table>
                </div>
                """
            else:
                equipment_sections += f"""
                <div style="margin-bottom: 25px;">
                    <h3 style="color: #2563eb; margin-bottom: 10px;">{eq_name}</h3>
                    <p style="color: #666; font-size: 14px; margin-bottom: 10px;">Location: {data.get('location', 'N/A')}</p>
                    <p style="color: #888; font-style: italic;">No bookings scheduled for this period.</p>
                </div>
                """

        if not equipment_bookings:
            equipment_sections = "<p style='color: #888;'>No equipment assigned to manage.</p>"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .summary {{ background: #f8fafc; padding: 15px; margin-bottom: 20px; border-radius: 6px; }}
        .content {{ padding: 20px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">Weekly Equipment Report</h2>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">{week_start} - {week_end}</p>
        </div>
        <div class="content">
            <p>Hi {name},</p>
            <p>Here's your weekly summary of upcoming equipment bookings:</p>

            <div class="summary">
                <strong>Summary:</strong> {total_bookings} booking(s) across {len(equipment_bookings)} equipment item(s)
            </div>

            {equipment_sections}

            <p>You can view and manage all bookings in the dashboard.</p>
        </div>
        <div class="footer">
            <p>{self.settings.organization.name}</p>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"Weekly Equipment Report: {week_start} - {week_end}",
            html=html,
        )


# Global service instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get the global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service


async def send_email_direct(
    config,  # EmailConfig from app.config
    to_email: str,
    subject: str,
    html_content: str,
) -> bool:
    """Send an email using provided configuration (for setup testing).

    Args:
        config: EmailConfig object with email settings
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email

    Returns:
        True if email was sent successfully, False otherwise
    """
    if config.provider.lower() == "smtp":
        import aiosmtplib

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{config.from_name} <{config.from_address}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=config.smtp_host,
            port=config.smtp_port,
            username=config.smtp_username or None,
            password=config.smtp_password or None,
            start_tls=config.smtp_use_tls,
            use_tls=config.smtp_use_ssl,
        )
        return True

    elif config.provider.lower() == "resend":
        import resend

        resend.api_key = config.api_key
        resend.Emails.send({
            "from": f"{config.from_name} <{config.from_address}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        })
        return True

    return False
