import vonage
import logging
from typing import List, Dict
from src.config import settings

logger = logging.getLogger("VonageProvider")

class VonageProvider:
    def __init__(self):
        # Vonage דורש גם Key וגם Secret
        self.api_key = settings.VONAGE_API_KEY
        self.api_secret = settings.VONAGE_API_SECRET
        
        if self.api_key and self.api_secret:
            self.client = vonage.Client(key=self.api_key, secret=self.api_secret)
        else:
            self.client = None
            logger.warning("⚠️ Vonage Credentials missing!")

    def search_numbers(self, country_code: str = "IL", type: str = "mobile-lvn") -> List[Dict]:
        """
        Vonage Search: type='mobile-lvn' for Mobile, 'landline' for Landline.
        """
        if not self.client: return []

        try:
            logger.info(f"🔍 Searching Vonage for {country_code}...")
            
            # Vonage משתמש ב-SDK בצורה קצת שונה
            numbers = self.client.numbers.get_available_numbers(
                country=country_code,
                features=["SMS", "VOICE"],
                size=5,
                type=type 
            )

            results = []
            if 'numbers' in numbers:
                for num in numbers['numbers']:
                    results.append({
                        "phone_number": "+" + num['msisdn'], # Vonage מחזיר בלי +
                        "friendly_name": num['msisdn'],
                        "locality": "", # Vonage לרוב לא נותן מידע גיאוגרפי מדויק למובייל
                        "price": num.get('cost', 'Unknown'),
                        "currency": "EUR", # Vonage לרוב מחייב ביורו
                        "provider": "vonage"
                    })
            
            return results

        except Exception as e:
            logger.error(f"❌ Vonage Search Error: {e}")
            return []

    def buy_number(self, phone_number: str, country_code: str = "IL") -> Dict:
        try:
            # Vonage דורש את המספר בלי ה-+
            clean_number = phone_number.replace("+", "")
            logger.info(f"🛒 Buying {clean_number} from Vonage...")

            response = self.client.numbers.buy_number({
                "country": country_code,
                "msisdn": clean_number
            })

            if response['error-code'] == '200':
                return {"status": "success", "phone_number": phone_number, "provider": "vonage"}
            else:
                return {"status": "failed", "error": f"Code: {response['error-code']}"}

        except Exception as e:
             logger.error(f"❌ Vonage Purchase Error: {e}")
             return {"status": "error", "message": str(e)}