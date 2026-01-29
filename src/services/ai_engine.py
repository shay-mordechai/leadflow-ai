# src/services/ai_engine.py
import json
import logging
import os
import google.generativeai as genai
from typing import Dict, Any
from src.config import settings

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
        # UPDATED: Using Gemini 2.0 Flash based on your scan!
        self.model_name = "gemini-2.0-flash"
        self.model = genai.GenerativeModel(
            self.model_name,
            generation_config={"response_mime_type": "application/json"}
        )

    def _clean_json_text(self, text: str) -> str:
        text = text.strip()
        if text.startswith("\`\`\`json"):
            text = text[7:]
        elif text.startswith("\`\`\`"):
            text = text[3:]
        if text.endswith("\`\`\`"):
            text = text[:-3]
        return text.strip()

    async def analyze_interaction(self, text_input: str = None, audio_path: str = None, user_context: Dict = None) -> Dict[str, Any]:
        print(f"DEBUG: Using Model {self.model_name}", flush=True)
        
        if not user_context: user_context = {}
        
        system_prompt = f"""
        You are 'Lea', a Yoga Studio AI.
        Policy: {get_policy_text()}
        User: {user_context.get('name', 'Guest')}
        
        Analyze and return JSON:
        {{
            "intent": "cancel" | "reschedule" | "info",
            "reply_text": "Hebrew reply"
        }}
        """

        try:
            content = [system_prompt]
            if audio_path and os.path.exists(audio_path):
                print(f"DEBUG: Uploading Audio...", flush=True)
                content.append(genai.upload_file(audio_path))
            elif text_input:
                content.append(f"Message: {text_input}")
            
            print("DEBUG: Sending to Gemini...", flush=True)
            response = self.model.generate_content(content)
            
            clean_text = self._clean_json_text(response.text)
            print(f"DEBUG: Gemini Response: {clean_text}", flush=True)
            
            return json.loads(clean_text)

        except Exception as e:
            print(f"CRITICAL_ERROR: {str(e)}", flush=True)
            logger.error(f"🔥 AI Crash: {e}")
            return {"reply_text": "סליחה, אני לא זמינה כרגע. אעביר למאמנת."}

ai_engine = AIEngine()