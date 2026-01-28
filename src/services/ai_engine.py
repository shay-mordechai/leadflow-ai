# src/services/ai_engine.py
import json
import logging
import os
import httpx
import google.generativeai as genai
from typing import Dict, Any
from src.config import settings

logger = logging.getLogger("AI_Brain")

# Configure Gemini
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)

class AIEngine:
    def __init__(self):
        # Gemini 1.5 Flash is perfect: Fast, Cheap, and handles Audio natively!
        self.model_name = "gemini-1.5-flash"
        self.model = genai.GenerativeModel(
            self.model_name,
            generation_config={"response_mime_type": "application/json"}
        )

    async def analyze_interaction(self, text_input: str = None, audio_path: str = None, user_context: Dict = None) -> Dict[str, Any]:
        """
        Analyzes Text OR Audio input to determine the Yoga Student's intent.
        Implements the 'Conditional Cancellation' logic.
        """
        
        # 1. The Yoga Instructor Persona & Policy
        system_prompt = f"""
        You are 'Lea', the AI manager for a Yoga Studio.
        
        Current User: {user_context.get('name', 'Student')}
        Upcoming Class: {user_context.get('upcoming_class', 'Unknown')}
        Time until class: {user_context.get('hours_until_class', 48)} hours.

        **YOUR STRICT POLICY:**
        1. **Cancellation > 24 Hours:** Allow immediately. Reply: "Canceled, no charge."
        2. **Cancellation < 24 Hours:** Conditional! Reply: "It's late notice. I'll move you to the waiting list. If someone takes the spot, you won't be charged. Otherwise, the fee stands."
        3. **Reschedule:** Treat as cancellation + new booking request.
        
        **TASK:**
        Analyze the input and output JSON:
        {{
            "intent": "cancel_booking" | "reschedule" | "general_query" | "confirm_arrival",
            "urgency_level": "high" (if < 24h) | "low",
            "action_required": "mark_pending_resale" | "cancel_immediate" | "none",
            "reply_text": "A friendly WhatsApp reply in Hebrew (Israeli style) based on the policy above."
        }}
        """

        try:
            content_parts = [system_prompt]
            
            # 2. Add Audio or Text to the prompt
            if audio_path and os.path.exists(audio_path):
                logger.info(f"🎤 Uploading audio to Gemini: {audio_path}")
                # Upload file to Gemini (Temporary storage)
                audio_file = genai.upload_file(audio_path)
                content_parts.append(audio_file)
                content_parts.append("Analyze this voice note.")
            elif text_input:
                content_parts.append(f"Student Message: {text_input}")
            else:
                return {"error": "No input provided"}

            # 3. Generate Analysis
            logger.info("🤖 Sending to Gemini...")
            response = self.model.generate_content(content_parts)
            
            # Parse JSON
            result = json.loads(response.text)
            logger.info(f"💡 AI Decision: {result['intent']}")
            return result

        except Exception as e:
            logger.error(f"AI Engine Failed: {e}")
            return {
                "intent": "error",
                "reply_text": "סליחה, לא הצלחתי להבין. אני מעבירה את ההודעה למאמנת."
            }

ai_engine = AIEngine()