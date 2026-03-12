# src/routers/partners.py
import secrets
import string
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.database.session import get_db
from src.database.models import User, UserRole, PlanTier, Lead, LeadStatus
from src.security.hashing import get_password_hash
from src.security.dependencies import get_current_user

logger = logging.getLogger("LeadFlowSystem")

router = APIRouter(prefix="/api/v1/partners", tags=["Partners"])

# Schema for incoming registration request from the frontend
class PartnerRegistrationRequest(BaseModel):
    full_name: str
    email: EmailStr
    agency_name: str
    specialty: str
    experience: str

@router.post("/register")
async def register_partner(data: PartnerRegistrationRequest, db: Session = Depends(get_db)):
    """
    Registers a new Campaigner/Partner into the system.
    Partners are created as inactive by default, requiring Admin approval.
    """
    # 1. Check if email already exists in the system
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        # We don't expose if it's a client or partner, just that it exists
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email is already registered in the system."
        )

    # 2. Generate a secure random password (Partners don't set passwords in the form)
    # They can reset it later, or login via OTP if implemented.
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(16))
    
    # 3. Create the Partner Record
    new_partner = User(
        name=data.full_name,
        email=data.email,
        hashed_password=get_password_hash(temp_password),
        role=UserRole.PARTNER,              # Assigning the Partner Role!
        business_name=data.agency_name,     # Treat their agency as the business
        agency_name=data.agency_name,
        business_type=f"Agency: {data.specialty} ({data.experience})",
        plan_tier=PlanTier.PRO,             # Partners get PRO dashboard features
        is_active=False                     # IMPORTANT: Requires your manual approval
    )
    
    try:
        db.add(new_partner)
        db.commit()
        db.refresh(new_partner)
        
        # 4. Log the application
        logger.info(f"🤝 New Partner Application: {new_partner.email} | Agency: {new_partner.agency_name}")
        
        # TODO: Send an internal email/Slack notification to the Admin (You) 
        # to review and approve the partner.
        
        return {
            "success": True, 
            "message": "Partner application received successfully. Awaiting approval."
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to register partner: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your application."
        )

# --- NEW: Agency Performance Tracking ---
@router.get("/performance")
async def get_partners_performance(
    db: Session = Depends(get_db),
    # In a real app, ensure current_user has Role = ADMIN
    # current_user: User = Depends(get_current_user) 
):
    """
    Returns performance metrics for all registered campaigners (Partners).
    Used by the Agency Admin Dashboard to track lead volume and quality.
    """
    partners = db.query(User).filter(User.role == UserRole.PARTNER).all()
    
    performance_stats = []
    
    for partner in partners:
        clients = db.query(User).filter(User.partner_id == partner.id).all()
        client_ids = [c.id for c in clients]
        
        # Calculate Leads brought by this partner's clients
        total_leads = 0
        qualified_leads = 0
        
        if client_ids:
            all_client_leads = db.query(Lead).filter(Lead.user_id.in_(client_ids)).all()
            total_leads = len(all_client_leads)
            qualified_leads = sum(1 for l in all_client_leads if l.status == LeadStatus.QUALIFIED or l.ai_rating == 1)

        conversion_rate = 0
        if total_leads > 0:
            conversion_rate = round((qualified_leads / total_leads) * 100, 1)

        performance_stats.append({
            "id": str(partner.id),
            "name": partner.name,
            "agency_name": partner.agency_name,
            "is_active": partner.is_active,
            "clients_count": len(clients),
            "total_leads_brought": total_leads,
            "qualified_leads": qualified_leads,
            "conversion_rate": conversion_rate
        })
        
    # Sort by conversion rate (best performing campaigners first)
    performance_stats.sort(key=lambda x: x["conversion_rate"], reverse=True)
    
    return performance_stats