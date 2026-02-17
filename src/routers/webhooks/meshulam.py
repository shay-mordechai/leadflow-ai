# src/routers/webhooks/meshulam.py
import logging
import hmac
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.database.session import SessionLocal
from src.database.models import User, PlanTier
from src.config import settings
from src.services.communication.email import email_service # NEW

router = APIRouter(tags=["Webhooks - Meshulam"])
logger = logging.getLogger("MeshulamWebhook")

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_meshulam_signature(data: dict, api_key: str) -> bool:
    received_sig = data.get("signature")
    if not received_sig: return False
    
    # Concatenate fields according to Meshulam documentation
    # (Update this string concatenation exactly as Meshulam requires in their docs)
    data_str = f"{data.get('transactionId', '')}{data.get('sum', '')}{data.get('status', '')}"
    
    expected_sig = hmac.new(api_key.encode(), data_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, received_sig)

@router.post("/notify")
async def meshulam_payment_notify(request: Request):
    """
    Handles payment notifications from Meshulam (IPN).
    Updates user plan and sends a receipt.
    """
    try:
        form_data = await request.form()
        data = dict(form_data)
        logger.info(f"Received Meshulam IPN. Transaction ID: {data.get('transactionId')}")

        # Signature Validation (Uncomment in Prod when API Key is set)
        # if not verify_meshulam_signature(data, settings.MESHULAM_API_KEY):
        #     raise HTTPException(status_code=401, detail="Invalid signature")

        transaction_id = data.get("transactionId") or data.get("id")
        payment_status = data.get("status", "").lower()
        amount = data.get("sum", "0")
        # Ensure we pass the user's email in the 'customField' when creating the Meshulam payment link!
        customer_email = data.get("customField") or data.get("email") 

        if str(payment_status) not in ["1", "success", "approved"]:
            return {"status": "ignored", "reason": "incomplete_status"}

        if not customer_email:
            return {"status": "error", "message": "Email missing"}

        # Open DB Session for Webhook
        db = next(get_db_session())
        user = db.query(User).filter(User.email == customer_email.lower()).first()
        
        if not user:
            return {"status": "user_not_found"}

        if user.plan_tier != PlanTier.PRO:
            user.plan_tier = PlanTier.PRO
            db.commit()
            logger.info(f"✅ SUCCESS: User {user.email} upgraded to PRO via Meshulam.")
            
            # --- NEW: Send Receipt Email ---
            receipt_body = f"""
            <h2>Payment Receipt - MyLeads AI</h2>
            <p>Hi {user.name},</p>
            <p>Thank you for your purchase! Your account has been upgraded to PRO.</p>
            <hr>
            <p><b>Transaction ID:</b> {transaction_id}</p>
            <p><b>Amount Paid:</b> ₪{amount}</p>
            <p><b>Status:</b> Success</p>
            <br>
            <p>The MyLeads AI Team</p>
            """
            await email_service.send_email(
                to_email=user.email,
                subject=f"Receipt for Transaction #{transaction_id}",
                html_content=receipt_body
            )

        return {"status": "success", "transaction": transaction_id}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"🔥 Meshulam Webhook Failure: {e}")
        return {"status": "error"}