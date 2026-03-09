# src/services/billing/grow_service.py
import httpx
import logging
from typing import Dict, Any
from src.config import settings

logger = logging.getLogger("GrowPayments")

class GrowPaymentService:
    """
    Service to handle payments via Grow (formerly Meshulam) API.
    Official Documentation: https://doc.meshulam.co.il/
    """

    def __init__(self):
        # Determine environment
        self.is_sandbox = settings.APP_ENV != "production"
        self.base_url = "https://sandbox.meshulam.co.il/api/light/server/1.0" if self.is_sandbox else "https://api.meshulam.co.il/api/light/server/1.0"
        
        # Credentials (Injected from AWS SSM)
        self.user_id = getattr(settings, 'MESHULAM_USER_ID', "MOCK_USER")
        self.api_key = settings.MESHULAM_API_KEY
        self.page_code = settings.MESHULAM_PAGE_CODE

    async def create_payment_page(self, 
                                 amount: float, 
                                 description: str, 
                                 customer_name: str, 
                                 customer_phone: str,
                                 user_id: str,
                                 success_url: str,
                                 cancel_url: str) -> Dict[str, Any]:
        """
        Generates a secure payment link for the customer.
        We pass the internal user_id to custom_field_1 so the webhook can identify who paid.
        """
        endpoint = f"{self.base_url}/createPaymentProcess"
        
        payload = {
            "pageCode": self.page_code,
            "userId": self.user_id,
            "apiKey": self.api_key,
            "sum": amount,
            "description": description,
            "fullName": customer_name,
            "phone": customer_phone,
            "successUrl": success_url,
            "cancelUrl": cancel_url,
            "customField1": user_id, # Very important: This links the payment to your user
            "type": "1",             # 1 = Immediate payment
            "paymentType": "1"       # 1 = Credit Card
        }

        # Mock Mode for local development without actual keys
        if self.is_sandbox and not self.api_key:
            logger.warning("🛠️ Running in MOCK Mode. Returning fake payment URL.")
            return {
                "status": 1,
                "url": f"https://sandbox.meshulam.co.il/mock_payment?amount={amount}&customField1={user_id}",
                "process_id": "mock_process_123"
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, data=payload, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                if str(data.get("status")) != "1":
                    logger.error(f"Grow API Error: {data.get('err_msg')}")
                    return {"status": 0, "error": data.get("err_msg")}
                
                return {
                    "status": 1,
                    "url": data.get("url"),
                    "process_id": data.get("process_id")
                }
        except Exception as e:
            logger.error(f"Failed to connect to Grow/Meshulam API: {e}")
            return {"status": 0, "error": "Connection failed to payment gateway"}

# Global singleton instance
grow_service = GrowPaymentService()