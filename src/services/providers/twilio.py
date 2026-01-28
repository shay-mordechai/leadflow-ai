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
    Implementation of the Twilio Provider logic.
    Separates the Search phase from the Purchase phase.
    """

    def __init__(self):
        self.client = None
        # Professional English Comment:
        # Check credentials securely from settings (loaded from AWS SSM/Env)
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            except Exception as e:
                logger.error(f"Twilio Client Init Failed: {e}")
                self.client = None
        
        # This URL is where Twilio will send incoming SMS/WhatsApp messages
        self.webhook_url = f"{settings.BASE_URL}/webhooks/whatsapp/twilio"

    @property
    def provider_name(self) -> str:
        return "TWILIO"

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def search_numbers(self, country_code: str, number_type: str = "local", limit: int = 5) -> List[Dict]:
        """
        Searches for available numbers without buying them.
        Returns a standardized dictionary list.
        """
        if not self.is_configured:
            logger.warning("Twilio is not configured. Skipping search.")
            return []

        try:
            # Twilio distinguishes between 'local' (Landline) and 'mobile' lists
            twilio_list = []
            
            if number_type.lower() == "mobile":
                # Note: Mobile search availability depends on the country
                twilio_list = self.client.available_phone_numbers(country_code).mobile.list(limit=limit)
            else:
                twilio_list = self.client.available_phone_numbers(country_code).local.list(limit=limit)

            results = []
            for record in twilio_list:
                # Professional English Comment:
                # Twilio Search API often does not return the monthly price.
                # We estimate the COST price here. The Service Manager will add the markup.
                # IL Local cost approx $1.15, IL Mobile approx $5.00
                estimated_cost = 5.00 if number_type == "mobile" else 1.15
                
                results.append({
                    "number": record.phone_number,
                    "country": record.iso_country,
                    "capabilities": [k for k, v in record.capabilities.items() if v], # e.g. ['sms', 'voice']
                    "cost_price": estimated_cost,
                    "provider": self.provider_name,
                    "type": number_type
                })
            
            return results

        except TwilioRestException as e:
            logger.error(f"[Twilio] Search API Error: {e}")
            return []
        except Exception as e:
            logger.error(f"[Twilio] Unexpected Search Error: {e}")
            return []

    def purchase_number(self, phone_number: str, user_id: str) -> Optional[str]:
        """
        Purchases a SPECIFIC phone number chosen by the user.
        """
        if not self.is_configured:
            return None

        try:
            logger.info(f"[Twilio] Attempting to purchase {phone_number} for User {user_id}")

            # Purchase and configure Webhook in one go
            purchased = self.client.incoming_phone_numbers.create(
                phone_number=phone_number,
                friendly_name=f"LeadFlow_{user_id}",
                sms_url=self.webhook_url, # Critical: Connects to our Bot
                sms_method="POST"
            )
            
            logger.info(f"✅ [Twilio] Successfully purchased: {purchased.phone_number}")
            return purchased.phone_number

        except TwilioRestException as e:
            logger.error(f"❌ [Twilio] Purchase API Error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ [Twilio] Purchase Unexpected Error: {e}")
            return None