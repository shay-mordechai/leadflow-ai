# src/services/communication/email.py
import os
import logging
from html import escape
from typing import List, Optional, Dict
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from src.config import settings

logger = logging.getLogger("EmailService")

class EmailService:
    """
    Asynchronous email service handler using fastapi-mail.
    Supports OTP delivery, PDFs, and Admin Crash Alerts.
    """
    def __init__(self):  
        self.conf = self._create_config()

    def _create_config(self) -> Optional[ConnectionConfig]:
        """
        Safely creates the connection configuration.
        Returns None if credentials are missing.
        """
        username = settings.MAIL_USERNAME
        password = settings.MAIL_PASSWORD
        
        if not username or not password:
            logger.warning("⚠️ SMTP Credentials missing in Config. Emails will NOT be sent (Log only).")
            return None

        try:
            return ConnectionConfig(
                MAIL_USERNAME=username,
                MAIL_PASSWORD=password,
                MAIL_FROM=settings.MAIL_FROM or "noreply@leadflow.ai",
                MAIL_PORT=int(settings.MAIL_PORT or 587),
                MAIL_SERVER=settings.MAIL_SERVER or "smtp-relay.brevo.com",
                MAIL_STARTTLS=True,
                MAIL_SSL_TLS=False,
                USE_CREDENTIALS=True,
                VALIDATE_CERTS=True
            )
        except Exception as e:
            logger.error(f"❌ Failed to configure SMTP: {e}")
            return None

    async def send_password_reset_email(self, to_email: EmailStr, otp_code: str):
        if not self.conf:
            logger.info("🛑 [MOCK RESET EMAIL] Credentials are not configured; reset email not sent.")
            return

        html_content = f"""
        <h3>LeadFlow AI Password Reset</h3>
        <p>Hello,</p>
        <p>We received a request to reset your password. Use the following code to proceed:</p>
        <h2 style='color: #4F46E5;'>{otp_code}</h2>
        <p>This code is valid for 5 minutes. If you didn't request this, please ignore this email.</p>
        """

        try:
            message = MessageSchema(
                subject="Password Reset Code",
                recipients=[to_email],
                body=html_content,
                subtype=MessageType.html
            )
            fm = FastMail(self.conf)
            await fm.send_message(message)
        except Exception as e:
            logger.error(f"❌ Failed to send password reset email: {e}")

    async def send_error_alert_email(self, error_summary: str, stack_trace: str, request_info: Dict):
        """
        Sends an emergency crash report to the System Administrator.
        """
        if not self.conf:
            logger.error(f"🛑 [MOCK CRASH ALERT] {error_summary}")
            return

        admin_email = getattr(settings, "ADMIN_EMAIL", None)
        if not admin_email:
            logger.warning("No ADMIN_EMAIL configured. Cannot send error alert.")
            return

        html_content = f"""
        <h3>🚨 LeadFlow System Crash Alert</h3>
        <p><b>Summary:</b> {escape(error_summary)}</p>
        <p><b>Request Info:</b></p>
        <pre>{escape(str(request_info))}</pre>
        <p><b>Stack Trace:</b></p>
        <pre style='background: #f4f4f4; padding: 10px; border: 1px solid #ddd;'>{escape(stack_trace)}</pre>
        """

        try:  
            message = MessageSchema(
                subject=f"🚨 LeadFlow Crash: {error_summary[:60]}",
                recipients=[admin_email],
                body=html_content,
                subtype=MessageType.html
            )

            fm = FastMail(self.conf)
            await fm.send_message(message)
            logger.info(f"✅ Crash report emailed to Admin ({admin_email})")
        except Exception as e:
            logger.error(f"❌ Failed to send crash email: {e}")

    async def send_otp_email(self, to_email: EmailStr, otp_code: str):
        if not self.conf:
            logger.info("🛑 [MOCK EMAIL] Credentials are not configured; login email not sent.")
            return

        html_content = f"""
        <h3>LeadFlow AI Login Code</h3>
        <p>Your one-time login code is:</p>
        <h2 style='color: #4F46E5; letter-spacing: 2px;'>{otp_code}</h2>
        <p>Please enter this code in your browser to complete your login. It will expire shortly.</p>
        """

        try:
            message = MessageSchema(
                subject=f"Login Code: {otp_code}",
                recipients=[to_email],
                body=html_content,
                subtype=MessageType.html
            )
            fm = FastMail(self.conf)
            await fm.send_message(message)
        except Exception as e:
            logger.error(f"❌ Failed to send OTP email: {e}")

    async def send_payment_receipt(self, to_email: EmailStr, pdf_path: str):
        if not self.conf:
            logger.info(f"🛑 [MOCK RECEIPT] To: {to_email} | File: {pdf_path}")
            return

        if not os.path.exists(pdf_path):
            logger.error(f"❌ Attachment not found: {pdf_path}")
            return

        html_content = """
        <h3>Thank you for your purchase!</h3>
        <p>Your LeadFlow AI account has been successfully upgraded. Attached is your official invoice/receipt.</p>
        <p>If you have any questions, feel free to reach out to our support team.</p>
        """

        try:
            message = MessageSchema(
                subject="Your LeadFlow AI Invoice & Account Upgrade",
                recipients=[to_email],
                body=html_content,
                subtype=MessageType.html,
                attachments=[pdf_path]
            )
            fm = FastMail(self.conf)
            await fm.send_message(message)
        except Exception as e:
            logger.error(f"❌ Failed to send invoice email: {e}")


# --- Singleton Instance Initialization ---
email_service = EmailService()

# --- Global Helper Wrappers for Backwards Compatibility ---
async def send_otp_email(to_email: str, otp_code: str):
    """Global wrapper for OTP delivery via global singleton."""
    await email_service.send_otp_email(to_email, otp_code)

async def send_password_reset_email(to_email: str, otp_code: str):
    """Global wrapper for password reset delivery via global singleton."""
    await email_service.send_password_reset_email(to_email, otp_code)