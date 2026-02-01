# src/services/providers/vonage.py
import requests
import logging
from typing import List, Dict, Optional
from src.config import settings
from src.services.providers.base import PhoneProviderStrategy

logger = logging.getLogger("VonageProvider")

class VonageProvider(PhoneProviderStrategy):
    def __init__(self):
        self.api_key = settings.VONAGE_API_KEY
        self.api_secret = settings.VONAGE_API_SECRET
        self.base_url = "https://rest.nexmo.com/number"

    @property
    def provider_name(self) -> str:
        return "VONAGE"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def search_numbers(self, country_code: str, number_type: str = "mobile-lvn", limit: int = 5) -> List[Dict]:
        if not self.is_configured:
            logger.warning("Vonage not configured (missing key/secret)")
            return []

        try:
            v_type = "mobile-lvn" if number_type == "mobile" else "landline"
            
            params = {
                "api_key": self.api_key,
                "api_secret": self.api_secret,
                "country": country_code,
                "features": "VOICE,SMS",
                "size": limit,
                "type": v_type
            }
            
            response = requests.get(f"{self.base_url}/search", params=params)
            data = response.json()
            
            # DEBUG: Print error if exists
            if 'error-code' in data:
                 logger.error(f"❌ [Vonage] API Error: {data}")
            
            results = []
            if 'numbers' in data:
                for num in data['numbers']:
                    results.append({
                        "phone_number": "+" + num['msisdn'], # FIX: Key matches compare script
                        "locality": num.get('type', 'unknown'),
                        "price": num.get('cost', 'Unknown'),
                        "currency": "EUR",
                        "provider": self.provider_name
                    })
            
            return results

        except Exception as e:
            logger.error(f"[Vonage] Search Exception: {e}")
            return []

    def purchase_number(self, phone_number: str, user_id: str) -> Optional[str]:
        # Purchase logic placeholder
        return None