# src/services/communication/whatsapp.py
import logging
import requests
import uuid
import os
import tempfile
from src.config import settings

logger = logging.getLogger("WhatsAppAdapter")

class WhatsAppAdapter:
    def __init__(self):
        self.api_version = "v17.0"

    def send_message(self, to_phone: str, text: str):
        if not settings.META_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_ID:
            logger.error("❌ Meta credentials missing in settings.")
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
            # SECURITY FIX (B113): Added timeout
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"🔥 Failed to send WhatsApp: {e}")
            return False

    def download_media(self, media_url: str) -> str:
        """
        Downloads media securely using dynamic temp directories.
        """
        try:
            # SECURITY FIX (B108): Use tempfile for secure ephemeral storage
            # This avoids predictable paths in /tmp
            temp_dir = tempfile.gettempdir()
            filename = f"wa_media_{uuid.uuid4()}.ogg"
            save_path = os.path.join(temp_dir, filename)
            
            headers = {}
            if "facebook.com" in media_url and settings.META_ACCESS_TOKEN:
                headers["Authorization"] = f"Bearer {settings.META_ACCESS_TOKEN}"

            # SECURITY FIX (B113): Ensured timeout is present
            response = requests.get(media_url, headers=headers, timeout=30)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"📥 Media downloaded securely to: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"❌ Error downloading media: {e}")
            return None

whatsapp_adapter = WhatsAppAdapter()