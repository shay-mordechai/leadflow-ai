# src/services/phone_service.py
import logging
from typing import Tuple, Optional

# Import Bridges
from src.services.providers.twilio import TwilioProvider
from src.services.providers.telnyx import TelnyxProvider
from src.services.providers.vonage import VonageProvider

logger = logging.getLogger("PhoneServiceManager")

class PhoneServiceManager:
    """
    The orchestrator. 
    POLICY: ISRAEL ONLY. No US Fallbacks.
    """

    def __init__(self):
        # Initialize strategies
        self.providers = {
            "TWILIO": TwilioProvider(),
            "TELNYX": TelnyxProvider(),
            "VONAGE": VonageProvider()
        }

    def provision_best_number(self, user_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Attempts to buy an ISRAELI number only.
        Returns: (phone_number, provider_name) OR (None, None) if failed.
        """
        # --- 🛑 MOCK MODE (For Testing) 🛑 ---
        if not settings.ENABLE_REAL_PHONE_PURCHASE:
            logger.info(f"🧪 TEST MODE: Simulating purchase for User {user_id}")
            # מחזיר מספר דמו שנראה אמיתי
            mock_number = f"+97250{user_id[-7:]}" # מייצר מספר שנגמר ב-ID של המשתמש כדי שיהיה ייחודי
            return mock_number, "MOCK_PROVIDER"

        # --- REAL MODE (Production) ---
        # --- STRATEGY 1: Cheap Local Numbers (Landline - 03/09/02/04) ---
        # Priority: Telnyx ($) -> Vonage ($) -> Twilio ($$)
        logger.info("🇮🇱 Strategy 1: Searching for Local (Landline) IL numbers...")
        
        for name in ["TELNYX", "VONAGE", "TWILIO"]:
            provider = self.providers[name]
            if provider.is_configured:
                try:
                    num = provider.search_and_buy_number("IL", "local", user_id)
                    if num:
                        logger.info(f"✅ Success! Acquired IL Local via {name}")
                        return num, name
                except Exception as e:
                    logger.warning(f"⚠️ Failed to buy local from {name}: {e}")

        # --- STRATEGY 2: Mobile Numbers (05X) - More Expensive ---
        # Priority: Telnyx -> Vonage -> Twilio
        logger.info("🇮🇱 Strategy 2: Local failed. Searching for Mobile IL numbers...")

        for name in ["TELNYX", "VONAGE", "TWILIO"]:
            provider = self.providers[name]
            if provider.is_configured:
                try:
                    num = provider.search_and_buy_number("IL", "mobile", user_id)
                    if num:
                        logger.info(f"✅ Success! Acquired IL Mobile via {name}")
                        return num, name
                except Exception as e:
                    logger.warning(f"⚠️ Failed to buy mobile from {name}: {e}")

        # --- FAILURE: NO NUMBERS FOUND ---
        # אם הגענו לפה, אין מספרים בישראל באף ספק, או שאין אישור רגולטורי.
        logger.critical("❌ CRITICAL: Could not find ANY Israel number (Local or Mobile).")
        return None, None

# Singleton Instance
phone_service = PhoneServiceManager()