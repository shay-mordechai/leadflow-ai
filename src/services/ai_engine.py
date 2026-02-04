# src/services/ai_engine.py
import json
import logging
import os
import google.generativeai as genai
from typing import Dict, Any
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
        if text.startswith("```json"): text = text[7:]
        elif text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        return text.strip()

    def generate_meeting_summary(self, transcription_text: str) -> str:
        """
        Summarizes a meeting transcription into action items and key points.
        Returns a plain text summary (not JSON) for the PDF.
        """
        # We use a standard model for text generation (not JSON mode)
        text_model = genai.GenerativeModel("gemini-2.0-flash")
        
        prompt = f"""
        You are an expert executive assistant. 
        Analyze the following meeting transcription (Hebrew/English).
        
        Output a structured summary containing:
        1. Key Topics Discussed
        2. Action Items (To-Do List)
        3. Next Steps
        
        Keep it professional, concise, and formatted for a report.
        
        Transcription:
        "{transcription_text}"
        """
        
        try:
            response = text_model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "Failed to generate summary."

    async def analyze_interaction(self, text_input: str = None, audio_path: str = None, user_context: Dict = None) -> Dict[str, Any]:
        """
        Analyzes standard chat interactions (Text or Audio via Gemini Cloud).
        """
        # ... (Existing code remains exactly the same as provided in your prompt) ...
        # Copied logic for brevity:
        if not user_context: user_context = {}
        
        business_type = user_context.get("business_type", "Yoga Instructor")
        business_name = user_context.get("business_name", "Lea's Studio")
        persona = get_business_config(business_type, business_name)

        system_prompt = f"""
        {persona['system_role']}
        Policy: {get_policy_text()}
        User Name: {user_context.get('name', 'Guest')}
        
        Analyze the input and return a single valid JSON object:
        {{
            "intent": "cancel" | "reschedule" | "info" | "greeting",
            "reply_text": "Hebrew reply based on the persona rules"
        }}
        """

        try:
            content = [system_prompt]
            if audio_path and os.path.exists(audio_path):
                # ... existing audio logic ...
                uploaded_file = genai.upload_file(audio_path, mime_type="audio/ogg")
                content.append(uploaded_file)
                content.append("Listen and respond in JSON.")
            elif text_input:
                content.append(f"User Message: {text_input}")
            
            response = self.model.generate_content(content)
            clean_text = self._clean_json_text(response.text)
            data = json.loads(clean_text)
            
            if isinstance(data, list):
                data = data[0] if len(data) > 0 else {"reply_text": "Error parsing."}
            return data

        except Exception as e:
            logger.error(f"🔥 AI Crash: {e}")
            return {"reply_text": "System Error."}

ai_engine = AIEngine()