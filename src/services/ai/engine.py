# src/services/ai/engine.py
import json
import logging
import os
import hashlib
import re
from datetime import date
import redis.asyncio as aioredis
from google import genai
from google.genai import types
from typing import Dict, Any, List
from fastapi.concurrency import run_in_threadpool

from src.config import settings
from src.services.ai.prompt_builder import PromptBuilder
from src.services.ai.output_sanitizer import sanitize_ai_output

logger = logging.getLogger("AI_Engine")
MAX_OUTPUT_TOKENS = 512
AI_REQUEST_TIMEOUT_SECONDS = 7.0
_TIME_FORMAT = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _validate_tool_date(date_str: str) -> None:
    """Accept only canonical ISO dates as calendar-tool arguments."""
    try:
        parsed_date = date.fromisoformat(date_str)
    except (TypeError, ValueError) as exc:
        raise ValueError("date_str must be a valid YYYY-MM-DD date") from exc
    if parsed_date.isoformat() != date_str:
        raise ValueError("date_str must be a valid YYYY-MM-DD date")

# --- CENTRALIZED CONFIGURATION ---
if not settings.GOOGLE_API_KEY:
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
    _validate_tool_date(date_str)
    logger.info(f"🤖 AI AGENT TOOL CALLED: check_calendar_availability for {date_str}")
    return json.dumps({
        "available_slots": ["09:00", "11:30", "15:00", "17:00"],
        "message": "These are the available slots. Ask the user which one they prefer."
    })

def book_appointment(date_str: str, time_str: str, lead_name: str) -> str:
    """Books an appointment for the lead on the specified date and time."""
    _validate_tool_date(date_str)
    if not _TIME_FORMAT.fullmatch(time_str):
        raise ValueError("time_str must be a valid 24-hour HH:MM time")
    if not lead_name.strip() or len(lead_name) > 50:
        raise ValueError("lead_name must contain between 1 and 50 characters")
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
        self.model_name = "gemini-2.5-flash"
        self.client = genai.Client(
            api_key=settings.GOOGLE_API_KEY or None,
            http_options=types.HttpOptions(
                timeout=int(AI_REQUEST_TIMEOUT_SECONDS * 1000)
            ),
        )

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
                with open(media_path, "rb") as media_file:
                    content.append(
                        types.Part.from_bytes(
                            data=media_file.read(),
                            mime_type=mime_type,
                        )
                    )
                
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=content,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        max_output_tokens=MAX_OUTPUT_TOKENS,
                    ),
                )
            except Exception as cfg_err:
                logger.warning(
                    "JSON Mode configuration failed; retrying without explicit mime_type (%s)",
                    type(cfg_err).__name__,
                )
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=content,
                    config=types.GenerateContentConfig(
                        max_output_tokens=MAX_OUTPUT_TOKENS,
                    ),
                )
                
            if not response.text:
                return {}

            clean_text = self._clean_json_text(response.text)
            result = json.loads(clean_text)
            if isinstance(result, dict) and isinstance(result.get("reply_text"), str):
                result["reply_text"] = sanitize_ai_output(result["reply_text"])
            return result

        except Exception as e:
            logger.error("AI generation failed (%s)", type(e).__name__)
            return {
                "error": "AI request failed",
                "reply_text": "I'm sorry, I'm having a technical moment. Please try again.",
            }

    async def analyze_interaction(
        self,
        system_prompt: str,
        text_input: str = None,
        audio_path: str = None,
        sender_name: str = "Guest",
        expected_schema: str = None,
        chat_history: List[Dict] = None
    ) -> Dict[str, Any]:
        if text_input is not None:
            text_input = text_input[: PromptBuilder.MAX_INBOUND_MESSAGE_LENGTH]

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

                formatted_history = []
                if chat_history:
                    for msg in chat_history:
                        role = "user" if msg.get("sender_type") == "user" else "model"
                        content = str(msg.get("content", ""))[
                            : PromptBuilder.MAX_INBOUND_MESSAGE_LENGTH
                        ]
                        formatted_history.append(
                            types.Content(
                                role=role,
                                parts=[types.Part.from_text(text=content)],
                            )
                        )

                formatted_history.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=f"[{sender_name}]: {text_input}")],
                    )
                )
                generation_config = types.GenerateContentConfig(
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    system_instruction=full_system_instruction,
                    tools=AI_TOOLS,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=10
                    ),
                )

                logger.info("Sending message to AI Agent and awaiting potential tool execution...")
                response = await run_in_threadpool(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=formatted_history,
                    config=generation_config,
                )
                final_text = response.text if hasattr(response, 'text') else ""
                final_text = sanitize_ai_output(final_text)
                
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
                logger.error("Agent execution failed (%s)", type(e).__name__)
                return {
                    "error": "AI request failed",
                    "reply_text": "אני קצת עמוסה כרגע, אפשר לנסות שוב בעוד רגע?",
                    "needs_human_escalation": True
                }

# Singleton Instance
ai_engine = AIEngine()