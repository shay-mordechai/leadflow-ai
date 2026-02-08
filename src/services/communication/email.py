# src/services/email.py
import os
import logging
from typing import List, Optional
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from src.config import settings

logger = logging.getLogger("EmailService")

# --- Configuration Loading ---
MAIL_USERNAME = settings.MAIL_USERNAME
MAIL_PASSWORD = settings.MAIL_PASSWORD
MAIL_FROM = settings.MAIL_FROM or "noreply@leadflow.ai"
MAIL_PORT = int(settings.MAIL_PORT) if settings.MAIL_PORT else 587
MAIL_SERVER = settings.MAIL_SERVER

# Safety Check: Verify if SMTP credentials exist to prevent runtime crashes
USE_CREDENTIALS = bool(MAIL_USERNAME and MAIL_PASSWORD)

if not USE_CREDENTIALS:
    logger.warning("⚠️ SMTP Credentials missing. Emails will NOT be sent (Log only).")

# FastAPI-Mail Connection Object
conf = None
if USE_CREDENTIALS:
    conf = ConnectionConfig(
        MAIL_USERNAME=MAIL_USERNAME,
        MAIL_PASSWORD=MAIL_PASSWORD,
        MAIL_FROM=MAIL_FROM,
        MAIL_PORT=MAIL_PORT,
        MAIL_SERVER=MAIL_SERVER,
        MAIL_STARTTLS=True,      # Standard for Port 587 (Gmail/Outlook)
        MAIL_SSL_TLS=False,      # Standard for Port 465
        USE_CREDENTIALS=USE_CREDENTIALS,
        VALIDATE_CERTS=True
    )

class EmailService:
    """
    Asynchronous email service handler using fastapi-mail.
    Supports OTP delivery and automated PDF attachments.
    """

    async def send_otp_email(self, to_email: EmailStr, otp_code: str):
        """
        Sends a security OTP code for MFA verification.
        """
        # Fallback to logging if SMTP is not configured
        if not USE_CREDENTIALS or not conf:
            logger.info(f"🛑 [MOCK EMAIL] To: {to_email} | OTP: {otp_code}")
            return

        # Modern HTML Template for OTP
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
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 11px; color: #6B7280; text-align: center;">
                    If you did not request this code, please ignore this email or contact support.
                </p>
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

            fm = FastMail(conf)
            await fm.send_message(message)
            logger.info(f"✅ OTP Email sent successfully to {to_email}")

        except Exception as e:
            logger.error(f"❌ Failed to send OTP email: {e}")

    async def send_payment_receipt(self, to_email: EmailStr, pdf_path: str):
        """
        Sends a payment receipt or summary with a PDF attachment.
        """
        if not USE_CREDENTIALS or not conf:
            logger.info(f"🛑 [MOCK RECEIPT] To: {to_email} | File: {pdf_path}")
            return
            
        if not os.path.exists(pdf_path):
            logger.error(f"❌ Attachment not found: {pdf_path}")
            return

        html_content = """
        <p>Hello,</p>
        <p>Your requested document (meeting summary or receipt) is attached to this email.</p>
        <p>Best regards,<br><b>LeadFlow AI Team</b></p>
        """

        try:
            message = MessageSchema(
                subject="Your Document from LeadFlow AI",
                recipients=[to_email],
                body=html_content,
                subtype=MessageType.html,
                attachments=[pdf_path]
            )

            fm = FastMail(conf)
            await fm.send_message(message)
            logger.info(f"✅ Receipt sent successfully to {to_email}")

        except Exception as e:
            logger.error(f"❌ Failed to send receipt: {e}")

# Singleton instance for easy import
email_service = EmailService()

# --- Hotfix Proxy Function ---
# This ensures that 'from src.services.communication.email import send_otp_email' works easily
async def send_otp_email(email: str, otp_code: str):
    await email_service.send_otp_email(email, otp_code)