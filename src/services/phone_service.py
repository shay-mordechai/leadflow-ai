# src/services/phone_service.py
import logging
from typing import List, Dict, Optional

# Import the provider we just created
from src.services.providers.twilio import TwilioProvider
# (Future: Add TelnyxProvider here)

from src.config import settings

logger = logging.getLogger("PhoneServiceManager")

class PhoneServiceManager:
    def __init__(self):
        self.twilio = TwilioProvider()
        # self.telnyx = TelnyxProvider() # נכין את זה לעתיד

    async def search_best_numbers(self, country_code: str) -> List[Dict]:
        """
        Aggregates numbers from all providers and applies the 'Coupon' (Markup).
        """
        if not settings.ENABLE_REAL_PHONE_PURCHASE:
            # Mock Fallback
            return [
                {"number": "+972541234567", "country": "IL", "price_monthly": 5.00, "provider": "MOCK"},
                {"number": "+97235555555", "country": "IL", "price_monthly": 4.00, "provider": "MOCK"}
            ]

        all_numbers = []

        # 1. Fetch from Twilio
        twilio_results = self.twilio.search_numbers(country_code, "local")
        all_numbers.extend(twilio_results)

        # 2. Fetch from Telnyx (Future implementation)
        # telnyx_results = self.telnyx.search_numbers(...)
        # all_numbers.extend(telnyx_results)

        # 3. APPLY MARKUP (The "Coupon") 💰
        # מחירון לצרכן:
        # Local (Landline) -> נמכור ב-$4.00
        # Mobile -> נמכור ב-$8.00
        final_list = []
        for item in all_numbers:
            cost = item.get("cost_price", 0)
            
            # אם המספר מתחיל ב-05 (נייד) או לא
            is_mobile = "sms" in item["capabilities"] or "mobile" in str(item.get("type", "")).lower()
            
            # קביעת מחיר מכירה
            selling_price = 8.00 if is_mobile else 4.00

            # עיצוב האובייקט הסופי ללקוח (מסתירים את ה-Provider ואת ה-Cost)
            final_list.append({
                "number": item["number"],
                "country": item["country"],
                "capabilities": item["capabilities"],
                "price_monthly": selling_price, # המחיר שהלקוח רואה
                "provider": "LeadFlow Network"  # White Labeling
            })

        return final_list

    async def purchase_number(self, phone_number: str, user_id: str) -> Dict:
        """
        Executes the purchase on the cheapest provider found.
        """
        # כרגע יש רק טוויליו, בעתיד נבדוק ממי המספר הזה הגיע
        logger.info(f"User {user_id} buying {phone_number}")
        
        success = self.twilio.buy_number(phone_number)
        
        if success:
            # TODO: Save to Database (We will do this in the next step)
            return {"status": "success", "number": phone_number}
        else:
            return {"status": "failed", "detail": "Provider error"}

phone_service = PhoneServiceManager()