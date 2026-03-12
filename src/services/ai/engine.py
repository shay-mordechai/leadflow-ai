# src/services/ai/engine.py
import json
import logging
import os
import hashlib
import redis.asyncio as aioredis
import google.generativeai as genai
from typing import Dict, Any, Optional, List
from fastapi.concurrency import run_in_threadpool

from src.config import settings

logger = logging.getLogger("AI_Engine")

# --- CENTRALIZED CONFIGURATION ---
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
else:
    logger.warning("GOOGLE_API_KEY is missing. AI features will fail.")

# --- TIER 3 OPTIMIZATION: Initialize Redis Client ---
try:
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception as e:
    logger.warning(f"Failed to initialize Redis client: {e}")
    redis_client = None


# --- DEFINE AI TOOLS (THE "AGENTS") ---
def check_calendar_availability(date_str: str) -> str:
    """Checks the business owner's calendar for available slots on a given date (YYYY-MM-DD)."""
    logger.info(f"🤖 AI AGENT TOOL CALLED: check_calendar_availability for {date_str}")
    return json.dumps({
        "available_slots": ["09:00", "11:30", "15:00", "17:00"],
        "message": "These are the available slots. Ask the user which one they prefer."
    })

def book_appointment(date_str: str, time_str: str, lead_name: str) -> str:
    """Books an appointment for the lead on the specified date and time."""
    logger.info(f"🤖 AI AGENT TOOL CALLED: book_appointment for {lead_name} at {date_str} {time_str}")
    return json.dumps({
        "status": "success",
        "message": "Appointment booked successfully. Confirm it politely with the user."
    })

def qualify_lead(budget: int, timeframe: str) -> str:
    """Saves the lead's budget and timeframe to the database to qualify them."""
    logger.info(f"🤖 AI AGENT TOOL CALLED: qualify_lead - Budget: {budget}, Timeframe: {timeframe}")
    return json.dumps({
        "status": "qualified",
        "message": "Lead details saved. Proceed with the conversation naturally."
    })

# List of tools to pass to the Gemini Agent
AI_TOOLS = [check_calendar_availability, book_appointment, qualify_lead]


