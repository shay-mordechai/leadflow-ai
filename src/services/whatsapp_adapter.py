# src/services/whatsapp_adapter.py
import os
import logging
import requests
from sqlalchemy.orm import Session
from src.database.models import User, MediaInteraction, ProcessingStatus

logger = logging.getLogger(__name__)

# --- Configuration: Load from .env ---
# These match the variables you provided in your prompt
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
API_VERSION = "v17.0"

class WhatsAppAdapter:
    """
    WhatsApp Adapter (Official Meta Cloud API).
    Handles message ingestion (Webhook) and sending outbound messages via Facebook Graph API.
    """

    def send_message(self, to_phone: str, text: str):
        """
        Sends a WhatsApp message using the Official Meta Graph API.
        """
        if not META_ACCESS_TOKEN or not PHONE_ID:
            logger.error("❌ Meta credentials missing in .env")
            return False

        url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_ID}/messages"
        
        headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        # Meta expects the object to be 'messaging_product': 'whatsapp'
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": text}
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"🚀 Sent WhatsApp (Meta) to {to_phone}: {text[:30]}...")
            return True
        except requests.exceptions.RequestException as e:
            # Enhanced error logging for Meta responses
            error_msg = "Unknown Error"
            if response is not None:
                try:
                    error_msg = response.json()
                except:
                    error_msg = response.text
            
            logger.error(f"🔥 Failed to send WhatsApp via Meta: {e}")
            logger.error(f"Meta API Response: {error_msg}")
            return False

    def process_incoming_webhook(self, db: Session, user_id: str, sender_phone: str, message_text: str, media_url: str = None):
        """
        Ingests the message immediately to the DB.
        This remains the same regardless of the provider (Meta vs GreenAPI),
        as the logic is internal to our system.
        """
        # 1. Lookup User (Business Owner)
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            logger.warning(f"⚠️ Webhook received for unknown User ID: {user_id}")
            return False

        logger.info(f"📩 New message for User: {user.business_name}")

        # 2. Save job to DB for the Worker
        new_interaction = MediaInteraction(
            user_id=user.id,
            sender_phone=sender_phone,
            media_type="AUDIO" if media_url else "TEXT",
            message_text=message_text,
            file_path=media_url, 
            status=ProcessingStatus.PENDING 
        )
        
        db.add(new_interaction)
        db.commit()
        
        logger.info(f"✅ Job queued: {new_interaction.id}. Worker is watching.")
        return True

# Singleton Instance
whatsapp_adapter = WhatsAppAdapter()