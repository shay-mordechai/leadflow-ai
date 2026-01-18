# src/services/payment_service.py
import requests
import logging
import os
from src.config import settings

logger = logging.getLogger("PaymentService")

class MeshulamService:
    def __init__(self):
        # Load credentials from settings/env
        self.page_code = os.getenv("MESHULAM_PAGE_CODE")
        self.api_key = os.getenv("MESHULAM_API_KEY")
        # Sandbox URL. For production, change to: https://meshulam.co.il/api/light/server/1.0
        self.base_url = "https://sandbox.meshulam.co.il/api/light/server/1.0" 
        self.app_url = os.getenv("BASE_URL", "http://localhost:8000")

    def generate_payment_link(self, user_id: str, user_name: str, amount: float = 99.0):
        """
        Generates a redirect URL for the user to pay via Meshulam.
        We use 'cField1' to pass the user_id so we can identify them in the webhook.
        """
        payload = {
            "pageCode": self.page_code,
            "userId": self.page_code, # In Meshulam, userId often refers to the business ID
            "sum": str(amount),
            "successUrl": f"{self.app_url}/dashboard?payment=success",
            "cancelUrl": f"{self.app_url}/dashboard?payment=cancel",
            "description": "LeadFlow AI - Pro Plan Upgrade",
            "pageField[fullName]": user_name,
            "cField1": str(user_id),  # CRITICAL: Connects the payment to the specific user
        }
        
        try:
            # Send request to Meshulam to create the transaction
            response = requests.post(f"{self.base_url}/createPaymentProcess", data=payload)
            data = response.json()
            
            # Check if status is positive (Meshulam uses 1 or higher for success)
            if data.get("status") and int(data["status"]) > 0:
                return {"status": "success", "url": data["url"]}
            else:
                logger.error(f"Meshulam Error Response: {data}")
                return {"status": "error", "message": "Could not generate payment link"}

        except Exception as e:
            logger.error(f"Payment Connection Error: {e}")
            return {"status": "error", "message": str(e)}

payment_service = MeshulamService()