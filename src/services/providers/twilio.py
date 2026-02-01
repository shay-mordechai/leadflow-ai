# src/services/providers/twilio.py
import logging
from typing import List, Dict, Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from src.config import settings
from src.services.providers.base import PhoneProviderStrategy

logger = logging.getLogger("TwilioProvider")

class TwilioProvider(PhoneProviderStrategy):
    """
    Twilio Implementation.
    """

    def __init__(self):
        self.client = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            except Exception as e:
                logger.error(f"Twilio Client Init Failed: {e}")
                self.client = None
        
        self.webhook_url = f"{settings.BASE_URL}/webhooks/whatsapp/twilio"

    @property
    def provider_name(self) -> str:
        return "TWILIO"

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def search_numbers(self, country_code: str, number_type: str = "local", limit: int = 5) -> List[Dict]:
        if not self.is_configured:
            return []

        try:
            twilio_list = []
            if number_type.lower() == "mobile":
                twilio_list = self.client.available_phone_numbers(country_code).mobile.list(limit=limit)
            else:
                twilio_list = self.client.available_phone_numbers(country_code).local.list(limit=limit)

            results = []
            for record in twilio_list:
                # FIX: Explicitly use 'phone_number' key to match compare script
                results.append({
                    "phone_number": record.phone_number, 
                    "locality": getattr(record, 'locality', 'General'),
                    "price": "5.00" if number_type == "mobile" else "1.15",
                    "currency": "USD",
                    "provider": self.provider_name
                })
            
            return results

        except Exception as e:
            logger.error(f"[Twilio] Search Error: {e}")
            return []

    def purchase_number(self, phone_number: str, user_id: str) -> Optional[str]:
        if not self.is_configured: return None
        try:
            purchased = self.client.incoming_phone_numbers.create(
                phone_number=phone_number,
                friendly_name=f"LeadFlow_{user_id}",
                sms_url=self.webhook_url
            )
            return purchased.phone_number
        except Exception as e:
            logger.error(f"[Twilio] Purchase Error: {e}")
            return None