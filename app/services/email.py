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
        org_name = self.settings.organization.name

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>Welcome to {org_name}!</h2>
      <p>Hi {name},</p>
      <p>Click the link below to log in to your RFBooking account:</p>
      <p style="margin: 30px 0;">
        <a href="{verify_url}" style="background-color: #FF6B35; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
          Log In to RFBooking
        </a>
      </p>
      <p>This link will expire in {self.settings.security.magic_link_minutes} minutes.</p>
      <p>If you didn't request this login link, you can safely ignore this email.</p>
      <p style="color: #666; font-size: 12px; margin-top: 40px;">
        This is an automated message from RFBooking System.
      </p>
    </div>
</body>
</html>
"""

        text = f"""
Welcome to {org_name}!

Hi {name},

Click the link below to log in to your RFBooking account:

{verify_url}

This link will expire in {self.settings.security.magic_link_minutes} minutes.

If you didn't request this login link, you can safely ignore this email.
"""

        return await self.send_email(
            to=email,
            subject=f"Your login link for {org_name} - RFBooking",
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
        org_name = self.settings.organization.name
        equipment_name = booking_data.get('equipment_name', 'N/A')
        location = booking_data.get('equipment_location', '')
        description = booking_data.get('description', '')
        manager_names = booking_data.get('manager_names', '')
        manager_emails = booking_data.get('manager_emails', '')

        # Build location row if exists
        location_row = f'''
              <tr>
                <td style="padding: 8px 0; color: #6b8278; font-weight: 600;">Location:</td>
                <td style="padding: 8px 0; color: #2d3e35;">{location}</td>
              </tr>
        ''' if location else ''

        # Build manager contact info
        manager_info = ''
        if manager_names:
            names = manager_names.split(', ') if isinstance(manager_names, str) else manager_names
            emails = manager_emails.split(', ') if isinstance(manager_emails, str) else (manager_emails or [])
            manager_items = []
            for idx, mgr_name in enumerate(names):
                mgr_email = emails[idx] if idx < len(emails) else ''
                if mgr_email:
                    manager_items.append(f'<div style="margin: 5px 0;">{mgr_name} - <a href="mailto:{mgr_email}" style="color: #4a7c59;">{mgr_email}</a></div>')
                else:
                    manager_items.append(f'<div style="margin: 5px 0;">{mgr_name}</div>')
            manager_info = ''.join(manager_items)
        else:
            manager_info = '<div style="color: #666;">No manager assigned</div>'

        # Build notes section if exists
        notes_section = f'''
          <div style="margin: 20px 0;">
            <h4 style="color: #3d5a4a; margin-bottom: 10px; font-size: 14px;">Notes:</h4>
            <div style="background-color: #fafbfa; padding: 12px; border-radius: 4px; color: #2d3e35; border: 1px solid #e5ebe7;">
              {description}
            </div>
          </div>
        ''' if description else ''

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @media only screen and (max-width: 600px) {{
          .booking-table tr {{ display: block !important; margin-bottom: 15px !important; }}
          .booking-table td {{ display: block !important; width: 100% !important; padding: 4px 0 !important; }}
          .booking-table td:first-child {{ padding-bottom: 2px !important; }}
        }}
    </style>
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto; background-color: #f9faf9; padding: 20px;">
        <div style="background-color: #ffffff; border-radius: 8px; padding: 30px; border-top: 4px solid #5a8a6b;">
          <h2 style="color: #3d5a4a; margin-top: 0; margin-bottom: 10px;">Booking Confirmed</h2>
          <p style="color: #6b8278; margin-bottom: 25px;">Your equipment booking has been successfully created.</p>

          <div style="background-color: #f4f8f6; border-left: 3px solid #5a8a6b; padding: 15px; margin: 20px 0;">
            <h3 style="color: #3d5a4a; margin-top: 0; margin-bottom: 15px; font-size: 16px;">Booking Details</h3>

            <table class="booking-table" style="width: 100%; border-collapse: collapse;">
              <tr>
                <td style="padding: 8px 0; color: #6b8278; font-weight: 600; width: 140px;">Equipment:</td>
                <td style="padding: 8px 0; color: #2d3e35;">{equipment_name}</td>
              </tr>
              {location_row}
              <tr>
                <td style="padding: 8px 0; color: #6b8278; font-weight: 600;">Start Date:</td>
                <td style="padding: 8px 0; color: #2d3e35;">{booking_data.get('start_date')} at {booking_data.get('start_time')}</td>
              </tr>
              <tr>
                <td style="padding: 8px 0; color: #6b8278; font-weight: 600;">End Date:</td>
                <td style="padding: 8px 0; color: #2d3e35;">{booking_data.get('end_date')} at {booking_data.get('end_time')}</td>
              </tr>
            </table>
          </div>

          {notes_section}

          <div style="margin: 20px 0;">
            <h4 style="color: #3d5a4a; margin-bottom: 10px; font-size: 14px;">Equipment Manager(s):</h4>
            <div style="color: #2d3e35;">
              {manager_info}
            </div>
          </div>

          <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5ebe7;">
            <p style="color: #6b8278; font-size: 13px; margin: 0;">
              You will receive a reminder 24 hours before your booking starts.
            </p>
          </div>
        </div>

        <div style="text-align: center; margin-top: 20px; color: #8a9a91; font-size: 12px;">
          RFBooking System - {org_name}
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"Booking Confirmed - {equipment_name}",
            html=html,
        )

    async def send_booking_reminder(
        self,
        email: str,
        name: str,
        booking_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send booking reminder email."""
        equipment_name = booking_data.get('equipment_name', 'N/A')
        location = booking_data.get('equipment_location', '')
        description = booking_data.get('description', '')
        manager_names = booking_data.get('manager_names', '')
        manager_emails = booking_data.get('manager_emails', '')

        # Build location row if exists
        location_row = f'<li><strong>Location:</strong> {location}</li>' if location else ''

        # Build manager contact info
        manager_info = ''
        if manager_names:
            names = manager_names.split(', ') if isinstance(manager_names, str) else manager_names
            emails = manager_emails.split(', ') if isinstance(manager_emails, str) else (manager_emails or [])
            manager_info = '<p><strong>Equipment Manager(s):</strong></p><ul>'
            for idx, mgr_name in enumerate(names):
                mgr_email = emails[idx] if idx < len(emails) else ''
                manager_info += f'<li>{mgr_name}{" - " + mgr_email if mgr_email else ""}</li>'
            manager_info += '</ul>'

        # Build notes section if exists
        notes_section = f'<p><strong>Notes:</strong> {description}</p>' if description else ''

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>Booking Reminder</h2>
      <p>Hi {name},</p>
      <p>This is a reminder that your booking is coming up:</p>
      <ul>
        <li><strong>Equipment:</strong> {equipment_name}</li>
        <li><strong>Date:</strong> {booking_data.get('start_date')}</li>
        <li><strong>Time:</strong> {booking_data.get('start_time')} - {booking_data.get('end_time')}</li>
        {location_row}
      </ul>
      {notes_section}
      {manager_info}
      <p>See you soon!</p>
      <p style="color: #666; font-size: 12px; margin-top: 40px;">
        This is an automated message from RFBooking System.
      </p>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"Booking Reminder - {equipment_name} on {booking_data.get('start_date')}",
            html=html,
        )

    async def send_booking_cancellation(
        self,
        email: str,
        name: str,
        booking_data: Dict[str, Any],
        cancelled_by_manager: bool = False,
        canceller_name: str = '',
        canceller_email: str = '',
    ) -> Dict[str, Any]:
        """Send booking cancellation email."""
        org_name = self.settings.organization.name
        equipment_name = booking_data.get('equipment_name', 'N/A')
        location = booking_data.get('equipment_location', '')
        description = booking_data.get('description', '')
        manager_names = booking_data.get('manager_names', '')
        manager_emails = booking_data.get('manager_emails', '')

        # Build location row if exists
        location_row = f'''
              <tr>
                <td style="padding: 8px 0; color: #a66; font-weight: 600;">Location:</td>
                <td style="padding: 8px 0; color: #3e2d2d;">{location}</td>
              </tr>
        ''' if location else ''

        # Build notes row if exists
        notes_row = f'''
              <tr>
                <td style="padding: 8px 0; color: #a66; font-weight: 600; vertical-align: top;">Notes:</td>
                <td style="padding: 8px 0; color: #3e2d2d;">{description}</td>
              </tr>
        ''' if description else ''

        # Build canceller info if cancelled by manager
        canceller_info = ''
        if cancelled_by_manager and canceller_name:
            canceller_info = f'''
          <div style="background-color: #fff5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0 0 10px 0; color: #8b3a3a; font-weight: 600;">Cancelled By:</p>
            <div style="margin: 5px 0;">{canceller_name}{' - <a href="mailto:' + canceller_email + '" style="color: #c45454;">' + canceller_email + '</a>' if canceller_email else ''}</div>
          </div>
            '''
            subtitle = 'Your equipment booking has been cancelled by a manager.'
        else:
            subtitle = 'Your booking has been successfully cancelled.'

        # Build manager contact info for user cancellation confirmation
        manager_info = ''
        if not cancelled_by_manager and manager_names:
            names = manager_names.split(', ') if isinstance(manager_names, str) else manager_names
            emails_list = manager_emails.split(', ') if isinstance(manager_emails, str) else (manager_emails or [])
            manager_items = []
            for idx, mgr_name in enumerate(names):
                mgr_email = emails_list[idx] if idx < len(emails_list) else ''
                if mgr_email:
                    manager_items.append(f'<div style="margin: 5px 0;">{mgr_name} - <a href="mailto:{mgr_email}" style="color: #c45454;">{mgr_email}</a></div>')
                else:
                    manager_items.append(f'<div style="margin: 5px 0;">{mgr_name}</div>')
            manager_info = f'''
          <div style="background-color: #f4f8f6; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0 0 10px 0; color: #3d5a4a; font-weight: 600;">Equipment Managers:</p>
            {''.join(manager_items)}
          </div>
            '''

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @media only screen and (max-width: 600px) {{
          .booking-table tr {{ display: block !important; margin-bottom: 15px !important; }}
          .booking-table td {{ display: block !important; width: 100% !important; padding: 4px 0 !important; }}
          .booking-table td:first-child {{ padding-bottom: 2px !important; }}
        }}
    </style>
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto; background-color: #faf9f9; padding: 20px;">
        <div style="background-color: #ffffff; border-radius: 8px; padding: 30px; border-top: 4px solid #c45454;">
          <h2 style="color: #8b3a3a; margin-top: 0; margin-bottom: 10px;">Booking Cancelled</h2>
          <p style="color: #a66; margin-bottom: 25px;">{subtitle}</p>

          <div style="background-color: #fff5f5; border-left: 3px solid #c45454; padding: 15px; margin: 20px 0;">
            <h3 style="color: #8b3a3a; margin-top: 0; margin-bottom: 15px; font-size: 16px;">Cancelled Booking Details</h3>

            <table class="booking-table" style="width: 100%; border-collapse: collapse;">
              <tr>
                <td style="padding: 8px 0; color: #a66; font-weight: 600; width: 140px;">Equipment:</td>
                <td style="padding: 8px 0; color: #3e2d2d;">{equipment_name}</td>
              </tr>
              {location_row}
              <tr>
                <td style="padding: 8px 0; color: #a66; font-weight: 600;">Start Date:</td>
                <td style="padding: 8px 0; color: #3e2d2d;">{booking_data.get('start_date')}</td>
              </tr>
              <tr>
                <td style="padding: 8px 0; color: #a66; font-weight: 600;">End Date:</td>
                <td style="padding: 8px 0; color: #3e2d2d;">{booking_data.get('end_date')}</td>
              </tr>
              <tr>
                <td style="padding: 8px 0; color: #a66; font-weight: 600;">Time:</td>
                <td style="padding: 8px 0; color: #3e2d2d;">{booking_data.get('start_time')} - {booking_data.get('end_time')}</td>
              </tr>
              {notes_row}
            </table>
          </div>

          {canceller_info}
          {manager_info}

          <p style="color: #666; font-size: 14px; margin: 20px 0 0 0;">
            {'If you have any questions about this cancellation, please contact the manager listed above or your administrator.' if cancelled_by_manager else 'The equipment is now available for rebooking during this time slot. If you need to make a new booking, please visit the dashboard.'}
          </p>
        </div>

        <div style="text-align: center; margin-top: 20px; color: #999; font-size: 12px;">
          <p>This is an automated message from RFBooking System</p>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"Booking Cancelled - {equipment_name}",
            html=html,
        )

    async def send_manager_new_booking(
        self,
        email: str,
        name: str,
        booking_data: Dict[str, Any],
        booker_name: str,
        booker_email: str = '',
    ) -> Dict[str, Any]:
        """Send notification to manager about new booking."""
        org_name = self.settings.organization.name
        equipment_name = booking_data.get('equipment_name', 'N/A')
        location = booking_data.get('equipment_location', '')
        description = booking_data.get('description', '')

        # Build location row if exists
        location_row = f'''
              <tr>
                <td style="padding: 8px 0; color: #6b8278; font-weight: 600;">Location:</td>
                <td style="padding: 8px 0; color: #2d3e35;">{location}</td>
              </tr>
        ''' if location else ''

        # Build notes section if exists
        notes_section = f'''
          <div style="margin: 20px 0;">
            <h4 style="color: #3d5a4a; margin-bottom: 10px; font-size: 14px;">Notes:</h4>
            <div style="background-color: #fafbfa; padding: 12px; border-radius: 4px; color: #2d3e35; border: 1px solid #e5ebe7;">
              {description}
            </div>
          </div>
        ''' if description else ''

        # Build booker info
        booker_info = f'{booker_name}'
        if booker_email:
            booker_info = f'{booker_name} (<a href="mailto:{booker_email}" style="color: #4a7c59;">{booker_email}</a>)'

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @media only screen and (max-width: 600px) {{
          .booking-table tr {{ display: block !important; margin-bottom: 15px !important; }}
          .booking-table td {{ display: block !important; width: 100% !important; padding: 4px 0 !important; }}
          .booking-table td:first-child {{ padding-bottom: 2px !important; }}
        }}
    </style>
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto; background-color: #f9faf9; padding: 20px;">
        <div style="background-color: #ffffff; border-radius: 8px; padding: 30px; border-top: 4px solid #5a8a6b;">
          <h2 style="color: #3d5a4a; margin-top: 0; margin-bottom: 10px;">New Booking Created</h2>
          <p style="color: #6b8278; margin-bottom: 25px;">A new booking has been made for equipment you manage.</p>

          <div style="background-color: #f4f8f6; border-left: 3px solid #5a8a6b; padding: 15px; margin: 20px 0;">
            <h3 style="color: #3d5a4a; margin-top: 0; margin-bottom: 15px; font-size: 16px;">Booking Details</h3>

            <table class="booking-table" style="width: 100%; border-collapse: collapse;">
              <tr>
                <td style="padding: 8px 0; color: #6b8278; font-weight: 600; width: 140px;">Equipment:</td>
                <td style="padding: 8px 0; color: #2d3e35;">{equipment_name}</td>
              </tr>
              {location_row}
              <tr>
                <td style="padding: 8px 0; color: #6b8278; font-weight: 600;">Start Date:</td>
                <td style="padding: 8px 0; color: #2d3e35;">{booking_data.get('start_date')} at {booking_data.get('start_time')}</td>
              </tr>
              <tr>
                <td style="padding: 8px 0; color: #6b8278; font-weight: 600;">End Date:</td>
                <td style="padding: 8px 0; color: #2d3e35;">{booking_data.get('end_date')} at {booking_data.get('end_time')}</td>
              </tr>
              <tr>
                <td style="padding: 8px 0; color: #6b8278; font-weight: 600;">Booked By:</td>
                <td style="padding: 8px 0; color: #2d3e35;">{booker_info}</td>
              </tr>
              <tr>
                <td style="padding: 8px 0; color: #6b8278; font-weight: 600;">Manager:</td>
                <td style="padding: 8px 0; color: #2d3e35;">{name} (<a href="mailto:{email}" style="color: #4a7c59;">{email}</a>)</td>
              </tr>
            </table>
          </div>

          {notes_section}

          <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5ebe7;">
            <p style="color: #6b8278; font-size: 13px; margin: 0;">
              You will receive a reminder 24 hours before this booking starts.
            </p>
          </div>
        </div>

        <div style="text-align: center; margin-top: 20px; color: #8a9a91; font-size: 12px;">
          RFBooking System - {org_name}
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"New Booking - {equipment_name}",
            html=html,
        )

    async def send_short_notice_cancellation(
        self,
        email: str,
        name: str,
        booking_data: Dict[str, Any],
        booker_name: str,
        booker_email: str = '',
    ) -> Dict[str, Any]:
        """Send alert to manager about short-notice cancellation."""
        settings = get_settings()
        equipment_name = booking_data.get('equipment_name', 'N/A')
        location = booking_data.get('equipment_location', '')
        description = booking_data.get('description', '')

        # Build location row if exists
        location_row = f'<li><strong>Location:</strong> {location}</li>' if location else ''

        # Build user info
        user_info = booker_name
        if booker_email:
            user_info = f'{booker_name} ({booker_email})'

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>Booking Cancelled by User</h2>
      <p>Hi {name},</p>
      <p>{booker_name} has cancelled their booking for equipment you manage:</p>
      <ul>
        <li><strong>Equipment:</strong> {equipment_name}</li>
        <li><strong>User:</strong> {user_info}</li>
        <li><strong>Date:</strong> {booking_data.get('start_date')} to {booking_data.get('end_date')}</li>
        <li><strong>Time:</strong> {booking_data.get('start_time')} - {booking_data.get('end_time')}</li>
        {location_row}
      </ul>
      {f'<p><strong>Original Notes:</strong> {description}</p>' if description else ''}
      <p><strong>Note:</strong> This booking was cancelled within {settings.booking.short_notice_days} days of the scheduled start date.</p>
      <p>The equipment is now available for rebooking during this time slot.</p>
      <p style="color: #666; font-size: 12px; margin-top: 40px;">
        This is an automated message from RFBooking System.
      </p>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"User Cancelled Booking - {equipment_name} on {booking_data.get('start_date')}",
            html=html,
        )

    async def send_calibration_reminder(
        self,
        email: str,
        name: str,
        equipment_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send calibration reminder to equipment manager."""
        equipment_name = equipment_data.get('name', 'N/A')
        location = equipment_data.get('location', '')
        calibration_date = equipment_data.get('next_calibration_date', 'N/A')

        # Calculate days until calibration
        days_remaining = equipment_data.get('days_remaining', '')
        days_info = f'<li><strong>Days Remaining:</strong> {days_remaining} days</li>' if days_remaining else ''

        # Build location row if exists
        location_row = f'<li><strong>Location:</strong> {location}</li>' if location else ''

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>Equipment Calibration Reminder</h2>
      <p>Hi {name},</p>
      <p>A piece of equipment you manage needs calibration soon:</p>
      <ul>
        <li><strong>Equipment:</strong> {equipment_name}</li>
        <li><strong>Calibration Date:</strong> {calibration_date}</li>
        {days_info}
        {location_row}
      </ul>
      <p>Please schedule the calibration in advance to avoid service interruptions.</p>
      <p style="color: #666; font-size: 12px; margin-top: 40px;">
        This is an automated message from RFBooking System.
      </p>
    </div>
</body>
</html>
"""

        return await self.send_email(
            to=email,
            subject=f"Calibration Reminder - {equipment_name}",
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
        org_name = self.settings.organization.name

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
                    <h3 style="color: #FF6B35; margin-bottom: 10px;">{eq_name}</h3>
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
                    <h3 style="color: #FF6B35; margin-bottom: 10px;">{eq_name}</h3>
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
</head>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #FF6B35 0%, #e55a28 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">Weekly Equipment Report</h2>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">{week_start} - {week_end}</p>
        </div>
        <div style="padding: 20px; background: #fff;">
            <p>Hi {name},</p>
            <p>Here's your weekly summary of upcoming equipment bookings:</p>

            <div style="background: #f8fafc; padding: 15px; margin-bottom: 20px; border-radius: 6px;">
                <strong>Summary:</strong> {total_bookings} booking(s) across {len(equipment_bookings)} equipment item(s)
            </div>

            {equipment_sections}

            <p>You can view and manage all bookings in the dashboard.</p>
        </div>
        <div style="text-align: center; margin-top: 20px; color: #999; font-size: 12px;">
            <p>RFBooking System - {org_name}</p>
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
