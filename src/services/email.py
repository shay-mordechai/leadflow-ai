# src/services/email.py
import os
import logging
from typing import List, Optional
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from src.config import settings  # Pulling configuration from SSM via Pydantic

logger = logging.getLogger("EmailService")

# --- Configuration Loading ---
# We retrieve values directly from our settings object (populated by SSM)
MAIL_USERNAME = settings.MAIL_USERNAME
MAIL_PASSWORD = settings.MAIL_PASSWORD
MAIL_FROM = settings.MAIL_FROM
MAIL_PORT = settings.MAIL_PORT
MAIL_SERVER = settings.MAIL_SERVER

# Check if credentials exist to avoid runtime crashes
USE_CREDENTIALS = bool(MAIL_USERNAME and MAIL_PASSWORD)

if not USE_CREDENTIALS:
    logger.warning("⚠️ MAIL_USERNAME or MAIL_PASSWORD missing in SSM. Emails will NOT be sent (Log only).")

# FastAPI-Mail Configuration Object
# We only initialize this if credentials exist, otherwise FastMail might raise validation errors on init
conf = None
if USE_CREDENTIALS:
    conf = ConnectionConfig(
        MAIL_USERNAME=MAIL_USERNAME,
        MAIL_PASSWORD=MAIL_PASSWORD,
        MAIL_FROM=MAIL_FROM,
        MAIL_PORT=MAIL_PORT,
        MAIL_SERVER=MAIL_SERVER,
        MAIL_STARTTLS=True,      # Typical for Gmail/Outlook (Port 587)
        MAIL_SSL_TLS=False,      # Typical for Port 465
        USE_CREDENTIALS=USE_CREDENTIALS,
        VALIDATE_CERTS=True
    )

class EmailService:
    """
    Asynchronous email service using fastapi-mail.
    Handles OTPs and File Attachments (PDFs).
    """

    async def send_otp_email(self, to_email: EmailStr, otp_code: str):
        """
        Sends an OTP code asynchronously.
        """
        if not USE_CREDENTIALS or not conf:
            logger.info(f"🛑 [MOCK EMAIL] To: {to_email} | OTP: {otp_code}")
            return

        # HTML Template for the OTP
        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #2c3e50;">LeadFlow AI Security</h2>
            <p>Hello,</p>
            <p>Please use the following code to complete your login:</p>
            <h1 style="color: #2980b9; letter-spacing: 5px; background: #ecf0f1; padding: 10px; display: inline-block;">{otp_code}</h1>
            <p>This code is valid for 5 minutes.</p>
            <p style="font-size: 12px; color: #7f8c8d;">If you did not request this, please ignore this email.</p>
          </body>
        </html>
        """

        try:
            message = MessageSchema(
                subject=f"Your Login Code: {otp_code}",
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
        Sends a payment receipt or meeting summary with PDF attachment.
        """
        if not USE_CREDENTIALS or not conf:
            logger.info(f"🛑 [MOCK RECEIPT] To: {to_email} | File: {pdf_path}")
            return
            
        if not os.path.exists(pdf_path):
            logger.error(f"❌ PDF file not found: {pdf_path}")
            return

        html_content = """
        <p>Hello,</p>
        <p>Please find your automated summary/receipt attached.</p>
        <p>Best regards,<br>LeadFlow AI</p>
        """

        try:
            message = MessageSchema(
                subject="Your Document from LeadFlow AI",
                recipients=[to_email],
                body=html_content,
                subtype=MessageType.html,
                attachments=[pdf_path] # Auto-handles MIME types
            )

            fm = FastMail(conf)
            await fm.send_message(message)
            logger.info(f"✅ Receipt sent successfully to {to_email}")

        except Exception as e:
            logger.error(f"❌ Failed to send receipt: {e}")

# Singleton instance to be imported elsewhere
email_service = EmailService()