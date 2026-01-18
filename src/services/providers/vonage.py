import logging
from vonage import Vonage, Auth
from src.config import settings
from src.services.providers.base import PhoneProviderStrategy

logger = logging.getLogger("VonageProvider")

class VonageProvider(PhoneProviderStrategy):
    def __init__(self):
        self.client = None
        
        # Check if basic credentials exist
        if settings.VONAGE_API_KEY and settings.VONAGE_API_SECRET:
            try:
                # Prepare authentication parameters
                auth_params = {
                    "api_key": settings.VONAGE_API_KEY,
                    "api_secret": settings.VONAGE_API_SECRET
                }

                # Add Application ID if available (Required for Voice/RTC)
                if settings.VONAGE_APP_ID:
                    auth_params["application_id"] = settings.VONAGE_APP_ID

                # Add Private Key if available (Required for generating JWTs)
                if settings.VONAGE_PRIVATE_KEY_PATH:
                    auth_params["private_key"] = settings.VONAGE_PRIVATE_KEY_PATH

                # Initialize the client using the new SDK syntax (v3.x+)
                # This fixes the "AttributeError: module 'vonage' has no attribute 'Client'"
                self.client = Vonage(Auth(**auth_params))
                
            except Exception as e:
                logger.error(f"[Vonage] Failed to initialize client: {e}")
                self.client = None

    @property
    def provider_name(self) -> str:
        return "VONAGE"

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def search_and_buy_number(self, country_code: str, number_type: str, user_id: str) -> str | None:
        if not self.is_configured:
            logger.warning("[Vonage] Provider is not configured")
            return None

        # Vonage uses different terminology: "landline" instead of "local"
        vonage_type = "landline" if number_type == "local" else "mobile-lvn"

        try:
            # 1. Search for available numbers
            # Note: In newer SDKs, 'get_available_numbers' is often wrapped under 'numbers'
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

            # 2. Buy the selected number
            self.client.numbers.buy_number({
                "country": country_code,
                "msisdn": msisdn
            })

            # 3. Link to Application (Critical for Webhooks/Voice)
            if settings.VONAGE_APP_ID:
                try:
                    self.client.numbers.update_number({
                        "country": country_code,
                        "msisdn": msisdn,
                        "app_id": settings.VONAGE_APP_ID
                    })
                except Exception as link_error:
                    # Don't fail the whole process if linking fails, but log it
                    logger.warning(f"[Vonage] Bought number but failed to link app: {link_error}")

            return f"+{msisdn}" # Ensure E.164 format

        except Exception as e:
            logger.error(f"[Vonage] Error purchasing number: {e}")
            return None
