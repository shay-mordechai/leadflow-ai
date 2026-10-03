# src/tasks/audio_tasks.py
import logging
from celery import shared_task
from sqlalchemy.orm import Session
from src.database.session import SessionLocal
from src.database.models import Message, Lead, User, MeetingSession, SessionStatus
from src.services.ai.engine import ai_engine
from src.services.ai.whisper import whisper_service
from src.services.communication.whatsapp import whatsapp_adapter

logger = logging.getLogger("AudioTask")

@shared_task(name="process_audio_message", bind=True, max_retries=3)
def process_audio_message(self, media_url: str, sender_id: str, bot_phone_number: str):
    """
    Asynchronous Celery task to download, transcribe, and respond to an audio message.
    """
    logger.info(f"🎧 Starting Async Audio Processing for {sender_id}")
    
    db: Session = SessionLocal()
    try:
        import asyncio
        transcription_text = asyncio.run(whisper_service.transcribe_from_url(media_url))
        
        if not transcription_text or "Error" in transcription_text:
            logger.error(f"❌ Transcription failed for {media_url}")
            whatsapp_adapter.send_message(to_phone=sender_id, text="סליחה, לא הצלחתי להבין את ההודעה הקולית. תוכל/י לכתוב לי במקום?")
            return "Transcription failed"

        logger.info(f"📝 Transcribed: {transcription_text[:50]}...")

        lead = db.query(Lead).filter(Lead.phone_number.contains(sender_id[-9:])).first()
        if not lead:
            logger.warning(f"⚠️ Lead not found for {sender_id} during audio processing.")
            return "Lead not found"
            
        user = db.query(User).filter(User.id == lead.user_id).first()
        agent = user.ai_agent

        db.add(Message(lead_id=lead.id, sender_type="user", content=f"🎤 [הודעה קולית]: {transcription_text}"))
        db.commit()

        if not lead.bot_active:
            logger.info("Bot is muted for this lead. Saving transcription only.")
            return "Bot muted"

        history = db.query(Message).filter(Message.lead_id == lead.id).order_by(Message.created_at.desc()).limit(10).all()
        history.reverse()
        history_str = "\n".join([f"{'Customer' if m.sender_type=='user' else 'AI'}: {m.content}" for m in history])

        system_prompt = f"{agent.system_prompt}\n\nContext History:\n{history_str}"

        ai_response = asyncio.run(ai_engine.analyze_interaction(
            system_prompt=system_prompt,
            text_input=transcription_text,
            sender_name=lead.name
        ))

        reply_text = ai_response.get('reply_text', "אני בודק את זה, רגע...")
        needs_human = ai_response.get("needs_human_escalation", False)

        if needs_human:
            lead.bot_active = False
            lead.requires_human = True
            db.commit()
            logger.info(f"🚨 Handoff triggered via Audio for {sender_id}")

        db.add(Message(lead_id=lead.id, sender_type="bot", content=reply_text))
        db.commit()
        
        whatsapp_adapter.send_message(to_phone=sender_id, text=reply_text)
        logger.info(f"✅ Audio Response sent to {sender_id}")
        
        return "Success"

    except Exception as e:
        logger.error(f"🔥 Error in process_audio_message: {e}")
        raise self.retry(exc=e, countdown=10)
        
    finally:
        db.close()

@shared_task(name="process_meeting_audio", bind=True, max_retries=1)
def process_meeting_audio(self, session_id: str, user_id: str, file_path: str):
    """
    Heavy task forced into SWAP. Transcribes a long audio file locally (Privacy First) 
    and uses AI to generate an NLP-structured summary.
    """
    logger.info(f"🎙️ Starting heavy NLP Meeting Session task for {session_id}")
    import os
    import asyncio
    
    db: Session = SessionLocal()
    try:
        session_record = db.query(MeetingSession).filter(MeetingSession.id == session_id).first()
        if not session_record:
            logger.error(f"Session {session_id} not found in DB.")
            return "Session not found"
        
        session_record.status = SessionStatus.PROCESSING
        db.commit()

        transcription = asyncio.run(whisper_service.transcribe_local_file(file_path))
        
        if "Error" in transcription or not transcription.strip():
            raise Exception("Local transcription failed or returned empty.")

        prompt = f"""
        You are an expert NLP Master Trainer and clinical supervisor.
        Analyze the following session transcription and provide a highly professional, structured summary.
        
        Format your response in Hebrew exactly like this, using bullet points and clear paragraphs:
        
        📋 **נושאים מרכזיים (Key Themes)**
        [פרט את הנושאים שעלו בשיחה]
        
        🧠 **אמונות מגבילות ודפוסי חשיבה (Limiting Beliefs)**
        [אילו אמונות מעכבות זיהית אצל המטופל?]
        
        🛠️ **טכניקות והתערבויות שבוצעו (Interventions Used)**
        [אילו כלים מתחום ה-NLP או האימון הופעלו בשיחה?]
        
        🎯 **משימות ושיעורי בית (Action Items)**
        [מה המטופל לקח על עצמו לעשות עד הפגישה הבאה?]
        
        Transcription of the session:
        {transcription}
        """
        
        ai_response = asyncio.run(ai_engine.analyze_interaction(
            system_prompt=prompt,
            text_input="אנא נתח את הפגישה והחזר סיכום קליני מדויק לפי התבנית.",
            sender_name="System"
        ))
        
        session_record.transcript = transcription
        session_record.summary = ai_response.get("reply_text", "לא הצלחנו לייצר סיכום עקב שגיאת AI.")
        session_record.status = SessionStatus.COMPLETED
        db.commit()
        
        logger.info(f"✅ NLP Session {session_id} processed successfully.")
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return "Success"
            
    except Exception as e:
        db.rollback()
        logger.error(f"🔥 Meeting session processing failed: {e}")
        if 'session_record' in locals() and session_record:
            session_record.status = SessionStatus.FAILED
            db.commit()
        return f"Failed: {str(e)}"
    finally:
        db.close()