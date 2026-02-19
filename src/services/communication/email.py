# src/services/communication/email.py
import os
import logging
from typing import List, Optional
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from src.config import settings

logger = logging.getLogger("EmailService")

class EmailService:
    """
    Asynchronous email service handler using fastapi-mail.
    Supports OTP delivery and automated PDF attachments.
    Robust handling for Brevo/Sendinblue and Gmail.
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

    async def send_otp_email(self, to_email: EmailStr, otp_code: str):
        """
        Sends a security OTP code for MFA verification.
        """
        # Fallback to logging if SMTP is not configured
        if not self.conf:
            logger.info(f"🛑 [MOCK EMAIL] To: {to_email} | OTP: {otp_code}")
            return

        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <div style="max-width: 500px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                <h2 style="color: #4F46E5; text-align: center;">LeadFlow AI Security</h2>
                <p>Hello,</p>
                <p>Please use the following verification code to access your account:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; background: #F3F4F6; padding: 15px 25px; border-radius: 8px; color: #111827;">
                        {otp_code}
                    </span>
                </div>
                <p>This code is valid for <b>5 minutes</b>.</p>
            </div>
          </body>
        </html>
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
            logger.info(f"✅ OTP Email sent successfully to {to_email}")

        except Exception as e:
            logger.error(f"❌ Failed to send OTP email: {e}")

    async def send_payment_receipt(self, to_email: EmailStr, pdf_path: str):
        """
        Sends the generated PDF invoice to the user after a successful upgrade.
        """
        if not self.conf:
            logger.info(f"🛑 [MOCK RECEIPT] To: {to_email} | File: {pdf_path}")
            return
            
        if not os.path.exists(pdf_path):
            logger.error(f"❌ Attachment not found: {pdf_path}")
            return

        html_content = """
        <html>
          <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #eee; padding: 30px; border-radius: 10px;">
                <h2 style="color: #4F46E5;">Welcome to MyLeads AI PRO! 🚀</h2>
                <p>Your payment was successful and your account has been instantly upgraded.</p>
                <p>You now have full access to our advanced AI Sales Agent features and unlimited lead processing.</p>
                <br>
                <p>Attached to this email is your official PDF tax invoice for your accounting records.</p>
                <br>
                <p>If you have any questions, simply reply to this email.</p>
                <p>Best regards,<br><b>The MyLeads AI Team</b></p>
            </div>
          </body>
        </html>
        """

        try:
            message = MessageSchema(
                subject="Your MyLeads AI Invoice & Account Upgrade",
                recipients=[to_email],
                body=html_content,
                subtype=MessageType.html,
                attachments=[pdf_path]
            )

            fm = FastMail(self.conf)
            await fm.send_message(message)
            logger.info(f"✅ Invoice PDF sent successfully to {to_email}")

        except Exception as e:
            logger.error(f"❌ Failed to send invoice email: {e}")

# Singleton Instance
email_service = EmailService()

# --- BACKWARD COMPATIBILITY WRAPPER ---
# This function allows 'from ... import send_otp_email' to keep working
async def send_otp_email(to_email: str, otp_code: str):
    await email_service.send_otp_email(to_email, otp_code)