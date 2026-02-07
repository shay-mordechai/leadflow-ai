# src/services/audio_processor.py
import os
import uuid
import json
import logging
import traceback
import google.generativeai as genai
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool

from src.config import settings
from src.database.session import SessionLocal
from src.database.models import Lead, LeadSource, LeadStatus, BusinessProfile
from src.services.whatsapp_adapter import whatsapp_adapter

logger = logging.getLogger(\"AudioProcessor\")

# Configure GenAI globally
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)

class AudioProcessor:
    def __init__(self, user_id: str, payload: dict):
        self.user_id = user_id
        self.payload = payload
        
        # Use GenerativeModel from google.generativeai
        self.model = genai.GenerativeModel(
            \"gemini-1.5-flash\",
            generation_config={\"response_mime_type\": \"application/json\"}
        )

    async def process_pipeline(self):
        file_path = None
        db = SessionLocal()
        
        try:
            message_data = self.payload.get(\"messageData\", {})
            file_data = message_data.get(\"fileMessageData\", {})
            download_url = file_data.get(\"downloadUrl\")
            mime_type = file_data.get(\"mimeType\", \"audio/ogg\")
            
            sender_data = self.payload.get(\"senderData\", {})
            sender_phone = sender_data.get(\"sender\", \"\").replace(\"@c.us\", \"\")
            sender_name = sender_data.get(\"senderName\", \"Unknown\")

            if not download_url:
                logger.error(\"No download URL found\")
                return

            # Download
            file_path = whatsapp_adapter.download_media(download_url)
            if not file_path:
                return

            # Analyze
            analysis = await self._analyze_audio(db, file_path, mime_type, sender_name)

            # Save
            if analysis:
                await run_in_threadpool(
                    self._save_results, db, sender_phone, analysis
                )
                logger.info(f\"✅ Audio processed for user {self.user_id}\")

        except Exception as e:
            logger.error(f\"Pipeline Error: {e}\")
            traceback.print_exc() 
        finally:
            db.close()
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

    async def _analyze_audio(self, db: Session, file_path: str, mime_type: str, sender_name: str) -> dict:
        if not settings.GOOGLE_API_KEY:
            return None

        profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == self.user_id).first()
        
        business_name = profile.business_name if profile else \"the business\"
        tone = profile.ai_tone if profile else \"Professional\"
        products = profile.products_services if profile else \"General services\"
        
        try:
            logger.info(f\"Uploading {file_path} to Gemini...\")
            audio_file = genai.upload_file(path=file_path, mime_type=mime_type)
            
            prompt = f\"\"\"
            You are a sales assistant for '{business_name}'.
            Context: {products}. Tone: {tone}.
            Task: Listen to message from '{sender_name}'.
            Return JSON:
            - customer_name
            - summary (Hebrew)
            - transcript (Hebrew)
            - sentiment
            - suggested_reply (Hebrew WhatsApp message)
            \"\"\"
            
            response = self.model.generate_content([prompt, audio_file])
            
            if response.text:
                text = response.text.strip()
                if text.startswith(\"\`\`\`json\"): text = text[7:]
                if text.endswith(\"\`\`\`\"): text = text[:-3]
                return json.loads(text.strip())
            
            return None

        except Exception as e:
            logger.error(f\"Gemini Error: {e}\")
            return None

    def _save_results(self, db: Session, phone: str, analysis: dict):
        # Update or Create Lead Logic (Simplified)
        lead = db.query(Lead).filter(Lead.user_id == self.user_id, Lead.phone_number == phone).first()
        
        if lead:
            lead.transcription_summary = analysis.get(\"summary\")
            lead.status = LeadStatus.IN_PROGRESS 
        else:
            lead = Lead(
                user_id=self.user_id,
                name=analysis.get(\"customer_name\") or \"Unknown\",
                phone_number=phone,
                source=LeadSource.WHATSAPP,
                status=LeadStatus.NEW,
                transcription_summary=analysis.get(\"summary\")
            )
            db.add(lead)
        db.commit()