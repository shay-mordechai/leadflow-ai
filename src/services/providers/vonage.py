# src/services/providers/vonage.py
import requests
import logging
from typing import List, Dict, Optional
from src.config import settings
from src.services.providers.base import PhoneProviderStrategy

logger = logging.getLogger("VonageProvider")

class VonageProvider(PhoneProviderStrategy):
    def __init__(self):
        self.api_key = getattr(settings, "VONAGE_API_KEY", None)
        self.api_secret = getattr(settings, "VONAGE_API_SECRET", None)
        self.base_url = "https://rest.nexmo.com/number"

    @property
    def provider_name(self) -> str:
        return "VONAGE"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def search_numbers(self, country_code: str, number_type: str = "mobile-lvn", limit: int = 5) -> List[Dict]:
        if not self.is_configured:
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
            
            # SECURITY FIX (B113): Added timeout
            response = requests.get(f"{self.base_url}/search", params=params, timeout=10)
            data = response.json()
            
            results = []
            if 'numbers' in data:
                for num in data['numbers']:
                    results.append({
                        "number": "+" + num['msisdn'], 
                        "friendly_name": f"Vonage {num.get('type', 'Unknown')}",
                        "locality": num.get('type', 'unknown'),
                        "country": country_code,
                        "price_monthly": float(num.get('cost', 1.25)),
                        "currency": "EUR",
                        "provider": "vonage"
                    })
            return results
        except Exception as e:
            logger.error(f"[Vonage] Search Exception: {e}")
            return []