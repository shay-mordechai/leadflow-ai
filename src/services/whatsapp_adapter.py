# src/services/whatsapp_adapter.py
import logging
import requests
import uuid
import os
from src.config import settings

logger = logging.getLogger(__name__)

class WhatsAppAdapter:
    def send_message(self, to_phone: str, text: str):
        if not settings.META_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_ID:
            logger.error("❌ Meta credentials missing in settings")
            return False

        url = f"https://graph.facebook.com/v17.0/{settings.WHATSAPP_PHONE_ID}/messages"
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
            logger.info(f"🚀 Sent WhatsApp to {to_phone}")
            return True
        except Exception as e:
            logger.error(f"🔥 Failed to send WhatsApp: {e}")
            return False

    def download_media(self, media_url: str) -> str:
        try:
            filename = f"{uuid.uuid4()}.ogg"
            save_path = f"/tmp/{filename}" # Use tmp for transient storage
            
            headers = {}
            if "facebook.com" in media_url and settings.META_ACCESS_TOKEN:
                headers["Authorization"] = f"Bearer {settings.META_ACCESS_TOKEN}"

            response = requests.get(media_url, headers=headers, timeout=30)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"📥 Media downloaded to {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"❌ Error downloading media: {e}")
            return None

whatsapp_adapter = WhatsAppAdapter()