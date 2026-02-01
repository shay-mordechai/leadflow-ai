# src/services/phone_service.py
import httpx
import logging
from typing import List, Dict, Any
from src.config import settings

logger = logging.getLogger("PhoneService")

BASE_URL = settings.BASE_URL
VOICE_WEBHOOK = f"{BASE_URL}/webhooks/voice/incoming"
SMS_WEBHOOK = f"{BASE_URL}/webhooks/whatsapp/twilio"

class PhoneService:
    def __init__(self):
        self.project_id = (settings.SIGNALWIRE_PROJECT_ID or "").strip()
        self.auth_token = (settings.SIGNALWIRE_AUTH_TOKEN or "").strip()
        raw_space = (settings.SIGNALWIRE_SPACE_URL or "").strip()
        
        # Clean URL
        clean_host = raw_space.replace("https://", "").replace("http://", "").strip("/")
        
        if self.project_id and clean_host:
            self.api_base = f"https://{clean_host}/api/laml/2010-04-01/Accounts/{self.project_id}"
        else:
            self.api_base = None

    def _get_auth(self):
        return (self.project_id, self.auth_token)

    async def search_best_numbers(self, country_code: str, area_code: str = None) -> List[Dict]:
        if not self.api_base:
            print("❌ Error: Missing API Base URL", flush=True)
            return []

        params = {"Limit": 5}
        if area_code: params["AreaCode"] = area_code
        
        # --- FIX: ADDED .json HERE ---
        endpoint = f"{self.api_base}/AvailablePhoneNumbers/{country_code}/Local.json"
        
        print(f"DEBUG: Requesting -> {endpoint}", flush=True)

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(endpoint, params=params, auth=self._get_auth())
                
                if resp.status_code != 200:
                    print(f"❌ API Error: {resp.text}", flush=True)
                    return []
                
                data = resp.json()
                results = []
                # Twilio/SignalWire JSON key usually has no "_list" suffix in pure JSON, checking both just in case
                numbers = data.get("available_phone_numbers", [])
                
                for n in numbers:
                    results.append({
                        "number": n["phone_number"],
                        "country": n.get("iso_country", "US"),
                        "provider": "signalwire"
                    })
                return results
            except Exception as e:
                print(f"❌ Exception: {e}", flush=True)
                return []

    async def purchase_number(self, phone_number: str, user_id: str, friendly_name: str) -> Dict[str, Any]:
        if not self.api_base: return {"status": "failed", "detail": "Missing Credentials"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                print(f"DEBUG: Purchasing {phone_number}...", flush=True)
                
                # --- FIX: ADDED .json HERE ---
                buy_resp = await client.post(
                    f"{self.api_base}/IncomingPhoneNumbers.json",
                    data={"PhoneNumber": phone_number, "FriendlyName": f"{friendly_name} ({user_id})"},
                    auth=self._get_auth()
                )
                
                if buy_resp.status_code != 201:
                    print(f"❌ Purchase Failed: {buy_resp.text}", flush=True)
                    return {"status": "failed", "detail": f"Provider Error: {buy_resp.text}"}

                sid = buy_resp.json()["sid"]
                print(f"✅ Bought! SID: {sid}. Configuring...", flush=True)

                # --- FIX: ADDED .json HERE ---
                await client.post(
                    f"{self.api_base}/IncomingPhoneNumbers/{sid}.json",
                    data={
                        "VoiceUrl": VOICE_WEBHOOK, "VoiceMethod": "POST",
                        "SmsUrl": SMS_WEBHOOK, "SmsMethod": "POST"
                    },
                    auth=self._get_auth()
                )

                return {"status": "success", "number": phone_number, "sid": sid}
            except Exception as e:
                return {"status": "failed", "detail": str(e)}

phone_service = PhoneService()