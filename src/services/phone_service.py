# src/services/phone_service.py
import httpx
import logging
from typing import List, Dict, Any
from src.config import settings

logger = logging.getLogger("PhoneService")

# Configuration for Webhooks
# These URLs are registered with the provider to handle incoming calls/messages
BASE_URL = settings.BASE_URL
VOICE_WEBHOOK = f"{BASE_URL}/webhooks/voice/incoming"
SMS_WEBHOOK = f"{BASE_URL}/webhooks/whatsapp/twilio"

class PhoneService:
    def __init__(self):
        """
        Initializes the SignalWire/Twilio client configuration.
        Parses the Space URL to construct the base API endpoint.
        """
        self.project_id = (settings.SIGNALWIRE_PROJECT_ID or "").strip()
        self.auth_token = (settings.SIGNALWIRE_AUTH_TOKEN or "").strip()
        raw_space = (settings.SIGNALWIRE_SPACE_URL or "").strip()
        
        # Clean URL to get the hostname (e.g., "example.signalwire.com")
        clean_host = raw_space.replace("https://", "").replace("http://", "").strip("/")
        
        if self.project_id and clean_host:
            # SignalWire uses the standard Twilio XML API format
            self.api_base = f"https://{clean_host}/api/laml/2010-04-01/Accounts/{self.project_id}"
        else:
            logger.warning("⚠️ SignalWire credentials missing. Phone service disabled.")
            self.api_base = None

    def _get_auth(self):
        """Returns Basic Auth tuple."""
        return (self.project_id, self.auth_token)

    async def search_best_numbers(self, country_code: str, area_code: str = None) -> List[Dict]:
        """
        Searches for available phone numbers.
        Returns a normalized list compatible with the frontend schema.
        """
        if not self.api_base:
            logger.error("❌ Cannot search: Missing API Base URL")
            return []

        params = {"Limit": 5}
        if area_code: 
            params["AreaCode"] = area_code
        
        # CRITICAL FIX: SignalWire requires '.json' extension for JSON responses
        endpoint = f"{self.api_base}/AvailablePhoneNumbers/{country_code}/Local.json"
        
        logger.info(f"🔎 Requesting numbers from: {endpoint}")

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(endpoint, params=params, auth=self._get_auth())
                
                if resp.status_code != 200:
                    logger.error(f"❌ Provider API Error: {resp.text}")
                    return []
                
                data = resp.json()
                results = []
                # Handle provider specific response structure
                numbers = data.get("available_phone_numbers", [])
                
                for n in numbers:
                    results.append({
                        "number": n.get("phone_number"),
                        "country": n.get("iso_country", country_code),
                        "provider": "signalwire",
                        # Default values required by Pydantic Schema
                        "capabilities": ["voice", "sms", "mms"],
                        "price_monthly": 1.00 
                    })
                return results
            except Exception as e:
                logger.error(f"❌ Search Exception: {e}")
                return []

    async def purchase_number(self, phone_number: str, user_id: str, friendly_name: str) -> Dict[str, Any]:
        """
        Purchases a phone number and immediately configures webhooks.
        """
        if not self.api_base: 
            return {"status": "failed", "detail": "Missing Provider Credentials"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                logger.info(f"🛒 Purchasing {phone_number} for User {user_id}...")
                
                # 1. Purchase Request
                # CRITICAL FIX: Added .json extension
                buy_resp = await client.post(
                    f"{self.api_base}/IncomingPhoneNumbers.json",
                    data={
                        "PhoneNumber": phone_number, 
                        "FriendlyName": f"{friendly_name} ({user_id})"
                    },
                    auth=self._get_auth()
                )
                
                if buy_resp.status_code != 201:
                    logger.error(f"❌ Purchase Failed: {buy_resp.text}")
                    return {"status": "failed", "detail": f"Provider Error: {buy_resp.text}"}

                sid = buy_resp.json().get("sid")
                logger.info(f"✅ Number Bought! SID: {sid}. Configuring Webhooks...")

                # 2. Configure Webhooks (Point to our AI Engine)
                # CRITICAL FIX: Added .json extension
                config_resp = await client.post(
                    f"{self.api_base}/IncomingPhoneNumbers/{sid}.json",
                    data={
                        "VoiceUrl": VOICE_WEBHOOK, "VoiceMethod": "POST",
                        "SmsUrl": SMS_WEBHOOK, "SmsMethod": "POST"
                    },
                    auth=self._get_auth()
                )

                if config_resp.status_code == 200:
                    logger.info("✅ Webhooks configured successfully.")
                else:
                    logger.warning(f"⚠️ Webhook config failed: {config_resp.text}")

                return {"status": "success", "number": phone_number, "sid": sid}
            except Exception as e:
                logger.error(f"❌ Purchase Exception: {e}")
                return {"status": "failed", "detail": str(e)}

# Singleton Instance
phone_service = PhoneService()