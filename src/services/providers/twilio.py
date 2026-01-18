import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from src.config import settings
from src.services.providers.base import PhoneProviderStrategy

logger = logging.getLogger("TwilioProvider")

class TwilioProvider(PhoneProviderStrategy):
    def __init__(self):
        self.client = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.webhook_url = f"{settings.BASE_URL}/webhooks/whatsapp/twilio"

    @property
    def provider_name(self) -> str:
        return "TWILIO"

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def search_and_buy_number(self, country_code: str, number_type: str, user_id: str) -> str | None:
        if not self.is_configured:
            return None

        try:
            # Twilio distinguishes between 'local' and 'mobile' lists
            numbers = None
            if number_type == "mobile":
                numbers = self.client.available_phone_numbers(country_code).mobile.list(limit=1)
            else:
                numbers = self.client.available_phone_numbers(country_code).local.list(limit=1)

            if not numbers:
                logger.warning(f"[Twilio] No {number_type} numbers found in {country_code}")
                return None

            selected_number = numbers[0]
            logger.info(f"[Twilio] Found {selected_number.phone_number}. Purchasing...")

            purchased = self.client.incoming_phone_numbers.create(
                phone_number=selected_number.phone_number,
                friendly_name=f"LeadFlow_{user_id}",
                sms_url=self.webhook_url
            )
            return purchased.phone_number

        except TwilioRestException as e:
            logger.error(f"[Twilio] API Error: {e}")
            return None
        except Exception as e:
            logger.error(f"[Twilio] Unexpected Error: {e}")
            return None