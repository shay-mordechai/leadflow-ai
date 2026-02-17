# src/services/ai/engine.py
import json
import logging
import os
import google.generativeai as genai
from typing import Dict, Any, Optional
from fastapi.concurrency import run_in_threadpool

from src.config import settings

logger = logging.getLogger("AI_Engine")

# --- CENTRALIZED CONFIGURATION ---
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
        Generic synchronous method to send a prompt to Gemini.
        Note: Use run_in_threadpool when calling this from async code.
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
            return {"error": str(e), "reply_text": "Error processing AI request."}

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
        Transcription: "{transcription_text}"
        """
        try:
            response = self.text_model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "Failed to generate summary."

    async def analyze_interaction(self, system_prompt: str, text_input: str = None, audio_path: str = None, sender_name: str = "Guest") -> Dict[str, Any]:
        """
        High-level flow for Chatbot Personas.
        Takes the dynamic system_prompt (from the DB) and calls the generic generator asynchronously.
        """
        # Construct the final prompt injected with the user's specific instructions
        final_prompt = f"""
        {system_prompt}
        
        Current User Talking to you: {sender_name}
        User Message: {text_input if text_input else 'Audio Message (Transcribed separately)'}
        
        Task: You must respond in the character defined above. 
        Return a valid JSON object strictly matching this format:
        {{
            "intent": "general_inquiry" | "booking" | "support" | "greeting" | "other",
            "reply_text": "Your response to the user in the correct tone and language.",
            "needs_human_escalation": boolean
        }}
        """

        # Execute via generic method (Non-blocking)
        return await run_in_threadpool(
            self.generate_raw_analysis,
            prompt=final_prompt,
            media_path=audio_path
        )

# Singleton Instance
ai_engine = AIEngine()