class AIEngine:
    """
    Central Logic for AI Interactions.
    Handles Model Initialization, File Uploads, Response Parsing, and Agentic Function Calling.
    Includes Redis Semantic Caching to reduce API costs.
    """
    def __init__(self):
        self.model_name = "gemini-2.0-flash"
        self.model = genai.GenerativeModel(self.model_name)

    def _clean_json_text(self, text: str) -> str:
        """Helper to strip Markdown formatting from JSON responses."""
        text = text.strip()
        if text.startswith("```json"): text = text[7:]
        elif text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        return text.strip()

    def generate_raw_analysis(self, prompt: str, media_path: str = None, mime_type: str = "audio/ogg") -> Dict[str, Any]:
        try:
            content = [prompt]
            if media_path and os.path.exists(media_path):
                logger.info(f"Uploading media file: {media_path}")
                uploaded_file = genai.upload_file(path=media_path, mime_type=mime_type)
                content.append(uploaded_file)
                
            try:
                response = self.model.generate_content(
                    content,
                    generation_config={"response_mime_type": "application/json"}
                )
            except Exception as cfg_err:
                logger.warning(f"JSON Mode config failed, retrying without explicit mime_type: {cfg_err}")
                response = self.model.generate_content(content)
                
            if not response.text:
                return {}

            clean_text = self._clean_json_text(response.text)
            return json.loads(clean_text)

        except Exception as e:
            logger.error(f"AI Generation Error: {e}")
            return {"error": str(e), "reply_text": "I'm sorry, I'm having a technical moment. Please try again."}

    async def analyze_interaction(
        self,
        system_prompt: str,
        text_input: str = None,
        audio_path: str = None,
        sender_name: str = "Guest",
        expected_schema: str = None,
        chat_history: List[Dict] = None
    ) -> Dict[str, Any]:
        
        # SCENARIO A: Audio/Media or Explicit Schema provided -> Legacy JSON Mode
        if audio_path or expected_schema:
            if audio_path:
                logger.info("Media payload detected. Using standard JSON analysis mode.")
            if not expected_schema:
                expected_schema = """{
                    "intent": "general_inquiry" | "booking" | "support" | "greeting" | "other",
                    "reply_text": "Your response to the user in the correct tone and language.",
                    "needs_human_escalation": boolean
                }"""

            final_prompt = f"""
            {system_prompt}
            Current User Talking to you: {sender_name}
            User Message: {text_input if text_input else 'Audio Message (Transcribed separately)'}
            Task: You must respond in the character defined above.
            Return ONLY a valid JSON object strictly matching this format:
            {expected_schema}
            """

            return await run_in_threadpool(
                self.generate_raw_analysis,
                prompt=final_prompt,
                media_path=audio_path
            )

        # SCENARIO B: Text-Based Chat -> Agentic / Function Calling Mode
        else:
            logger.info(f"Agentic flow triggered for lead: {sender_name}")
            try:
                text_lower = text_input.lower() if text_input else ""
                trigger_words = [
                    "human", "representative", "manager", "urgent",
                    "נציג", "אנושי", "מנהל", "שירות לקוחות", "מענה אנושי", "תענה לי בן אדם"
                ]
                if any(word in text_lower for word in trigger_words):
                    logger.warning(f"🚨 Rule-Based Handoff Triggered for: {sender_name}")
                    return {
                        "intent": "escalation",
                        "reply_text": "אני מבין. העברתי את הפנייה שלך, ונציג אנושי יחזור אליך בהקדם.",
                        "needs_human_escalation": True
                    }

                # -------------------------------------------------------------
                # TIER 3 OPTIMIZATION: AI Response Caching (Redis)
                # -------------------------------------------------------------
                cache_key = None
                if redis_client and text_input:
                    normalized_input = text_input.strip().lower()
                    history_str = json.dumps(chat_history) if chat_history else ""
                    # Hash the combination of persona, history, and exact input
                    hash_input = f"{system_prompt}|{normalized_input}|{history_str}"
                    cache_key = f"ai_cache:{hashlib.md5(hash_input.encode()).hexdigest()}"
                    
                    try:
                        cached_response = await redis_client.get(cache_key)
                        if cached_response:
                            logger.info(f"⚡ CACHE HIT! Saved Gemini API cost for query: {normalized_input[:30]}...")
                            return json.loads(cached_response)
                    except Exception as cache_err:
                        logger.warning(f"Redis cache read error: {cache_err}")

                # Dynamically inject the System Instructions to the Model
                full_system_instruction = f"""
                [SYSTEM PERSONA - ADHERE STRICTLY]:
                {system_prompt}
                [INSTRUCTIONS]:
                1. If the user asks about availability, autonomously use the 'check_calendar_availability' tool.
                2. If the user wants to book, autonomously use the 'book_appointment' tool.
                3. If you need to qualify a budget/timeframe, autonomously use the 'qualify_lead' tool.
                4. Always respond naturally, in character, and in the user's language.
                5. If they are angry, include the EXACT word "[HANDOFF]" in your response so a human can take over.
                """

                chat_model = genai.GenerativeModel(
                    model_name=self.model_name,
                    tools=AI_TOOLS,
                    system_instruction=full_system_instruction
                )

                formatted_history = []
                if chat_history:
                    for msg in chat_history:
                        role = "user" if msg.get("sender_type") == "user" else "model"
                        formatted_history.append({"role": role, "parts": [msg.get("content", "")]})

                agent_session = chat_model.start_chat(
                    history=formatted_history,
                    enable_automatic_function_calling=True
                )

                user_message = f"[{sender_name}]: {text_input}"

                logger.info("Sending message to AI Agent and awaiting potential tool execution...")
                response = await run_in_threadpool(agent_session.send_message, user_message)
                final_text = response.text if hasattr(response, 'text') else ""
                
                # Robust Handoff Detection
                upper_text = final_text.upper()
                needs_human = "[HANDOFF]" in upper_text or "HANDOFF" in upper_text

                result = {
                    "intent": "agent_handled",
                    "reply_text": final_text.replace("[HANDOFF]", "").replace("[handoff]", "").strip(),
                    "needs_human_escalation": needs_human
                }

                # Save successful responses to Cache (TTL: 24 hours)
                if cache_key and redis_client and not needs_human:
                    try:
                        await redis_client.setex(cache_key, 86400, json.dumps(result))
                    except Exception as cache_err:
                        logger.warning(f"Redis cache write error: {cache_err}")

                return result

            except Exception as e:
                logger.error(f"Agent Execution Error: {e}")
                return {
                    "error": str(e),
                    "reply_text": "אני קצת עמוסה כרגע, אפשר לנסות שוב בעוד רגע?",
                    "needs_human_escalation": True
                }

# Singleton Instance
ai_engine = AIEngine()