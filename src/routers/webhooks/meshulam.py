# src/routers/webhooks/meshulam.py
import os
import logging
import hmac
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from fpdf import FPDF # NEW: PDF Generator

from src.database.session import SessionLocal
from src.database.models import User, PlanTier, SubscriptionStatus # FIXED: Added SubscriptionStatus
from src.config import settings
from src.services.communication.email import email_service 
from src.security.audit import audit_service # FIXED: Added Audit Log

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
    
    data_str = f"{data.get('transactionId', '')}{data.get('sum', '')}{data.get('status', '')}"
    expected_sig = hmac.new(api_key.encode(), data_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, received_sig)

def generate_invoice_pdf(transaction_id: str, amount: str, user_name: str, user_email: str) -> str:
    """
    Generates a professional PDF invoice and saves it temporarily to the server.
    Returns the file path.
    """
    pdf = FPDF()
    pdf.add_page()
    
    # Fonts and Colors
    pdf.set_font("Arial", 'B', 24)
    pdf.set_text_color(79, 70, 229) # Indigo color matching our brand
    
    # Header
    pdf.cell(200, 20, txt="TAX INVOICE / RECEIPT", ln=True, align='C')
    pdf.set_text_color(50, 50, 50)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="MyLeads AI Ltd.", ln=True, align='C')
    
    pdf.ln(10)
    
    # Invoice Details
    pdf.set_font("Arial", size=12)
    current_date = datetime.now().strftime("%B %d, %Y")
    
    details = [
        f"Date: {current_date}",
        f"Invoice Number: INV-{transaction_id}",
        f"Billed To: {user_name} ({user_email})",
        "",
        "Description: MyLeads AI - PRO Plan (Monthly Subscription)",
        f"Total Amount Paid: NIS {amount}.00",
        "",
        "Status: PAID IN FULL",
        "Payment Method: Credit Card via Meshulam"
    ]
    
    for line in details:
        if "Total Amount" in line or "Status" in line:
            pdf.set_font("Arial", 'B', 12)
        else:
            pdf.set_font("Arial", size=12)
        pdf.cell(200, 8, txt=line, ln=True, align='L')
        
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(200, 10, txt="Thank you for your business. This is a computer-generated document.", ln=True, align='C')
    
    # Ensure the 'temp' directory exists
    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/Invoice_{transaction_id}.pdf"
    
    pdf.output(file_path)
    return file_path

@router.post("/notify")
async def meshulam_payment_notify(request: Request):
    """
    Handles payment notifications from Meshulam (IPN).
    Updates user plan, generates a PDF invoice, handles DUNNING, and emails it.
    """
    try:
        form_data = await request.form()
        data = dict(form_data)
        logger.info(f"Received Meshulam IPN. Transaction ID: {data.get('transactionId')}")

        transaction_id = data.get("transactionId") or data.get("id")
        payment_status = str(data.get("status", "")).lower()
        amount = data.get("sum", "0")
        customer_email = data.get("customField") or data.get("email") 

        if not customer_email:
            return {"status": "error", "message": "Email missing"}

        db = next(get_db_session())
        user = db.query(User).filter(User.email == customer_email.lower()).first()
        
        if not user:
            return {"status": "user_not_found"}

        # SUCCESSFUL PAYMENT
        if payment_status in ["1", "success", "approved"]:
            if user.plan_tier != PlanTier.PRO or user.subscription_status != SubscriptionStatus.ACTIVE:
                # 1. Upgrade User
                user.plan_tier = PlanTier.PRO
                user.subscription_status = SubscriptionStatus.ACTIVE
                db.commit()
                logger.info(f"✅ SUCCESS: User {user.email} upgraded to PRO via Meshulam.")
                
                # 2. Generate PDF Invoice
                pdf_path = generate_invoice_pdf(
                    transaction_id=str(transaction_id), 
                    amount=str(amount), 
                    user_name=user.name, 
                    user_email=user.email
                )
                
                # 3. Send Email with Attachment
                await email_service.send_payment_receipt(
                    to_email=user.email,
                    pdf_path=pdf_path
                )
                
                # 4. Cleanup: Delete the PDF from the server after sending
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)

            return {"status": "success", "transaction": transaction_id}

        # TIER 3: DUNNING MANAGEMENT (FAILED PAYMENT)
        elif payment_status in ["2", "failed", "rejected", "declined"]:
            logger.warning(f"💳 Payment failed for User {user.email}. Initiating Dunning process.")
            
            # 1. Downgrade Status
            user.subscription_status = SubscriptionStatus.PAST_DUE
            db.commit()
            
            # 2. Log the failure
            audit_service.log(
                db=db,
                user_id=str(user.id),
                action="SUBSCRIPTION_PAYMENT_FAILED",
                details={"transaction_id": str(transaction_id), "amount": str(amount)}
            )
            
            # 3. Send Dunning Warning Email
            await email_service.send_dunning_email(
                to_email=user.email, 
                user_name=user.name
            )
            
            return {"status": "success", "message": "Dunning process initiated"}

        # UNKNOWN STATUS
        return {"status": "ignored", "reason": "incomplete_status"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"🔥 Meshulam Webhook Failure: {e}")
        return {"status": "error"}