import telnyx
import logging
from typing import List, Dict, Optional
from src.config import settings

logger = logging.getLogger("TelnyxProvider")

class TelnyxProvider:
    def __init__(self):
        self.api_key = settings.TELNYX_API_KEY
        if self.api_key:
            telnyx.api_key = self.api_key
        else:
            logger.warning("⚠️ TELNYX_API_KEY is missing!")

    def search_numbers(self, country_code: str = "IL", type: str = "mobile") -> List[Dict]:
        """
        מחפש מספרים פנויים ב-Telnyx ומחזיר רשימה עם מחירים.
        """
        if not self.api_key: return []
        
        try:
            # Telnyx uses 2-letter country codes (IL, US)
            logger.info(f"🔍 Searching Telnyx for {country_code} numbers...")
            
            # חיפוש מספרים
            available_numbers = telnyx.AvailablePhoneNumber.list(
                filter={"country_code": country_code, "features": ["sms", "voice"]},
                page={"size": 5}
            )

            results = []
            for num in available_numbers:
                # המרה לפורמט אחיד שלנו
                # Telnyx מחזיר עלות, למשל "1.00"
                cost = num.cost_information.upfront_cost if hasattr(num, 'cost_information') else "N/A"
                
                results.append({
                    "phone_number": num.phone_number,
                    "friendly_name": num.phone_number, # Telnyx לא תמיד נותן פורמט יפה
                    "locality": num.region_information.region_name if hasattr(num, 'region_information') else "",
                    "price": cost,
                    "currency": num.cost_information.currency if hasattr(num, 'cost_information') else "USD",
                    "provider": "telnyx"
                })
            
            return results

        except Exception as e:
            logger.error(f"❌ Telnyx Search Error: {e}")
            return []

    def buy_number(self, phone_number: str) -> Dict:
        """
        מבצע רכישה של מספר.
        """
        try:
            logger.info(f"🛒 Buying {phone_number} from Telnyx...")
            # ב-Telnyx צריך קודם להזמין (Order)
            order = telnyx.NumberOrder.create(
                phone_numbers=[{"phone_number": phone_number}],
                customer_reference="LeadFlow_AI_Purchase"
            )
            
            # בדיקה אם ההזמנה הצליחה
            if order.status in ["pending", "success"]:
                 return {"status": "success", "phone_number": phone_number, "provider": "telnyx", "order_id": order.id}
            else:
                 return {"status": "failed", "error": f"Order status: {order.status}"}

        except Exception as e:
            logger.error(f"❌ Telnyx Purchase Error: {e}")
            return {"status": "error", "message": str(e)}