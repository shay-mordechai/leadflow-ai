# src/routers/settings.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4
from typing import Optional, List

from src.database.session import get_db
from src.database.models import User, BusinessProfile, AIAgent
from src.security.dependencies import get_current_user
from src.schemas.user import AISettingsSchema, AIAgentSchema
from src.security.audit import audit_service
from pydantic import BaseModel

router = APIRouter(tags=["AI Configuration"])
logger = logging.getLogger("LeadFlowSystem")

# --- Schemas ---
class ChatMessage(BaseModel):
    role: str
    content: str

class SimulateRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

@router.get("", response_model=AISettingsSchema)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch current Business Profile and AI Agent settings."""
    profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
    agent = db.query(AIAgent).filter(AIAgent.user_id == current_user.id).first()
    
    # Fallback if no profile exists yet
    if not profile:
        return AISettingsSchema(
            business_name=current_user.business_name or current_user.name,
            business_type=current_user.business_type or "General",
            ai_tone="Professional",
            products_services="",
            custom_instructions="",
            summary_template="",
            ai_agent=None
        )
    
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
        summary_template=profile.summary_template,
        ai_agent=agent_data
    )

@router.post("", status_code=status.HTTP_200_OK)
def update_settings(
    data: AISettingsSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update Business Profile and AI Agent configuration.
    """
    try:
        # 1. Upsert Business Profile
        profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == current_user.id).first()
        
        if not profile:
            logger.info(f"Creating new business profile for user {current_user.email}")
            profile = BusinessProfile(
                id=uuid4(),
                user_id=current_user.id,
                business_name=data.business_name,
                business_type=data.business_type,
                ai_tone=data.ai_tone,
                products_services=data.products_services,
                custom_instructions=data.custom_instructions,
                summary_template=data.summary_template
            )
            db.add(profile)
        else:
            profile.business_name = data.business_name
            profile.business_type = data.business_type
            profile.ai_tone = data.ai_tone
            profile.products_services = data.products_services
            profile.custom_instructions = data.custom_instructions
            profile.summary_template = data.summary_template
            
        # 2. Upsert AI Agent (The Brain)
        agent = db.query(AIAgent).filter(AIAgent.user_id == current_user.id).first()
        master_prompt = _generate_master_prompt(data)
        
        if not agent:
            agent = AIAgent(
                id=uuid4(),
                user_id=current_user.id,
                system_prompt=master_prompt,
                voice_id=data.ai_agent.voice_id if data.ai_agent else "female_calm_1",
                language=data.ai_agent.language if data.ai_agent else "he-IL",
                is_active=True
            )
            db.add(agent)
        else:
            agent.system_prompt = master_prompt
            if data.ai_agent:
                agent.voice_id = data.ai_agent.voice_id
                agent.language = data.ai_agent.language

        db.commit()

        # 3. Security: Audit Logging
        try:
            audit_service.log(
                db=db,
                user_id=str(current_user.id),
                action="AI_SETTINGS_UPDATED",
                details={
                    "business_name": data.business_name,
                    "ai_tone": data.ai_tone,
                    "prompt_length": len(master_prompt)
                }
            )
        except Exception as audit_err:
            logger.warning(f"Audit log failed but settings were saved: {audit_err}")

        return {"status": "success", "message": "Business Profile and AI Brain updated successfully."}

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update settings for {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="לא הצלחנו לשמור את השינויים. צוות הפיתוח קיבל דיווח."
        )

# --- NEW: AI Simulator Endpoint ---
@router.post("/simulate")
async def simulate_ai_chat(
    data: SimulateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Allows the user to test their AI prompt live from the dashboard.
    """
    agent = db.query(AIAgent).filter(AIAgent.user_id == current_user.id).first()
    
    if not agent or not agent.system_prompt:
        raise HTTPException(
            status_code=400, 
            detail="אנא הגדר ושמור את מוח ה-AI לפני השימוש בסימולטור."
        )

    try:
        # Format history for Gemini engine
        formatted_history = []
        for msg in data.history:
            sender = "model" if msg.role == "bot" else "user"
            
            # FIX: Gemini API crashes (HTTP 400) if the history starts with a 'model' message.
            # We skip 'bot' messages until we find the first 'user' message.
            if not formatted_history and sender == "model":
                continue
                
            formatted_history.append({
                "sender_type": "user" if sender == "user" else "bot",
                "content": msg.content
            })

        # Lazy load the AI Engine to prevent circular imports
        from src.services.ai.engine import ai_engine

        # Ask the AI Engine
        ai_response = await ai_engine.analyze_interaction(
            system_prompt=agent.system_prompt,
            text_input=data.message,
            sender_name="לקוח פוטנציאלי (סימולטור)",
            chat_history=formatted_history
        )

        return {
            "reply": ai_response.get("reply_text", "הייתה בעיה בניסוח התשובה."),
            "needs_human": ai_response.get("needs_human_escalation", False)
        }
        
    except Exception as e:
        logger.error(f"Simulator error for {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="שגיאה בסימולציית ה-AI")

def _generate_master_prompt(data: AISettingsSchema) -> str:
    """
    Synthesizes user inputs into a structured Gemini prompt for the agent.
    """
    tone_instruction = ""
    tone = data.ai_tone
    
    if tone == "רשמי" or tone == "Professional":
        tone_instruction = "דבר בשפה רשמית, מקצועית ומכובדת. השתמש בשפה גבוהה אך ברורה."
    elif tone == "חברי" or tone == "Friendly":
        tone_instruction = "דבר בגובה העיניים, היה אמפתי, נחמד, ושזור אימוג'ים במידה הנכונה."
    elif tone == "מכירתי" or tone == "Sales":
        tone_instruction = "המטרה העיקרית שלך היא להניע לפעולה. הצע הצעות ערך ברורות וצור דחיפות חיובית."
    else:
        tone_instruction = "דבר בצורה טבעית, שירותית ועניינית."

    prompt = f"""
    אתה נציג וירטואלי חכם של העסק: {data.business_name} (תחום: {data.business_type}).
    סגנון הדיבור שלך: {tone_instruction}
    
    מידע על העסק ושירותים (חשוב לענות לפיו):
    {data.products_services}
    
    הנחיות קריטיות מהבעלים:
    {data.custom_instructions}
    
    כללים מנחים:
    1. ענה קצר ולעניין (WhatsApp style).
    2. אם אתה לא יודע משהו, אל תמציא. בקש מהלקוח להמתין לנציג אנושי.
    3. השתמש תמיד בשפה שבה הלקוח פונה אליך (ברירת מחדל: עברית).
    """
    return prompt.strip()