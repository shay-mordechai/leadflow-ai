# src/routers/webhooks/meshulam.py
import logging
import hmac
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

# Internal imports
from src.database.session import get_db
from src.database.models import User, PlanTier
from src.config import settings

# Router Configuration
router = APIRouter(tags=["Webhooks - Meshulam"])
logger = logging.getLogger("MeshulamWebhook")

def verify_meshulam_signature(data: dict, api_key: str) -> bool:
    """
    Security: Verify the authenticity of the Meshulam IPN.
    Prevents malicious users from spoofing payment success notifications.
    """
    received_sig = data.get("signature")
    if not received_sig:
        return False

    # Meshulam Logic: Concatenate specific fields to verify the hash.
    # Note: Ensure these fields match your Meshulam implementation's signature string.
    # Typical pattern: transactionId + sum + status
    transaction_id = data.get("transactionId") or data.get("id", "")
    amount = data.get("sum", "")
    payment_status = data.get("status", "")
    
    data_str = f"{transaction_id}{amount}{payment_status}"
    
    # Calculate expected HMAC-SHA256 signature using your Meshulam API Key
    expected_sig = hmac.new(
        api_key.encode(), 
        data_str.encode(), 
        hashlib.sha256
    ).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_sig, received_sig)

@router.post("/notify")
async def meshulam_payment_notify(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handles payment notifications from Meshulam (IPN).
    Updates the user's plan to PRO only after signature validation.
    """
    try:
        # 1. Parse Form Data (Meshulam sends x-www-form-urlencoded)
        form_data = await request.form()
        data = dict(form_data)
        
        logger.info(f"Received Meshulam IPN. Transaction ID: {data.get('transactionId')}")

        # 2. SECURITY: Signature Verification
        # This prevents anyone from calling this endpoint without knowing your Meshulam API Key
        if not verify_meshulam_signature(data, settings.MESHULAM_API_KEY):
            logger.error(f"❌ UNAUTHORIZED: Invalid signature from IP {request.client.host}")
            # We return 401 to signal authentication failure
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid signature"
            )

        # 3. Extract Key Fields
        transaction_id = data.get("transactionId") or data.get("id")
        payment_status = data.get("status", "").lower()
        customer_email = data.get("customField") or data.get("email") 

        # 4. Validate Transaction Status
        # Meshulam typically uses '1' for success. Adjust based on your provider settings.
        if str(payment_status) not in ["1", "success", "approved"]:
            logger.warning(f"Payment not successful. Status: {payment_status}. Transaction: {transaction_id}")
            return {"status": "ignored", "reason": "incomplete_status"}

        if not customer_email:
            logger.error(f"Missing customer email for transaction: {transaction_id}")
            return {"status": "error", "message": "Email missing"}

        # 5. Database Logic
        user = db.query(User).filter(User.email == customer_email.lower()).first()
        
        if not user:
            logger.error(f"Payment received but user not found: {customer_email}")
            return {"status": "user_not_found"}

        # 6. Apply Upgrade (Idempotent: Only update if not already PRO)
        if user.plan_tier != PlanTier.PRO:
            user.plan_tier = PlanTier.PRO
            db.commit()
            logger.info(f"✅ SUCCESS: User {user.email} upgraded to PRO via Meshulam.")
        else:
            logger.info(f"User {user.email} is already PRO. No action taken.")

        return {"status": "success", "transaction": transaction_id}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"🔥 Meshulam Webhook Failure: {str(e)}")
        # We return 200 even on some internal errors to stop Meshulam from retrying 
        # unless we actually want a retry. Generic error response follows:
        return {"status": "error", "message": "Internal processing error"}