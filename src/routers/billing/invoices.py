# src/routers/billing/invoices.py
import logging
import io
import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fpdf import FPDF

# Internal Project Imports
from src.security.dependencies import get_current_user
from src.database.session import get_db
from src.database.models import User, PlanTier

router = APIRouter(tags=["Billing - Invoices"])
logger = logging.getLogger("BillingInvoices")

# --- Schemas ---

class SubscriptionInfo(BaseModel):
    """Schema representing the user's active subscription state."""
    plan_tier: PlanTier
    is_active: bool

class InvoiceResponse(BaseModel):
    """Schema representing a single historical invoice/receipt."""
    id: str
    transaction_id: str
    amount: float
    currency: str = "ILS"
    date: datetime
    download_url: str

# --- PDF Generation Helper ---

def generate_invoice_pdf(invoice_id: str, user_name: str, user_email: str, amount: float, date_str: str) -> io.BytesIO:
    """
    Generates a professional PDF Tax Invoice / Receipt in memory.
    Using English to avoid RTL/Font embedding complexities in the MVP phase.
    """
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("helvetica", "B", 20)
    pdf.cell(0, 15, "TAX INVOICE / RECEIPT", ln=True, align="C")
    pdf.ln(10)
    
    # Company Info (Your SaaS)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 6, "MyLeads AI", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, "Email: support@my-leads.app", ln=True)
    pdf.cell(0, 6, "Website: https://my-leads.app", ln=True)
    pdf.ln(10)
    
    # Customer Info & Invoice Details
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(100, 8, "Billed To:", border=0)
    pdf.cell(90, 8, "Invoice Details:", border=0, ln=True)
    
    pdf.set_font("helvetica", "", 10)
    pdf.cell(100, 6, f"Name: {user_name}", border=0)
    pdf.cell(90, 6, f"Invoice No: {invoice_id}", border=0, ln=True)
    pdf.cell(100, 6, f"Email: {user_email}", border=0)
    pdf.cell(90, 6, f"Date: {date_str}", border=0, ln=True)
    pdf.ln(10)
    
    # Table Header
    pdf.set_font("helvetica", "B", 11)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(140, 10, " Description", border=1, fill=True)
    pdf.cell(50, 10, " Amount (ILS)", border=1, ln=True, align="C", fill=True)
    
    # Table Row
    pdf.set_font("helvetica", "", 11)
    pdf.cell(140, 10, " MyLeads AI - PRO Plan (Monthly Subscription)", border=1)
    pdf.cell(50, 10, f" {amount:.2f}", border=1, ln=True, align="C")
    
    # Total
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(140, 10, "TOTAL PAID:", border=0, align="R")
    pdf.cell(50, 10, f" ILS {amount:.2f}", border=0, ln=True, align="C")
    
    # Footer
    pdf.ln(20)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 10, "Thank you for upgrading your business with MyLeads AI!", ln=True, align="C")
    pdf.cell(0, 5, "This is a computer-generated document. No signature is required.", ln=True, align="C")
    
    # Output to BytesIO buffer
    pdf_bytes = pdf.output()
    return io.BytesIO(pdf_bytes)


# --- Routes ---

@router.get("/my-plan", response_model=SubscriptionInfo)
async def get_current_plan(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the current subscription status of the authenticated user.
    """
    return {
        "plan_tier": user.plan_tier,
        "is_active": user.is_active
    }


@router.get("/", response_model=List[InvoiceResponse])
async def list_user_invoices(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves a history of all generated invoices/receipts.
    Mocked implementation until DB Table 'invoices' is created.
    """
    logger.info(f"User {user.email} requested invoice history.")
    
    if user.plan_tier == PlanTier.PRO:
        # Generate a mock invoice for PRO users to demonstrate the UI
        return [{
            "id": f"INV-{str(user.id)[:8].upper()}",
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "amount": 199.00,
            "currency": "ILS",
            "date": datetime.utcnow(),
            "download_url": f"/api/billing/invoices/INV-{str(user.id)[:8].upper()}/pdf"
        }]
    
    return []


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates and returns the official PDF tax invoice for download.
    """
    logger.info(f"Generating PDF invoice {invoice_id} for user {user.email}.")
    
    # Ensure only PRO users (or users who actually paid) can download
    if user.plan_tier != PlanTier.PRO:
        raise HTTPException(status_code=403, detail="No active paid invoices found.")
    
    date_str = datetime.utcnow().strftime("%B %d, %Y")
    
    # Generate the PDF in memory
    pdf_buffer = generate_invoice_pdf(
        invoice_id=invoice_id,
        user_name=user.name,
        user_email=user.email,
        amount=199.00, # Mocked price for now
        date_str=date_str
    )
    
    # Stream the file back to the client directly
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=MyLeads_Invoice_{invoice_id}.pdf"
        }
    )