# src/routers/webhooks/meshulam.py
import logging
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import User, PlanTier
from src.config import settings

# Router Configuration
router = APIRouter(tags=["Webhooks - Meshulam"])
logger = logging.getLogger("MeshulamWebhook")

@router.post("/notify")
async def meshulam_payment_notify(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handles payment notifications from Meshulam (IPN).
    Updates the user's plan to PRO upon successful payment.
    
    Note: Meshulam sends data as Form Data, not JSON.
    """
    try:
        # 1. Parse Form Data
        form_data = await request.form()
        data = dict(form_data)
        
        logger.info(f"💰 Meshulam IPN Received: {data}")

        # 2. Extract Key Fields
        # Meshulam field names may vary based on configuration (e.g., 'customField', 'asmachta', 'status')
        transaction_id = data.get("transactionId") or data.get("id")
        status = data.get("status", "").lower()
        # We assume the user's email was passed as a custom field during checkout
        customer_email = data.get("customField") or data.get("email") 
        amount = data.get("sum")

        # 3. Validate Transaction Status
        # Usually '1' or 'success' indicates approved payment
        if str(status) not in ["1", "success", "approved"]:
            logger.warning(f"⚠️ Payment failed or pending. Transaction: {transaction_id}, Status: {status}")
            return {"status": "ignored"}

        # 4. Security: Signature Verification (Recommended)
        # TODO: Implement Meshulam's signature check using settings.MESHULAM_API_KEY
        # if not verify_meshulam_signature(data, settings.MESHULAM_API_KEY):
        #     logger.error("❌ Invalid Signature")
        #     return {"status": "unauthorized"}

        # 5. Update User Logic
        if not customer_email:
            logger.error("❌ No email provided in transaction data.")
            return {"status": "error", "detail": "Missing email"}

        user = db.query(User).filter(User.email == customer_email).first()
        
        if not user:
            logger.error(f"❌ User not found for email: {customer_email}")
            return {"status": "user_not_found"}

        # 6. Apply Upgrade
        if user.plan_tier != PlanTier.PRO:
            user.plan_tier = PlanTier.PRO
            db.commit()
            logger.info(f"✅ User {user.email} upgraded to PRO via Meshulam Transaction {transaction_id}")
            # Optional: Trigger 'src.services.communication.email.send_payment_receipt' here
        else:
            logger.info(f"ℹ️ User {user.email} is already PRO.")

        return {"status": "success", "message": "User updated"}

    except Exception as e:
        logger.error(f"🔥 Meshulam Webhook Error: {e}")
        # Return 200 OK even on error to prevent Meshulam from retrying endlessly
        return {"status": "error"}