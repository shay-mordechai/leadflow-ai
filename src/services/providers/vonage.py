import logging
import vonage
from src.config import settings
from src.services.providers.base import PhoneProviderStrategy

logger = logging.getLogger("VonageProvider")

class VonageProvider(PhoneProviderStrategy):
    def __init__(self):
        self.client = None
        if settings.VONAGE_API_KEY and settings.VONAGE_API_SECRET:
            # Vonage requires the private key for the Messages API (WhatsApp/SMS)
            if settings.VONAGE_PRIVATE_KEY_PATH:
                 self.client = vonage.Client(
                    key=settings.VONAGE_API_KEY, 
                    secret=settings.VONAGE_API_SECRET,
                    application_id=settings.VONAGE_APP_ID,
                    private_key=settings.VONAGE_PRIVATE_KEY_PATH
                )
            else:
                # Fallback for basic number search without full app context
                self.client = vonage.Client(
                    key=settings.VONAGE_API_KEY, 
                    secret=settings.VONAGE_API_SECRET
                )

    @property
    def provider_name(self) -> str:
        return "VONAGE"

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def search_and_buy_number(self, country_code: str, number_type: str, user_id: str) -> str | None:
        if not self.is_configured:
            return None

        # Vonage uses different terminology: "landline" instead of "local"
        vonage_type = "landline" if number_type == "local" else "mobile-lvn"

        try:
            # 1. Search
            response = self.client.numbers.get_available_numbers(
                country_code, 
                {"type": vonage_type, "features": "SMS", "size": 1}
            )

            if not response.get('numbers'):
                logger.warning(f"[Vonage] No numbers found for {country_code}")
                return None

            selected = response['numbers'][0]
            msisdn = selected['msisdn']
            
            logger.info(f"[Vonage] Found {msisdn}. Purchasing...")

            # 2. Buy
            self.client.numbers.buy_number({
                "country": country_code,
                "msisdn": msisdn
            })

            # 3. Link to Application (Critical for Webhooks)
            if settings.VONAGE_APP_ID:
                self.client.numbers.update_number({
                    "country": country_code,
                    "msisdn": msisdn,
                    "app_id": settings.VONAGE_APP_ID
                })

            return f"+{msisdn}" # Ensure E.164 format

        except Exception as e:
            logger.error(f"[Vonage] Error: {e}")
            return None