# src/tasks/followup_tasks.py
import logging
import asyncio
from datetime import datetime, timedelta
from src.database.session import SessionLocal
from src.database.models import Lead, User, LeadStatus, Message
from src.services.communication.whatsapp import whatsapp_adapter
from src.services.ai.engine import ai_engine
# from src.worker import celery_app # Uncomment if using direct celery app decorator

logger = logging.getLogger("LeadFlowFollowUp")

# @celery_app.task(name="tasks.process_smart_followups") # Register as Celery task
def process_smart_followups():
    """
    Background worker task: Scans stale leads and uses AI to generate 
    and send personalized follow-up messages via WhatsApp.
    """
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If running inside an existing event loop context
        asyncio.create_task(_async_process_smart_followups())
    else:
        loop.run_until_complete(_async_process_smart_followups())

async def _async_process_smart_followups():
    db = SessionLocal()
    try:
        # Define timeframe (e.g., leads created 24+ hours ago still in NEW status)
        time_threshold = datetime.utcnow() - timedelta(hours=24)
        
        stale_leads = db.query(Lead).join(User).filter(
            Lead.status == LeadStatus.NEW,
            Lead.created_at <= time_threshold,
            Lead.needs_followup == False,
            Lead.bot_active == True # Only follow up if human takeover hasn't muted the bot
        ).all()

        logger.info(f"🔍 AI Follow-up Check: Found {len(stale_leads)} stale leads waiting for a smart nudge.")

        for lead in stale_leads:
            try:
                owner = lead.user
                biz = owner.business_profile
                clean_phone = ''.join(filter(str.isdigit, lead.phone_number))

                # Fetch last few messages for context
                history = db.query(Message).filter(Message.lead_id == lead.id).order_by(Message.created_at.desc()).limit(5).all()
                history.reverse()
                history_str = "\n".join([f"{'Customer' if m.sender_type=='user' else 'AI'}: {m.content}" for m in history])

                # Construct AI prompt for personalized follow-up
                system_prompt = f"""
                You are 'Liron', the expert sales assistant for '{owner.business_name}'.
                Goal: Write a short, friendly, and natural Hebrew WhatsApp follow-up message to a potential client who hasn't replied in 24 hours.
                
                Business Info: {biz.products_services if biz else 'Professional service provider'}
                Tone: {biz.ai_tone if biz else 'Friendly and professional'}
                
                Recent Chat History:
                {history_str if history_str else 'No prior conversation.'}
                
                IMPORTANT: Return ONLY a JSON object with a single key 'followup_text' containing your drafted message in Hebrew.
                """

                ai_res = await ai_engine.analyze_interaction(
                    system_prompt=system_prompt, 
                    text_input="Generate follow-up message", 
                    sender_name=lead.name,
                    expected_schema='{"followup_text": "string"}'
                )

                message_text = ai_res.get("followup_text")
                if not message_text:
                    message_text = f"היי {lead.name}, רציתי לבדוק אם יש שאלות נוספות שאוכל לעזור לגביהן? 😊"

                # Send via WhatsApp adapter
                success = whatsapp_adapter.send_message(to_phone=clean_phone, text=message_text)
                
                if success:
                    lead.needs_followup = True 
                    lead.status = LeadStatus.IN_PROGRESS
                    
                    # Log message in DB
                    db.add(Message(lead_id=lead.id, sender_type="bot", content=message_text))
                    db.commit()
                    
                    logger.info(f"✅ AI Follow-up sent to {lead.name} ({clean_phone})")
            
            except Exception as e:
                logger.error(f"❌ Failed to process follow-up for lead {lead.id}: {str(e)}")

    except Exception as e:
        logger.error(f"🚨 Critical error in smart follow-up task: {str(e)}")
        db.rollback()
    finally:
        db.close()