# src/services/communication/whatsapp.py
import logging
import requests
import uuid
import os
from src.config import settings

logger = logging.getLogger("WhatsAppAdapter")

class WhatsAppAdapter:
    """
    Handles interactions with the Meta (WhatsApp Cloud) API.
    Sending messages and downloading media.
    """
    def __init__(self):
        self.api_version = "v17.0"

    def send_message(self, to_phone: str, text: str):
        if not settings.META_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_ID:
            logger.error("❌ Meta credentials missing in settings. Cannot send WhatsApp.")
            return False

        url = f"https://graph.facebook.com/{self.api_version}/{settings.WHATSAPP_PHONE_ID}/messages"
        headers = {
            "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
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
            logger.info(f"🚀 Sent WhatsApp message to {to_phone}")
            return True
        except Exception as e:
            logger.error(f"🔥 Failed to send WhatsApp: {e}")
            return False

    def download_media(self, media_url: str) -> str:
        """
        Downloads media (Audio/Image) from WhatsApp URLs.
        Requires Authorization header for security.
        """
        try:
            filename = f"{uuid.uuid4()}.ogg"
            # Use /tmp for ephemeral storage (compatible with Lambda/Containers)
            save_path = f"/tmp/{filename}" 
            
            headers = {}
            # Meta URLs require auth, generic URLs might not
            if "facebook.com" in media_url and settings.META_ACCESS_TOKEN:
                headers["Authorization"] = f"Bearer {settings.META_ACCESS_TOKEN}"

            response = requests.get(media_url, headers=headers, timeout=30)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"📥 Media downloaded successfully: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"❌ Error downloading media: {e}")
            return None

# Singleton Instance
whatsapp_adapter = WhatsAppAdapter()