# src/services/ai_engine.py
import json
import logging
import os
import google.generativeai as genai
from typing import Dict, Any, Union
from src.config import settings
from src.prompts import get_business_config

# Safe Policy Import
try:
    from src.config.policy import get_policy_text
except ImportError:
    def get_policy_text(): return "Policy unavailable."

logger = logging.getLogger("AI_Brain")

if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)

class AIEngine:
    def __init__(self):
        self.model_name = "gemini-2.0-flash"
        self.model = genai.GenerativeModel(
            self.model_name,
            generation_config={"response_mime_type": "application/json"}
        )

    def _clean_json_text(self, text: str) -> str:
        text = text.strip()
        if text.startswith("\`\`\`json"): text = text[7:]
        elif text.startswith("\`\`\`"): text = text[3:]
        if text.endswith("\`\`\`"): text = text[:-3]
        return text.strip()

    async def analyze_interaction(self, text_input: str = None, audio_path: str = None, user_context: Dict = None) -> Dict[str, Any]:
        print(f"DEBUG: Using Model {self.model_name}", flush=True)
        
        if not user_context: user_context = {}
        
        # Load Persona
        business_type = user_context.get("business_type", "Yoga Instructor")
        business_name = user_context.get("business_name", "Lea's Studio")
        persona = get_business_config(business_type, business_name)

        system_prompt = f"""
        {persona['system_role']}
        
        Policy: {get_policy_text()}
        User Name: {user_context.get('name', 'Guest')}
        
        Analyze the input and return a single valid JSON object (NOT a list):
        {{
            "intent": "cancel" | "reschedule" | "info" | "greeting",
            "reply_text": "Hebrew reply based on the persona rules"
        }}
        """

        try:
            content = [system_prompt]
            
            if audio_path and os.path.exists(audio_path):
                print(f"DEBUG: Uploading Audio: {audio_path}", flush=True)
                
                # MIME Type Handling
                mime_type = "audio/ogg" 
                if audio_path.endswith(".wav"): mime_type = "audio/wav"
                elif audio_path.endswith(".mp3"): mime_type = "audio/mpeg"

                uploaded_file = genai.upload_file(audio_path, mime_type=mime_type)
                content.append(uploaded_file)
                content.append("Please listen to this audio note and respond in JSON.")
                
            elif text_input:
                content.append(f"User Message: {text_input}")
            
            print("DEBUG: Sending to Gemini...", flush=True)
            response = self.model.generate_content(content)
            
            clean_text = self._clean_json_text(response.text)
            print(f"DEBUG: Gemini Response: {clean_text}", flush=True)
            
            # Parse JSON
            data = json.loads(clean_text)
            
            # FIX: Handle List vs Dict response
            if isinstance(data, list):
                if len(data) > 0:
                    data = data[0]
                else:
                    data = {"reply_text": "סליחה, לא הבנתי."}
            
            return data

        except Exception as e:
            print(f"CRITICAL_ERROR: {str(e)}", flush=True)
            logger.error(f"🔥 AI Crash: {e}")
            return {"reply_text": "סליחה, אני לא זמינה כרגע. אעביר למאמנת."}

ai_engine = AIEngine()