# src/tasks/followup_tasks.py
import logging
from datetime import datetime, timedelta
from src.database.session import SessionLocal
from src.database.models import Lead, User, LeadStatus
from src.services.communication.whatsapp import whatsapp_adapter

logger = logging.getLogger("LeadFlowSystem")

async def process_smart_followups():
    """
    Finds leads created between 24-48 hours ago that are still in 'NEW' status
    and sends them a gentle nudge via WhatsApp.
    """
    db = SessionLocal()
    try:
        # 1. Define the timeframe (e.g., exactly 24 hours ago)
        time_threshold = datetime.utcnow() - timedelta(hours=24)
        
        # 2. Query 'NEW' leads that haven't been contacted for follow-up yet
        # We also join with User to get business details
        stale_leads = db.query(Lead).join(User).filter(
            Lead.status == LeadStatus.NEW,
            Lead.created_at <= time_threshold,
            Lead.needs_followup == False # Using this as a flag that we haven't followed up yet
        ).all()

        logger.info(f"🔍 Follow-up Check: Found {len(stale_leads)} leads waiting for a nudge.")

        for lead in stale_leads:
            try:
                # Get the business name from the target user
                biz_name = lead.user.business_name or "העסק שלנו"
                clean_phone = ''.join(filter(str.isdigit, lead.phone_number))
                
                message = f"היי {lead.name}, זה שוב הבוט של {biz_name}. רק רציתי לוודא שהסתדרת וקיבלת את כל המידע שרצית? 😊"
                
                # Send the message
                success = whatsapp_adapter.send_message(to_phone=clean_phone, text=message)
                
                if success:
                    # Update lead so we don't nudge them again tomorrow
                    lead.needs_followup = True 
                    lead.status = LeadStatus.IN_PROGRESS
                    logger.info(f"✅ Follow-up sent to {lead.name} ({clean_phone})")
                
            except Exception as e:
                logger.error(f"❌ Failed to nudge lead {lead.id}: {str(e)}")

        db.commit()
    except Exception as e:
        logger.error(f"🚨 Critical error in follow-up task: {str(e)}")
        db.rollback()
    finally:
        db.close()