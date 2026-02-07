# src/services/providers/twilio.py
import logging
from typing import List, Dict, Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from src.config import settings

logger = logging.getLogger("TwilioProvider")

class TwilioProvider:
    """
    Twilio Implementation for searching and buying numbers.
    """

    def __init__(self):
        self.client = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            except Exception as e:
                logger.error(f"Twilio Client Init Failed: {e}")
                self.client = None
        
        # Webhook URL for handling incoming messages
        self.webhook_url = f"{settings.BASE_URL}/webhooks/whatsapp/twilio"

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def search_numbers(self, country_code: str = "IL", area_code: str = None, contains: str = None) -> List[Dict]:
        if not self.is_configured:
            logger.warning("Twilio is not configured. Returning empty list.")
            return []

        try:
            params = {"limit": 10}
            if contains:
                params["contains"] = contains
            
            # 1. Try Local Numbers first
            try:
                twilio_results = self.client.available_phone_numbers(country_code).local.list(**params)
                number_type = "local"
            except TwilioRestException:
                twilio_results = []

            # 2. If no local numbers found, try Mobile
            if not twilio_results:
                twilio_results = self.client.available_phone_numbers(country_code).mobile.list(**params)
                number_type = "mobile"

            results = []
            for record in twilio_results:
                results.append({
                    "number": record.phone_number,
                    "friendly_name": record.friendly_name,
                    "locality": getattr(record, 'locality', 'General'),
                    "country": country_code,
                    "capabilities": ["voice", "sms", "mms"] if number_type == "mobile" else ["voice"],
                    "price_monthly": 1.15 if number_type == "local" else 5.00,
                    "provider": "twilio"
                })
            
            return results

        except Exception as e:
            logger.error(f"[Twilio] Search Error: {e}")
            return []

    def buy_number(self, phone_number: str, friendly_name: str = None) -> Optional[str]:
        if not self.is_configured: return None
        try:
            purchased = self.client.incoming_phone_numbers.create(
                phone_number=phone_number,
                friendly_name=friendly_name or "LeadFlow AI Number",
                voice_url=self.webhook_url, 
                sms_url=self.webhook_url 
            )
            return purchased.sid
        except Exception as e:
            logger.error(f"[Twilio] Purchase Error: {e}")
            raise e

# Singleton instance
twilio_provider = TwilioProvider()