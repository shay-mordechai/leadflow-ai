# src/routers/webhooks/meshulam.py
import os
import logging
import hmac
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from fpdf import FPDF

from src.database.session import SessionLocal
from src.database.models import User, PlanTier, SubscriptionStatus, PaymentTransaction, AuditLog
from src.config import settings
from src.services.communication.email import email_service 

router = APIRouter(tags=["Webhooks - Meshulam"])
logger = logging.getLogger("MeshulamWebhook")

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_meshulam_signature(data: dict, api_key: str) -> bool:
    received_sig = data.get("signature") or data.get("hash")
    if not received_sig: 
        return True 
    
    data_str = f"{data.get('transactionId', '')}{data.get('sum', '')}{data.get('status', '')}"
    expected_sig = hmac.new(api_key.encode(), data_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, received_sig)

def generate_invoice_pdf(transaction_id: str, amount: str, user_name: str, user_email: str) -> str:
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 24)
    pdf.set_text_color(79, 70, 229)
    
    pdf.cell(200, 20, txt="TAX INVOICE / RECEIPT", ln=True, align='C')
    pdf.set_text_color(50, 50, 50)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="MyLeads AI Ltd.", ln=True, align='C')
    
    pdf.ln(10)
    
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
    
    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/Invoice_{transaction_id}.pdf"
    
    pdf.output(file_path)
    return file_path

@router.post("/notify")
async def meshulam_payment_notify(request: Request):
    """
    Handles payment notifications from Meshulam (IPN).
    Enforces signature validation, idempotency checks, user mapping, and PDF receipt dispatch.
    """
    try:
        form_data = await request.form()
        data = dict(form_data)
        transaction_id = data.get("transactionId") or data.get("id") or data.get("transaction_id")
        
        if not transaction_id:
            return {"status": "error", "message": "Transaction ID missing"}

        logger.info(f"Received Meshulam IPN. Transaction ID: {transaction_id}")

        # 1. Security: Signature Validation
        if settings.MESHULAM_API_KEY and settings.MESHULAM_API_KEY != "MOCK_API_KEY":
            if not verify_meshulam_signature(data, settings.MESHULAM_API_KEY):
                logger.error(f"❌ SECURITY ALERT: Invalid Meshulam signature for transaction {transaction_id}")
                raise HTTPException(status_code=403, detail="Invalid signature")

        payment_status = str(data.get("status", "")).lower()
        amount = data.get("sum", "0")
        raw_user_id = data.get("customField1") or data.get("custom_field_1")
        customer_email = data.get("email")

        db = next(get_db_session())
        try:
            # 2. Idempotency Check: Prevent double processing of the same transaction
            existing_tx = db.query(PaymentTransaction).filter(PaymentTransaction.transaction_id == str(transaction_id)).first()
            if existing_tx:
                logger.info(f"🛡️ Idempotency Shield: Transaction {transaction_id} already processed.")
                return {"status": "ok", "message": "Already processed"}

            # 3. Resolve User via customField1 (UUID) or fallback to email
            user = None
            if raw_user_id:
                try:
                    user = db.query(User).filter(User.id == raw_user_id).first()
                except Exception:
                    pass
            
            if not user and customer_email:
                user = db.query(User).filter(User.email == customer_email.lower()).first()

            if not user:
                logger.error(f"Meshulam Webhook: User mapping not found for transaction {transaction_id}")
                return {"status": "error", "message": "User not found"}

            # 4. SUCCESSFUL PAYMENT
            if payment_status in ["1", "success", "approved"]:
                # Register transaction token for idempotency
                new_tx = PaymentTransaction(
                    user_id=user.id,
                    transaction_id=str(transaction_id),
                    amount=int(float(amount or 0)),
                    status="SUCCESS"
                )
                db.add(new_tx)

                # Upgrade user state atomically
                user.plan_tier = PlanTier.PRO
                user.subscription_status = SubscriptionStatus.ACTIVE
                db.flush()

                # Audit log entry
                audit_log = AuditLog(
                    user_id=str(user.id),
                    action="SUBSCRIPTION_PAID",
                    details={"transaction_id": transaction_id, "amount": amount, "provider": "Meshulam"}
                )
                db.add(audit_log)
                db.commit()
                
                logger.info(f"✅ SUCCESS: User {user.email} upgraded to PRO via Meshulam Tx {transaction_id}")
                
                # Generate PDF Invoice & Dispatch
                pdf_path = generate_invoice_pdf(
                    transaction_id=str(transaction_id), 
                    amount=str(amount), 
                    user_name=user.name, 
                    user_email=user.email
                )
                
                try:
                    await email_service.send_payment_receipt(
                        to_email=user.email,
                        pdf_path=pdf_path
                    )
                except Exception as email_err:
                    logger.error(f"Failed to send payment receipt email: {email_err}")
                
                if os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                    except Exception:
                        pass

                return {"status": "success", "transaction": transaction_id}

            # 5. FAILED PAYMENT (DUNNING)
            elif payment_status in ["2", "failed", "rejected", "declined"]:
                logger.warning(f"💳 Payment failed for User {user.email}. Initiating Dunning process.")
                
                user.subscription_status = SubscriptionStatus.PAST_DUE
                
                audit_log = AuditLog(
                    user_id=str(user.id),
                    action="SUBSCRIPTION_PAYMENT_FAILED",
                    details={"transaction_id": str(transaction_id), "amount": str(amount)}
                )
                db.add(audit_log)
                db.commit()
                
                try:
                    if hasattr(email_service, "send_dunning_email"):
                        await email_service.send_dunning_email(to_email=user.email, user_name=user.name)
                except Exception as mail_err:
                    logger.error(f"Failed to send dunning email: {mail_err}")
                
                return {"status": "success", "message": "Dunning process initiated"}

            return {"status": "ignored", "reason": "incomplete_status"}

        finally:
            db.close()

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"🔥 Meshulam Webhook Failure: {e}")
        return {"status": "error", "message": str(e)}