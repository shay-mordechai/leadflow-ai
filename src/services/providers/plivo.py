# src/services/providers/plivo.py
import plivo
import logging
from typing import List, Dict, Optional
from src.config import settings
from src.services.providers.base import PhoneProviderStrategy

logger = logging.getLogger("PlivoProvider")

class PlivoProvider(PhoneProviderStrategy):
    """
    Plivo Implementation conforming to the Base Strategy.
    """

    def __init__(self):
        # Use getattr to prevent crashes if config is missing
        self.auth_id = getattr(settings, 'PLIVO_AUTH_ID', None)
        self.auth_token = getattr(settings, 'PLIVO_AUTH_TOKEN', None)
        self.client = None

        if self.auth_id and self.auth_token:
            try:
                self.client = plivo.RestClient(auth_id=self.auth_id, auth_token=self.auth_token)
            except Exception:
                self.client = None

    @property
    def provider_name(self) -> str:
        return "PLIVO"

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def search_numbers(self, country_code: str, number_type: str = "local", limit: int = 5) -> List[Dict]:
        if not self.is_configured: return []

        try:
            # Plivo types: 'local', 'mobile', 'tollfree'
            p_type = "mobile" if number_type == "mobile" else "local"

            # API call to Plivo
            response = self.client.numbers.search(
                country_iso=country_code,
                type=p_type,
                limit=limit
            )

            results = []
            for num in response:
                results.append({
                    "number": "+" + str(num['number']), # Ensure standard format
                    "friendly_name": f"Plivo {country_code} Number",
                    "locality": num.get('country', country_code),
                    "country": num.get('country', country_code),
                    "capabilities": ["voice", "sms"],
                    "price_monthly": float(num.get('monthly_rental_rate', 0.80)), # Standardize key
                    "provider": "plivo"
                })
            
            return results

        except Exception as e:
            logger.error(f"[Plivo] Search Error: {e}")
            return []

    def purchase_number(self, phone_number: str, user_id: str) -> Optional[str]:
        if not self.is_configured: return None

        try:
            logger.info(f"[Plivo] Buying {phone_number}...")
            # Plivo requires the number without '+' usually
            response = self.client.numbers.buy(number=phone_number.replace("+", ""))
            
            if response.get('status') == 'fulfilled':
                 return phone_number
            return None

        except Exception as e:
            logger.error(f"[Plivo] Purchase Error: {e}")
            return None