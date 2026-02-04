# src/services/whatsapp_adapter.py
import os
import logging
import requests
import uuid
from sqlalchemy.orm import Session
from src.database.models import User, MediaInteraction, ProcessingStatus
from src.config import settings

logger = logging.getLogger(__name__)

# --- Configuration: Load from .env ---
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
API_VERSION = "v17.0"

class WhatsAppAdapter:
    """
    WhatsApp Adapter.
    Handles message sending and media downloading.
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
            logger.error(f"🔥 Failed to send WhatsApp via Meta: {e}")
            return False

    def download_media(self, media_url: str) -> str:
        """
        Downloads media (audio/image) from a URL to local storage.
        Returns the local file path.
        """
        try:
            # Generate unique filename
            filename = f"{uuid.uuid4()}.ogg"
            save_path = f"storage/audio/{filename}"
            
            # Ensure directory exists
            os.makedirs("storage/audio", exist_ok=True)

            # Professional English Comment:
            # If using Twilio, basic auth might be needed: auth=(settings.TWILIO_SID, settings.TWILIO_TOKEN)
            # For public URLs (Meta sometimes), standard get works.
            response = requests.get(media_url)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"📥 Media downloaded to {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"❌ Error downloading media: {e}")
            return None

# Singleton Instance
whatsapp_adapter = WhatsAppAdapter()