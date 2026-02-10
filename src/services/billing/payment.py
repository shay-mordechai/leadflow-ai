# src/services/payment.py
import requests
import logging
from src.config import settings

logger = logging.getLogger("PaymentService")

class MeshulamService:
    def __init__(self):
        self.page_code = getattr(settings, "MESHULAM_PAGE_CODE", "")
        self.api_key = getattr(settings, "MESHULAM_API_KEY", "")
        
        if getattr(settings, "APP_ENV", "development") == "production":
            self.base_url = "https://meshulam.co.il/api/light/server/1.0"
        else:
            self.base_url = "https://sandbox.meshulam.co.il/api/light/server/1.0"
            
        self.app_url = getattr(settings, "BASE_URL", "http://localhost:3000")

    def generate_payment_link(self, user_id: str, user_name: str, amount: float = 99.0):
        if not self.page_code or not self.api_key:
            logger.error("Meshulam credentials missing in settings.")
            return {"status": "error", "message": "Payment system not configured"}

        payload = {
            "pageCode": self.page_code,
            "userId": self.page_code,
            "sum": str(amount),
            "successUrl": f"{self.app_url}/dashboard?payment=success",
            "cancelUrl": f"{self.app_url}/dashboard?payment=cancel",
            "description": "LeadFlow AI - Pro Plan Upgrade",
            "pageField[fullName]": user_name,
            "cField1": str(user_id),
        }
        
        try:
            # SECURITY FIX (B113): Added timeout to prevent hanging connections
            response = requests.post(
                f"{self.base_url}/createPaymentProcess", 
                data=payload, 
                timeout=10
            )
            
            data = response.json()
            if data.get("status") and int(data["status"]) > 0:
                return {"status": "success", "url": data["url"]}
            else:
                logger.error(f"Meshulam Error: {data}")
                return {"status": "error", "message": "Failed to generate link"}

        except Exception as e:
            logger.error(f"Payment Connection Error: {e}")
            return {"status": "error", "message": str(e)}

payment_service = MeshulamService()