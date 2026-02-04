import smtplib
import logging
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("EmailService")

# --- Configuration (Load from Environment) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# ברירת מחדל: אם לא מוגדר בשרת, המערכת תודיע בלוגים
SENDER_EMAIL = os.getenv("MAIL_USERNAME", "noreply@leadflow.ai")
SENDER_PASSWORD = os.getenv("MAIL_PASSWORD", "")

def send_otp_email(to_email: str, otp_code: str):
    """
    Sends an OTP code via SMTP (Gmail/Outlook/AWS SES).
    This function is blocking, so it should be run in BackgroundTasks.
    """
    if not SENDER_PASSWORD:
        logger.warning("⚠️ MAIL_PASSWORD not set! OTP will strictly be logged only.")
        logger.info(f"CONFIDENTIAL OTP for {to_email}: {otp_code}")
        return

    try:
        # Create the email content
        subject = f"Your Login Code: {otp_code}"
        body = f"""
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

        msg = MIMEMultipart()
        msg["From"] = f"LeadFlow AI <{SENDER_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        # Connect to Server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Secure the connection
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        # Send
        server.send_message(msg)
        server.quit()
        
        logger.info(f"✅ OTP Email sent successfully to {to_email}")

    except Exception as e:
        logger.error(f"❌ Failed to send email to {to_email}: {e}")
