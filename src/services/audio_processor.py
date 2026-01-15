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
from src.database.models import User, Lead, LeadSource, LeadStatus

logger = logging.getLogger("AudioProcessor")

class AudioProcessor:
    def __init__(self, user_id: str, payload: dict):
        self.user_id = user_id
        self.payload = payload
        self.temp_dir = "/tmp/audio_processing"
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Initialize the new Client
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    async def process_pipeline(self):
        """
        Orchestrates the full flow using the NEW Google GenAI SDK.
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

            # 3. Process with Gemini (Using New SDK)
            analysis = await self._analyze_audio_with_gemini(file_path, mime_type, sender_name)

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
            # Print full traceback to see exactly what failed
            logger.error(f"Error in Gemini pipeline: {e}")
            traceback.print_exc() 
        finally:
            db.close()
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

    async def _download_file(self, url: str, target_path: str):
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http_client:
            resp = await http_client.get(url)
            resp.raise_for_status()
            with open(target_path, "wb") as f:
                f.write(resp.content)

    async def _analyze_audio_with_gemini(self, file_path: str, mime_type: str, sender_name: str) -> dict:
        """
        Attempts to use models in priority order (2.5 -> 1.5).
        Returns the first successful result.
        """
        if not settings.GOOGLE_API_KEY:
            logger.warning("No Google API Key found.")
            return None

        # רשימת המודלים לפי סדר עדיפות
        # המערכת תנסה את הראשון, אם ייכשל תעבור לשני
        PRIORITY_MODELS = [
            "gemini-2.5-flash",      # The future model you requested
            "gemini-2.0-flash-exp",  # Current experimental fast model
            "gemini-1.5-flash"       # The stable workhorse (Backup)
        ]

        uploaded_file = None

        try:
            # 1. Upload File (We do this once)
            with open(file_path, "rb") as f:
                # Note: For very small files we could send bytes, but upload is safer
                uploaded_file = self.client.files.upload(
                    file=file_path,
                    config={'mime_type': mime_type}
                )
            
            # 2. Define Prompt
            prompt = f"""
            You are a CRM expert. Listen to this audio message from a lead named '{sender_name}'. 
            Return ONLY a raw JSON object with these fields:
            - "customer_name": (Extract name if mentioned, otherwise use '{sender_name}')
            - "summary": (A short summary in Hebrew)
            - "transcript": (Full transcription in Hebrew)
            - "sentiment": (One of: Positive, Neutral, Negative)
            - "suggested_reply": (A polite, professional WhatsApp reply in Hebrew)
            """

            # 3. Iterate through models until one works
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
                    
                    # If we got here, it worked!
                    if response.text:
                        logger.info(f"✅ Success with model: {model_name}")
                        return json.loads(response.text)
                    
                except Exception as e:
                    # Log warning but don't crash - just try the next model
                    logger.warning(f"⚠️ Model {model_name} failed or not found. Error: {e}")
                    last_error = e
                    continue # Try next model in list

            # If loop finished and nothing worked
            logger.error("❌ All models failed to process the audio.")
            if last_error:
                logger.error(f"Last error: {last_error}")
            return None

        except Exception as e:
            logger.error(f"Critical Error in Gemini setup: {e}")
            traceback.print_exc()
            return None

    def _save_results_to_db(self, db: Session, phone: str, analysis: dict):
        user = db.query(User).filter(User.id == self.user_id).first()
        if not user:
            return

        lead = Lead(
            user_id=user.id,
            name=analysis.get("customer_name") or "Unknown",
            phone_number=phone,
            source=LeadSource.WHATSAPP,
            status=LeadStatus.NEW
        )
        db.add(lead)
        db.commit()