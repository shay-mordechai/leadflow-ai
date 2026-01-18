import logging
import telnyx
from src.config import settings
from src.services.providers.base import PhoneProviderStrategy

logger = logging.getLogger("TelnyxProvider")

if settings.TELNYX_API_KEY:
    telnyx.api_key = settings.TELNYX_API_KEY

class TelnyxProvider(PhoneProviderStrategy):
    @property
    def provider_name(self) -> str:
        return "TELNYX"

    @property
    def is_configured(self) -> bool:
        return bool(settings.TELNYX_API_KEY)

    def search_and_buy_number(self, country_code: str, number_type: str, user_id: str) -> str | None:
        if not self.is_configured:
            return None

        try:
            # Telnyx search filter
            # Note: Telnyx treats number types differently, verification is key.
            available = telnyx.AvailablePhoneNumber.list(
                filter={
                    "country_code": country_code,
                    "features": ["sms"],
                    "limit": 1,
                    # Telnyx uses 'local' or 'mobile' in filter
                    "number_type": number_type 
                }
            )

            if not available or not available.data:
                logger.warning(f"[Telnyx] No numbers found for {country_code} ({number_type})")
                return None

            phone_number = available.data[0].phone_number
            logger.info(f"[Telnyx] Found {phone_number}. Purchasing...")

            # Execute Order
            telnyx.NumberOrder.create(
                phone_numbers=[{"phone_number": phone_number}],
                customer_reference=f"User_{user_id}"
            )
            
            # NOTE: In production, you must also assign a Messaging Profile here
            # to handle webhooks. For MVP, we assume a default profile is set on the account.
            
            return phone_number

        except Exception as e:
            logger.error(f"[Telnyx] Error: {e}")
            return None