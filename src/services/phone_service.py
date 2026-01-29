# src/services/phone_service.py
import logging
from typing import List, Dict, Optional
from src.services.providers.twilio import TwilioProvider
from src.config import settings

logger = logging.getLogger("PhoneServiceManager")

class PhoneServiceManager:
    def __init__(self):
        self.twilio = TwilioProvider()

    async def search_best_numbers(self, country_code: str) -> List[Dict]:
        """
        Aggregates numbers from all providers and applies the 'Coupon' (Markup).
        """
        if not settings.ENABLE_REAL_PHONE_PURCHASE:
            return [
                {"number": "+972541234567", "country": "IL", "price_monthly": 5.00, "provider": "MOCK"},
                {"number": "+97235555555", "country": "IL", "price_monthly": 4.00, "provider": "MOCK"}
            ]

        all_numbers = []
        # 1. Fetch from Twilio
        twilio_results = self.twilio.search_numbers(country_code, "local")
        all_numbers.extend(twilio_results)

        # 2. APPLY MARKUP
        final_list = []
        for item in all_numbers:
            is_mobile = "mobile" in str(item.get("type", "")).lower()
            selling_price = 8.00 if is_mobile else 4.00

            final_list.append({
                "number": item["number"],
                "country": item["country"],
                "capabilities": item["capabilities"],
                "price_monthly": selling_price,
                "provider": "LeadFlow Network"
            })

        return final_list

    async def purchase_number(self, phone_number: str, user_id: str) -> Dict:
        """
        Executes the purchase using the corrected method name.
        """
        logger.info(f"User {user_id} buying {phone_number}")
        
        # --- THE FIX: Using .purchase_number() instead of .buy_number() ---
        purchased_number = self.twilio.purchase_number(phone_number, user_id)
        
        if purchased_number:
            return {"status": "success", "number": purchased_number}
        else:
            return {"status": "failed", "detail": "Provider purchase failed (Check Logs)"}

phone_service = PhoneServiceManager()