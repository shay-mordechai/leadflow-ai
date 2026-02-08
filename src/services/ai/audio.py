# src/services/ai/audio.py
import os
import logging
import traceback
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool

from src.database.session import SessionLocal
from src.database.models import Lead, LeadSource, LeadStatus, BusinessProfile
from src.services.whatsapp_adapter import whatsapp_adapter

# IMPORT THE CENTRAL ENGINE
from src.services.ai.engine import ai_engine

logger = logging.getLogger("AudioProcessor")

class AudioProcessor:
    """
    Handles the end-to-end processing of incoming audio messages:
    Download -> Analyze (via AIEngine) -> Update CRM (Database).
    """
    def __init__(self, user_id: str, payload: dict):
        self.user_id = user_id
        self.payload = payload

    async def process_pipeline(self):
        """
        Main execution flow.
        """
        file_path = None
        db = SessionLocal()
        
        try:
            # 1. Extract Metadata from Payload
            message_data = self.payload.get("messageData", {})
            file_data = message_data.get("fileMessageData", {})
            download_url = file_data.get("downloadUrl")
            mime_type = file_data.get("mimeType", "audio/ogg")
            
            sender_data = self.payload.get("senderData", {})
            sender_phone = sender_data.get("sender", "").replace("@c.us", "")
            sender_name = sender_data.get("senderName", "Unknown")

            if not download_url:
                logger.error("No download URL found in payload.")
                return

            # 2. Download File
            file_path = whatsapp_adapter.download_media(download_url)
            if not file_path:
                return

            # 3. Analyze (Delegated to AIEngine)
            # We pass the DB session to fetch specific business context
            analysis = await self._prepare_and_analyze(db, file_path, mime_type, sender_name)

            # 4. Save Results
            if analysis:
                await run_in_threadpool(
                    self._save_results, db, sender_phone, analysis
                )
                logger.info(f"✅ Audio processed successfully for user {self.user_id}")
            else:
                logger.warning("AI Analysis returned empty result.")

        except Exception as e:
            logger.error(f"Pipeline Error: {e}")
            traceback.print_exc() 
        finally:
            db.close()
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

    async def _prepare_and_analyze(self, db: Session, file_path: str, mime_type: str, sender_name: str) -> dict:
        """
        Fetches business context, constructs the prompt, and calls AIEngine.
        """
        # Fetch Context
        profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == self.user_id).first()
        
        business_name = profile.business_name if profile else "the business"
        tone = profile.ai_tone if profile else "Professional"
        products = profile.products_services if profile else "General services"
        custom_instructions = profile.custom_instructions if profile else ""
        
        # Construct Prompt
        prompt = f"""
        You are a highly capable sales assistant for '{business_name}'.
        
        **Business Context:**
        - Products/Services: {products}
        - Tone: {tone}
        - Custom Rules: {custom_instructions}
        
        **Task:** Listen to the audio message from a customer named '{sender_name}'.
        
        **Output Requirement:**
        Return a single valid JSON object with the following keys:
        - customer_name: Extract if mentioned, else use '{sender_name}'.
        - summary: A concise summary of the request (in Hebrew).
        - transcript: A near-verbatim transcription (in Hebrew).
        - sentiment: "Positive", "Neutral", or "Negative".
        - suggested_reply: A helpful, tone-appropriate WhatsApp reply (in Hebrew).
        - intent: "Sales", "Support", "Scheduling", or "Other".
        """
        
        # Call the Central Engine
        # This uses the unified logic in engine.py (Model init, JSON cleaning, etc.)
        return ai_engine.generate_raw_analysis(prompt, file_path, mime_type)

    def _save_results(self, db: Session, phone: str, analysis: dict):
        """
        Updates or creates a Lead record in the database.
        """
        lead = db.query(Lead).filter(Lead.user_id == self.user_id, Lead.phone_number == phone).first()
        
        customer_name = analysis.get("customer_name") or "Unknown"
        summary = analysis.get("summary")
        transcript = analysis.get("transcript")
        reply = analysis.get("suggested_reply")

        if lead:
            lead.transcription_summary = summary
            lead.original_transcript = transcript
            lead.suggested_reply = reply
            lead.status = LeadStatus.IN_PROGRESS
            # Update name if previously unknown
            if lead.name in ["Unknown", "Guest"] and customer_name != "Unknown":
                lead.name = customer_name
        else:
            lead = Lead(
                user_id=self.user_id,
                name=customer_name,
                phone_number=phone,
                source=LeadSource.WHATSAPP,
                status=LeadStatus.NEW,
                transcription_summary=summary,
                original_transcript=transcript,
                suggested_reply=reply
            )
            db.add(lead)
        
        db.commit()