# src/services/audio_processor.py
import os
import uuid
import json
import httpx
import logging
import traceback
from google import genai
from google.genai import types
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool

# Project Imports
from src.config import settings
from src.database.session import SessionLocal
from src.database.models import User, Lead, LeadSource, LeadStatus, BusinessProfile

logger = logging.getLogger("AudioProcessor")

class AudioProcessor:
    def __init__(self, user_id: str, payload: dict):
        self.user_id = user_id
        self.payload = payload
        self.temp_dir = "/tmp/audio_processing"
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Initialize Google GenAI Client
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    async def process_pipeline(self):
        """
        Orchestrates the full flow: Download -> Transcribe/Analyze (Gemini) -> Save to DB.
        """
        file_path = None
        db = SessionLocal()
        
        try:
            # 1. Extract Metadata
            message_data = self.payload.get("messageData", {})
            file_data = message_data.get("fileMessageData", {})
            
            download_url = file_data.get("downloadUrl")
            mime_type = file_data.get("mimeType", "audio/ogg")
            
            sender_data = self.payload.get("senderData", {})
            sender_phone = sender_data.get("sender", "").replace("@c.us", "")
            sender_name = sender_data.get("senderName", "Unknown")

            if not download_url:
                logger.error("No download URL found in payload")
                return

            # 2. Download Audio File
            file_ext = ".ogg" if "ogg" in mime_type else ".mp3"
            filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(self.temp_dir, filename)
            
            await self._download_file(download_url, file_path)

            # 3. Process with Gemini (Passing DB session to fetch Business Profile)
            analysis = await self._analyze_audio_with_gemini(db, file_path, mime_type, sender_name)

            # 4. Save results to Database
            if analysis:
                await run_in_threadpool(
                    self._save_results_to_db, 
                    db, 
                    sender_phone, 
                    analysis
                )
                logger.info(f"Gemini successfully processed audio for user {self.user_id}")
            else:
                logger.error("Analysis returned empty result")

        except Exception as e:
            logger.error(f"Error in Gemini pipeline: {e}")
            traceback.print_exc() 
        finally:
            db.close()
            # Cleanup temp file
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

    async def _download_file(self, url: str, target_path: str):
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http_client:
            resp = await http_client.get(url)
            resp.raise_for_status()
            with open(target_path, "wb") as f:
                f.write(resp.content)

    async def _analyze_audio_with_gemini(self, db: Session, file_path: str, mime_type: str, sender_name: str) -> dict:
        """
        Analyzes audio using Gemini 2.5/1.5, injected with the User's Business Profile.
        """
        if not settings.GOOGLE_API_KEY:
            logger.warning("No Google API Key found.")
            return None

        # --- FETCH BUSINESS BRAIN ---
        # We fetch the specific settings for this user to customize the AI
        profile = db.query(BusinessProfile).filter(BusinessProfile.user_id == self.user_id).first()
        
        # Defaults if no profile exists
        business_name = profile.business_name if profile else "the business"
        tone = profile.ai_tone if profile else "Professional and polite"
        products = profile.products_services if profile else "General services"
        instructions = profile.custom_instructions if profile else "Be helpful."

        PRIORITY_MODELS = [
            "gemini-2.5-flash",      # Latest
            "gemini-2.0-flash-exp",  # Experimental
            "gemini-1.5-flash"       # Stable fallback
        ]

        uploaded_file = None

        try:
            # 1. Upload File
            uploaded_file = self.client.files.upload(
                file=file_path,
                config={'mime_type': mime_type}
            )
            
            # 2. Define Dynamic Prompt
            prompt = f"""
            You are a CRM expert and sales assistant for a business named '{business_name}'.
            
            **Business Context:**
            - Products/Services: {products}
            - Your Tone: {tone}
            - Special Instructions: {instructions}

            **Task:**
            Listen to this audio message from a lead named '{sender_name}'.
            
            Return ONLY a raw JSON object with these fields:
            - "customer_name": (Extract name if mentioned, otherwise use '{sender_name}')
            - "summary": (A short summary in Hebrew)
            - "transcript": (Full transcription in Hebrew)
            - "sentiment": (One of: Positive, Neutral, Negative)
            - "suggested_reply": (A WhatsApp reply in Hebrew, adopting the tone '{tone}' and following the special instructions)
            """

            # 3. Execute Model
            last_error = None
            
            for model_name in PRIORITY_MODELS:
                try:
                    logger.info(f"🤖 Attempting to analyze using model: {model_name}...")
                    
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=[uploaded_file, prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type='application/json'
                        )
                    )
                    
                    if response.text:
                        logger.info(f"✅ Success with model: {model_name}")
                        return json.loads(response.text)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Model {model_name} failed. Error: {e}")
                    last_error = e
                    continue

            logger.error("❌ All models failed to process the audio.")
            return None

        except Exception as e:
            logger.error(f"Critical Error in Gemini setup: {e}")
            return None

    def _save_results_to_db(self, db: Session, phone: str, analysis: dict):
        """
        Saves or Updates the lead in the database.
        """
        # 1. Check if lead already exists for this user (Prevent duplicates)
        existing_lead = db.query(Lead).filter(
            Lead.user_id == self.user_id,
            # Note: We query by the encrypted phone setter logic (needs exact match or raw query)
            # Since encryption is randomized, exact searching might be tricky without a hash column.
            # For this example, we assume we fetch all and check, OR use a hashed_phone index in production.
            # Here we act as if it's a new lead or simplistic update.
        ).all()
        
        # Simple Logic: Check decrypted phones in python (Not efficient for millions of rows, but fine for MVP)
        target_lead = None
        for l in existing_lead:
            if l.phone_number == phone:
                target_lead = l
                break
        
        if target_lead:
            logger.info(f"Updating existing lead: {phone}")
            target_lead.transcription_summary = analysis.get("summary")
            target_lead.original_transcript = analysis.get("transcript")
            target_lead.suggested_reply = analysis.get("suggested_reply")
            target_lead.status = LeadStatus.IN_PROGRESS # Move status
            # target_lead.coach_feedback = analysis.get("sentiment") # Optional mapping
        else:
            logger.info(f"Creating new lead: {phone}")
            new_lead = Lead(
                user_id=self.user_id,
                name=analysis.get("customer_name") or "Unknown",
                phone_number=phone,
                source=LeadSource.WHATSAPP,
                status=LeadStatus.NEW,
                transcription_summary=analysis.get("summary"),
                original_transcript=analysis.get("transcript"),
                suggested_reply=analysis.get("suggested_reply")
            )
            db.add(new_lead)
        
        db.commit()