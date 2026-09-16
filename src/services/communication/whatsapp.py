# src/services/communication/whatsapp.py
import logging
import os
import tempfile
from typing import Optional

import requests

from src.config import settings

logger = logging.getLogger("WhatsAppAdapter")

GRAPH_HOST = "https://graph.facebook.com"


def _digits_only(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


class WhatsAppAdapter:
    """
    Native Meta WhatsApp Cloud API adapter (Graph).
    Twilio is no longer used for outbound WhatsApp traffic.
    """

    def __init__(self):
        self.access_token = settings.META_ACCESS_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_ID
        self.api_version = getattr(settings, "GRAPH_API_VERSION", "v21.0") or "v21.0"

    def _is_production(self) -> bool:
        return (settings.APP_ENV or "").lower() == "production"

    def _credentials(self, access_token: Optional[str] = None, phone_number_id: Optional[str] = None) -> tuple[str, str]:
        token = (access_token or self.access_token or "").strip()
        phone_id = (phone_number_id or self.phone_number_id or "").strip()
        return token, phone_id

    def is_configured(self, access_token: Optional[str] = None, phone_number_id: Optional[str] = None) -> bool:
        token, phone_id = self._credentials(access_token, phone_number_id)
        return bool(token and phone_id)

    def send_message(
        self,
        to_phone: str,
        text: str,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> bool:
        """
        Sends a WhatsApp text message via Meta Graph API.
        Mock replies are allowed only outside production when credentials are absent.
        """
        token, phone_id = self._credentials(access_token, phone_number_id)
        clean_phone = _digits_only(to_phone)
        body = (text or "").strip()

        if not clean_phone or not body:
            logger.warning("Refusing Graph send: missing destination or empty body.")
            return False

        if not token or not phone_id:
            if self._is_production():
                logger.error("Graph API credentials missing in production; message not sent.")
                return False
            logger.warning(
                "[DEV MOCK] Meta credentials missing. Would send WhatsApp to %s: %s",
                clean_phone,
                body[:120],
            )
            return True

        url = f"{GRAPH_HOST}/{self.api_version}/{phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code >= 400:
                logger.error(
                    "Graph API send failed (%s): %s",
                    response.status_code,
                    response.text[:500],
                )
                return False
            data = response.json() if response.content else {}
            message_id = (data.get("messages") or [{}])[0].get("id")
            logger.info("Graph WhatsApp message sent to %s (id=%s)", clean_phone, message_id)
            return True
        except requests.exceptions.RequestException as exc:
            logger.error("Network error sending Graph WhatsApp message: %s", exc)
            return False
        except Exception as exc:
            logger.error("Unexpected Graph send error: %s", exc)
            return False

    def download_media(
        self,
        media_id: str,
        access_token: Optional[str] = None,
    ) -> Optional[str]:
        """
        Downloads Cloud API media by Graph media id into a secure temp file.
        """
        token, _ = self._credentials(access_token, None)
        media_id = (media_id or "").strip()
        if not media_id:
            return None

        if not token:
            if self._is_production():
                logger.error("Cannot download Meta media in production without META_ACCESS_TOKEN.")
            else:
                logger.warning("[DEV MOCK] Cannot download Meta media without credentials.")
            return None

        headers = {"Authorization": f"Bearer {token}"}
        try:
            meta_url = f"{GRAPH_HOST}/{self.api_version}/{media_id}"
            meta_response = requests.get(meta_url, headers=headers, timeout=30)
            meta_response.raise_for_status()
            media_url = (meta_response.json() or {}).get("url")
            if not media_url:
                logger.error("Graph media lookup returned no URL for id %s", media_id)
                return None

            binary_response = requests.get(media_url, headers=headers, timeout=60)
            binary_response.raise_for_status()

            fd, save_path = tempfile.mkstemp(suffix=".ogg", prefix="wa_media_")
            with os.fdopen(fd, "wb") as handle:
                handle.write(binary_response.content)

            logger.info("Meta media downloaded to %s", save_path)
            return save_path
        except requests.exceptions.RequestException as exc:
            logger.error("Network error downloading Meta media %s: %s", media_id, exc)
            return None
        except Exception as exc:
            logger.error("Unexpected Meta media download error: %s", exc)
            return None


whatsapp_adapter = WhatsAppAdapter()
