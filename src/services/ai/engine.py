# src/services/ai/engine.py
import json
import logging
import os
import google.generativeai as genai
from typing import Dict, Any, Optional, List
from src.config import settings
from src.services.ai.personas import get_persona_config

logger = logging.getLogger("AI_Engine")

# --- CENTRALIZED CONFIGURATION ---
# This is the only place where genai.configure happens.
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
else:
    logger.warning("GOOGLE_API_KEY is missing. AI features will fail.")

class AIEngine:
    """
    Central Logic for AI Interactions.
    Handles Model Initialization, File Uploads, and Response Parsing.
    """
    
    def __init__(self):
        # We use 'gemini-2.0-flash' for speed and cost efficiency.
        self.model_name = "gemini-2.0-flash"
        
        # Model optimized for JSON output
        self.json_model = genai.GenerativeModel(
            self.model_name,
            generation_config={"response_mime_type": "application/json"}
        )
        # Model optimized for free text (summaries)
        self.text_model = genai.GenerativeModel(self.model_name)

    def _clean_json_text(self, text: str) -> str:
        """Helper to strip Markdown formatting from JSON responses."""
        text = text.strip()
        if text.startswith("```json"): text = text[7:]
        elif text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        return text.strip()

    def generate_raw_analysis(self, prompt: str, media_path: str = None, mime_type: str = "audio/ogg") -> Dict[str, Any]:
        """
        Generic method to send a prompt (and optional media) to Gemini 
        and return a parsed dictionary.
        """
        try:
            content = [prompt]
            
            # Handle Media Upload
            if media_path and os.path.exists(media_path):
                logger.info(f"Uploading media file: {media_path}")
                uploaded_file = genai.upload_file(path=media_path, mime_type=mime_type)
                content.append(uploaded_file)
            
            # Generate Response
            response = self.json_model.generate_content(content)
            
            # Parse Response
            if not response.text:
                return {}

            clean_text = self._clean_json_text(response.text)
            return json.loads(clean_text)

        except Exception as e:
            logger.error(f"AI Generation Error: {e}")
            return {"error": str(e)}

    def generate_meeting_summary(self, transcription_text: str) -> str:
        """
        Summarizes text into a report format (Plain Text).
        """
        prompt = f"""
        You are an expert executive assistant. 
        Analyze the following meeting transcription (Hebrew/English).
        
        Output a structured summary containing:
        1. Key Topics Discussed
        2. Action Items (To-Do List)
        3. Next Steps
        
        Keep it professional, concise, and formatted as a clear report.
        
        Transcription:
        "{transcription_text}"
        """
        try:
            response = self.text_model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "Failed to generate summary."

    async def analyze_interaction(self, text_input: str = None, audio_path: str = None, user_context: Dict = None) -> Dict[str, Any]:
        """
        High-level flow for Chatbot Personas.
        Constructs the persona prompt and calls the generic generator.
        """
        if not user_context: user_context = {}
        
        # 1. Get Persona Config
        business_type = user_context.get("business_type", "General Business")
        custom_data = {
            "business_name": user_context.get("business_name", "My Business"),
            "location": user_context.get("location", "Israel"),
        }
        persona_config = get_persona_config(business_type, custom_data)
        
        # 2. Construct System Prompt
        system_prompt = f"""
        {persona_config['role_prompt']}
        User Name: {user_context.get('name', 'Guest')}
        User Message: {text_input if text_input else 'Audio Message'}
        
        Task: Analyze the input and return a valid JSON object with:
        {{
            "intent": "cancel" | "reschedule" | "info" | "greeting" | "purchase",
            "reply_text": "Hebrew reply based on the persona rules",
            "suggested_actions": []
        }}
        """

        # 3. Execute via generic method
        return self.generate_raw_analysis(system_prompt, audio_path)

# Singleton Instance
ai_engine = AIEngine()