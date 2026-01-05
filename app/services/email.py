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

"""Email service using Resend API."""

from typing import Optional, Dict, Any

from app.config import get_settings


class EmailService:
    """Email service for sending notifications."""

    def __init__(self):
        self.settings = get_settings()
        self._client = None

    @property
    def enabled(self) -> bool:
        """Check if email is enabled."""
        return self.settings.email.enabled

    @property
    def client(self):
        """Lazy-load Resend client."""
        if self._client is None and self.enabled:
            import resend
            resend.api_key = self.settings.email.api_key
            self._client = resend
        return self._client

    async def send_email(
        self,
        to: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            html: HTML content
            text: Plain text content (optional)

        Returns:
            Response from email provider or dev mode info
        """
        if not self.enabled:
            print(f"[DEV MODE] Email to {to}: {subject}")
            return {"dev_mode": True, "to": to, "subject": subject}

        params = {
            "from": f"{self.settings.email.from_name} <{self.settings.email.from_address}>",
            "to": [to],
            "subject": subject,
            "html": html,
        }

        if text:
            params["text"] = text

        result = self.client.Emails.send(params)
        return {"id": result.get("id"), "success": True}

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
        verify_url = f"{self.settings.app.base_url}/auth/verify?token={token}"

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


# Global service instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get the global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
