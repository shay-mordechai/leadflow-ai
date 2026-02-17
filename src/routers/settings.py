# src/routers/settings.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4

from src.database.session import get_db
from src.database.models import User, BusinessProfile, AIAgent
from src.security.dependencies import get_current_user
from src.schemas.user import AISettingsSchema, AIAgentSchema

router = APIRouter(prefix="/settings", tags=["AI Configuration"])

@router.get("/", response_model=AISettingsSchema)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch current Business Profile and AI Agent settings."""
    # We query both tables
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    agent = db.query(AIAgent).filter(AIAgent.user_id == current_user.id).first()
    
    # If the user has no profile yet, return default empty structure
    if not profile:
        return AISettingsSchema(
            business_name=current_user.business_name or current_user.name,
            business_type=current_user.business_type or "General",
            ai_tone="Professional",
            products_services="",
            custom_instructions="",
            ai_agent=None
        )
    
    # Map the DB agent to the Pydantic schema if it exists
    agent_data = None
    if agent:
        agent_data = AIAgentSchema(
            system_prompt=agent.system_prompt,
            voice_id=agent.voice_id,
            language=agent.language,
            is_active=agent.is_active
        )
        
    return AISettingsSchema(
        business_name=profile.business_name,
        business_type=profile.business_type,
        ai_tone=profile.ai_tone,
        products_services=profile.products_services,
        custom_instructions=profile.custom_instructions,
        ai_agent=agent_data
    )

@router.post("/", status_code=status.HTTP_200_OK)
def update_settings(
    data: AISettingsSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update Business Profile and AI Agent configuration."""
    
    # --- 1. Upsert Business Profile ---
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    
    if not profile:
        profile = BusinessProfile(
            id=uuid4(),
            user_id=current_user.id,
            business_name=data.business_name,
            business_type=data.business_type,
            ai_tone=data.ai_tone,
            products_services=data.products_services,
            custom_instructions=data.custom_instructions
        )
        db.add(profile)
    else:
        profile.business_name = data.business_name
        profile.business_type = data.business_type
        profile.ai_tone = data.ai_tone
        profile.products_services = data.products_services
        profile.custom_instructions = data.custom_instructions
        
    # --- 2. Upsert AI Agent (The Brain) ---
    agent = db.query(AIAgent).filter(AIAgent.user_id == current_user.id).first()
    
    # If the user provided AI instructions but doesn't have an agent, create one
    if not agent:
        agent = AIAgent(
            id=uuid4(),
            user_id=current_user.id,
            # For now, we save the raw instructions.
            # Later, an external cron/job will convert this to a real prompt via Google AI Studio.
            system_prompt=f"Act as a professional assistant for {data.business_name}. Directives: {data.custom_instructions}",
            voice_id=data.ai_agent.voice_id if data.ai_agent else "default_voice_1",
            language=data.ai_agent.language if data.ai_agent else "he-IL"
        )
        db.add(agent)
    else:
        # Just update voice settings if provided
        if data.ai_agent:
            agent.voice_id = data.ai_agent.voice_id
            agent.language = data.ai_agent.language
        
        # Simple prompt generation (Can be replaced by Google AI call later)
        agent.system_prompt = f"Act as an assistant for {data.business_name}. {data.custom_instructions}"

    db.commit()
    return {"status": "success", "message": "Business Profile and AI Brain updated successfully."}