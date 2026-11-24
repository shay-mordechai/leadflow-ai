# src/services/communication/email.py
import hashlib
import logging
import os
import uuid
from html import escape

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr

from src.config import settings

logger = logging.getLogger("EmailService")


def _otp_thread_headers(to_email: str) -> dict[str, str]:
    """Build deterministic RFC 5322 headers so all OTP emails for a user group into one thread."""
    normalized = str(to_email).strip().lower().encode("utf-8")
    thread_digest = hashlib.sha256(normalized).hexdigest()[:20]
    root_msg_id = f"<otp-thread-{thread_digest}@my-leads.app>"
    current_msg_id = f"<otp-{uuid.uuid4().hex}@my-leads.app>"
    return {
        "Message-ID": current_msg_id,
        "In-Reply-To": root_msg_id,
        "References": root_msg_id,
    }


class EmailService:
    """
    Asynchronous email service handler using fastapi-mail.
    Supports OTP delivery, PDFs, and Admin Crash Alerts.
    """

    def __init__(self):
        self.conf = self._create_config()

    def _create_config(self) -> ConnectionConfig | None:
        """
        Safely creates the connection configuration.
        Returns None if credentials are missing.
        """
        username = settings.MAIL_USERNAME
        password = settings.MAIL_PASSWORD

        if not username or not password:
            logger.warning(
                "⚠ SMTP Credentials missing in Config. Emails will NOT be sent (Log only)."
            )
            return None

        try:
            return ConnectionConfig(
                MAIL_USERNAME=username,
                MAIL_PASSWORD=password,
                MAIL_FROM=settings.MAIL_FROM or "noreply@my-leads.app",
                MAIL_FROM_NAME="MY-Leads AI",
                MAIL_PORT=int(settings.MAIL_PORT or 587),
                MAIL_SERVER=settings.MAIL_SERVER or "smtp-relay.brevo.com",
                MAIL_STARTTLS=True,
                MAIL_SSL_TLS=False,
                USE_CREDENTIALS=True,
                VALIDATE_CERTS=True,
            )
        except Exception as e:
            logger.error(f"❌ Failed to configure SMTP: {e}")
            return None

    async def send_password_reset_email(self, to_email: EmailStr, otp_code: str):
        if not self.conf:
            logger.info(
                "🛑 [MOCK RESET EMAIL] Credentials are not configured; reset email not sent."
            )
            return

        html_content = f"""
        <h3>MY-Leads AI Password Reset</h3>
        <p>Hello,</p>
        <p>We received a request to reset your password. Use the following code to proceed:</p>
        <h2 style='color: #4F46E5; letter-spacing: 2px;'>{otp_code}</h2>
        <p>This code is valid for 5 minutes. If you didn't request this, please ignore this email.</p>
        """

        try:
            message = MessageSchema(
                subject="MY-Leads AI Password Reset Code",
                recipients=[to_email],
                body=html_content,
                subtype=MessageType.html,
                headers=_otp_thread_headers(str(to_email)),
            )
            fm = FastMail(self.conf)
            await fm.send_message(message)
        except Exception as e:
            logger.error(f"❌ Failed to send password reset email: {e}")

    async def send_error_alert_email(
        self, error_summary: str, stack_trace: str, request_info: dict
    ):
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
                subtype=MessageType.html,
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
        <h3>MY-Leads AI Login Code</h3>
        <p>Your one-time login code is:</p>
        <h2 style='color: #4F46E5; letter-spacing: 2px;'>{otp_code}</h2>
        <p>Please enter this code in your browser to complete your login. This code will expire in 5 minutes.</p>
        """

        try:
            message = MessageSchema(
                subject="MY-Leads AI Login Code",
                recipients=[to_email],
                body=html_content,
                subtype=MessageType.html,
                headers=_otp_thread_headers(str(to_email)),
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
        <p>Your MY-Leads AI account has been successfully upgraded. Attached is your official invoice/receipt.</p>
        <p>If you have any questions, feel free to reach out to our support team.</p>
        """

        try:
            message = MessageSchema(
                subject="Your MY-Leads AI Invoice & Account Upgrade",
                recipients=[to_email],
                body=html_content,
                subtype=MessageType.html,
                attachments=[pdf_path],
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
