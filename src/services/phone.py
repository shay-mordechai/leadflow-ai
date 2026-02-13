# src/services/phone.py
import httpx
import logging
import vonage
from twilio.rest import Client as TwilioClient
from typing import List, Dict, Any, Optional
from src.config import settings
import os

logger = logging.getLogger("TelephonyManager")

class TelephonyService:
    def __init__(self):
        """
        Initializes clients for all configured providers (Twilio, Vonage, SignalWire).
        """
        self.providers = []

        # --- 1. Init Twilio ---
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self.twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                self.providers.append("twilio")
                logger.info("✅ Twilio Client Initialized")
            except Exception as e:
                logger.error(f"❌ Twilio Init Failed: {e}")
        else:
            self.twilio_client = None

        # --- 2. Init Vonage ---
        if settings.VONAGE_API_KEY and settings.VONAGE_API_SECRET and os.path.exists(settings.VONAGE_PRIVATE_KEY_PATH):
            try:
                # Auth with both Key/Secret (for SMS) and App/PrivateKey (for Voice)
                self.vonage_auth = vonage.Auth(
                    api_key=settings.VONAGE_API_KEY,
                    api_secret=settings.VONAGE_API_SECRET,
                    application_id=settings.VONAGE_APP_ID,
                    private_key=settings.VONAGE_PRIVATE_KEY_PATH
                )
                # FIX: Use 'vonage.Vonage' instead of 'vonage.Client' for newer SDKs
                self.vonage_client = vonage.Vonage(self.vonage_auth)
                self.providers.append("vonage")
                logger.info("✅ Vonage Client Initialized")
            except Exception as e:
                logger.error(f"❌ Vonage Init Failed: {e}")
                self.vonage_client = None
        else:
            self.vonage_client = None

        # --- 3. Init SignalWire (via HTTPX) ---
        self.sw_project = settings.SIGNALWIRE_PROJECT_ID
        self.sw_token = settings.SIGNALWIRE_AUTH_TOKEN
        self.sw_space = settings.SIGNALWIRE_SPACE_URL
        
        if self.sw_project and self.sw_token and self.sw_space:
            clean_host = self.sw_space.replace("https://", "").replace("http://", "").strip("/")
            self.sw_base = f"https://{clean_host}/api/laml/2010-04-01/Accounts/{self.sw_project}"
            self.providers.append("signalwire")
            logger.info("✅ SignalWire Configured")
        else:
            self.sw_base = None

    async def search_best_numbers(self, country_code: str, area_code: str = None) -> List[Dict]:
        """
        Aggregates available numbers from ALL active providers.
        Includes a filter to ensure numbers match the requested country code.
        """
        results = []

        # --- A. Search Twilio ---
        if self.twilio_client:
            try:
                logger.info("🔍 Searching Twilio...")
                numbers = self.twilio_client.available_phone_numbers(country_code).local.list(limit=5)
                for n in numbers:
                    results.append({
                        "number": n.phone_number,
                        "country": country_code,
                        "provider": "twilio",
                        "price_monthly": 1.15,
                        "capabilities": ["voice", "sms"]
                    })
            except Exception as e:
                logger.warning(f"⚠️ Twilio Search Failed: {e}")

        # --- B. Search Vonage ---
        if self.vonage_client:
            try:
                logger.info("🔍 Searching Vonage...")
                # Vonage uses 2-letter ISO code
                resp = self.vonage_client.numbers.get_available_numbers(country_code, {"size": 5, "type": "mobile-lvn"})
                if "numbers" in resp:
                    for n in resp["numbers"]:
                        results.append({
                            "number": "+" + n["msisdn"],
                            "country": country_code,
                            "provider": "vonage",
                            "price_monthly": 1.00,
                            "capabilities": ["voice", "sms"]
                        })
            except Exception as e:
                logger.warning(f"⚠️ Vonage Search Failed: {e}")

        # --- C. Search SignalWire ---
        if self.sw_base:
            try:
                logger.info("🔍 Searching SignalWire...")
                params = {"Limit": 5}
                if area_code: params["AreaCode"] = area_code
                
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"{self.sw_base}/AvailablePhoneNumbers/{country_code}/Local.json",
                        params=params,
                        auth=(self.sw_project, self.sw_token)
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for n in data.get("available_phone_numbers", []):
                            results.append({
                                "number": n.get("phone_number"),
                                "country": country_code,
                                "provider": "signalwire",
                                "price_monthly": 0.80,
                                "capabilities": ["voice", "sms"]
                            })
            except Exception as e:
                logger.warning(f"⚠️ SignalWire Search Failed: {e}")

        # --- D. Filter Results (Strict Region Check) ---
        # Some providers (like SignalWire) might return US numbers if IL is requested but not found.
        filtered_results = []
        for res in results:
            num = str(res.get("number", ""))
            
            # If searching for Israel, ensure it starts with +972
            if country_code == "IL" and not num.startswith("+972"):
                continue
                
            filtered_results.append(res)

        logger.info(f"🏁 Found total {len(filtered_results)} valid numbers (filtered from {len(results)}) across providers.")
        return filtered_results

    async def purchase_number(self, provider: str, phone_number: str, user_id: str) -> Dict[str, Any]:
        """
        Routes the purchase request to the correct provider.
        """
        logger.info(f"🛒 Purchasing {phone_number} via {provider} for user {user_id}")
        
        if provider == "twilio" and self.twilio_client:
            return self._purchase_twilio(phone_number, user_id)
        elif provider == "vonage" and self.vonage_client:
            return self._purchase_vonage(phone_number, user_id)
        elif provider == "signalwire" and self.sw_base:
            return await self._purchase_signalwire(phone_number, user_id)
        
        return {"status": "failed", "detail": "Provider not configured or unknown"}

    # --- Internal Purchase Logic ---

    def _purchase_twilio(self, phone_number: str, user_id: str):
        try:
            incoming_phone = self.twilio_client.incoming_phone_numbers.create(
                phone_number=phone_number,
                friendly_name=f"User {user_id}"
            )
            # Update Webhooks
            incoming_phone.update(
                voice_url=f"{settings.BASE_URL}/webhooks/voice/incoming",
                voice_method="POST",
                sms_url=f"{settings.BASE_URL}/webhooks/sms/incoming",
                sms_method="POST"
            )
            return {"status": "success", "sid": incoming_phone.sid, "provider": "twilio"}
        except Exception as e:
            logger.error(f"Twilio Buy Error: {e}")
            return {"status": "failed", "detail": str(e)}

    def _purchase_vonage(self, phone_number: str, user_id: str):
        try:
            clean_num = phone_number.replace("+", "")
            self.vonage_client.numbers.buy(country="IL", msisdn=clean_num)
            self.vonage_client.numbers.update(
                country="IL", 
                msisdn=clean_num, 
                app_id=settings.VONAGE_APP_ID
            )
            return {"status": "success", "provider": "vonage"}
        except Exception as e:
            logger.error(f"Vonage Buy Error: {e}")
            return {"status": "failed", "detail": str(e)}

    async def _purchase_signalwire(self, phone_number: str, user_id: str):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.sw_base}/IncomingPhoneNumbers.json",
                    data={"PhoneNumber": phone_number, "FriendlyName": user_id},
                    auth=(self.sw_project, self.sw_token)
                )
                if resp.status_code != 201:
                    return {"status": "failed", "detail": resp.text}
                
                sid = resp.json().get("sid")
                await client.post(
                    f"{self.sw_base}/IncomingPhoneNumbers/{sid}.json",
                    data={
                        "VoiceUrl": f"{settings.BASE_URL}/webhooks/voice/incoming",
                        "SmsUrl": f"{settings.BASE_URL}/webhooks/sms/incoming"
                    },
                    auth=(self.sw_project, self.sw_token)
                )
                return {"status": "success", "sid": sid, "provider": "signalwire"}
        except Exception as e:
            return {"status": "failed", "detail": str(e)}

# Export Singleton
phone_service = TelephonyService()