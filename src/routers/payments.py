# src/routers/payments.py
import logging
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from src.database.session import get_db
from src.database.models import User, PlanTier, SubscriptionStatus
from src.services.payment_service import payment_service
from src.services.phone_service import phone_service  # The new abstract service
from src.routers.ui import get_current_user

router = APIRouter()
logger = logging.getLogger("Payments")

@router.get("/checkout/pro")
async def checkout_pro(user: User = Depends(get_current_user)):
    """
    Initiates the payment flow. Redirects user to Meshulam payment page.
    """
    # Generate the payment link via Meshulam API
    result = payment_service.generate_payment_link(
        user_id=str(user.id),
        user_name=user.name,
        amount=99.00
    )
    
    if result["status"] == "success":
        return RedirectResponse(result["url"])
    
    # If failed, redirect back to dashboard with error parameter
    return RedirectResponse("/dashboard?error=payment_init_failed")

@router.post("/webhook/meshulam")
async def meshulam_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives update from Meshulam after payment is completed.
    This runs server-to-server.
    """
    try:
        # Meshulam sends data as Form Data
        form_data = await request.form()
        data = dict(form_data)
        
        logger.info(f"💰 Webhook Received: {data}")

        # Extract critical data
        # 'status' = 1 means approved transaction
        transaction_status = data.get("status")
        # 'cField1' contains the User ID we sent during checkout initialization
        user_id = data.get("cField1") 

        # 1. Validate Transaction Status
        if str(transaction_status) != '1':
            logger.warning(f"⚠ Payment failed or canceled. UserID: {user_id}, Status: {transaction_status}")
            return "Ignored"

        # 2. Fetch User from Database
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"❌ User not found for ID: {user_id}")
            return "User Not Found"

        # 3. Update Subscription Status
        logger.info(f"✅ Payment Approved for User {user.name}. Upgrading account...")
        user.plan_tier = PlanTier.PRO
        user.subscription_status = SubscriptionStatus.ACTIVE
        
        # 4. Provision Phone Number (Smart Waterfall Logic)
        if user.assigned_phone_number is None:
            logger.info(f"📞 Attempting to provision number for User {user.id}...")
            
            # Call the abstract phone service to find the best provider
            new_number, provider = phone_service.provision_best_number(str(user.id))
            
            if new_number:
                # Success: Save number and provider to DB
                user.assigned_phone_number = new_number
                user.phone_provider = provider 
                logger.info(f"🎉 New Number Assigned: {new_number} via {provider}")
            else:
                # Failure: No numbers available in Israel (Regulatory or Stock issue)
                # We mark it as 'PENDING_SETUP' so the UI can show a 'Processing' message
                # instead of crashing or showing nothing.
                logger.critical(f"🚨 ALERT: User {user.id} paid but NO NUMBER available (Israel Only Policy).")
                user.assigned_phone_number = "PENDING_SETUP"

        # 5. Commit Changes
        db.commit()
        return "OK"

    except Exception as e:
        logger.error(f"🔥 Webhook Critical Error: {e}")
        return "Error"