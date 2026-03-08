# src/services/ai/engine.py
import json
import logging
import os
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


# --- DEFINE AI TOOLS (THE "AGENTS") ---
# These functions will be exposed to Gemini. It will decide when to call them autonomously.

def check_calendar_availability(date_str: str) -> str:
    """Checks the business owner's calendar for available slots on a given date (YYYY-MM-DD)."""
    # TODO: Phase 3/4 - Connect to Google Calendar API
    logger.info(f"🤖 AI AGENT TOOL CALLED: check_calendar_availability for {date_str}")
    return json.dumps({
        "available_slots": ["09:00", "11:30", "15:00", "17:00"],
        "message": "These are the available slots. Ask the user which one they prefer."
    })

def book_appointment(date_str: str, time_str: str, lead_name: str) -> str:
    """Books an appointment for the lead on the specified date and time."""
    # TODO: Phase 3/4 - Save to DB / Google Calendar
    logger.info(f"🤖 AI AGENT TOOL CALLED: book_appointment for {lead_name} at {date_str} {time_str}")
    return json.dumps({
        "status": "success",
        "message": "Appointment booked successfully. Confirm it politely with the user."
    })

def qualify_lead(budget: int, timeframe: str) -> str:
    """Saves the lead's budget and timeframe to the database to qualify them."""
    # TODO: Phase 3/4 - Update the Lead table in the DB
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
    """
    
    def __init__(self):
        # Using 'gemini-2.0-flash' for speed and cost efficiency.
        self.model_name = "gemini-2.0-flash"
        self.model = genai.GenerativeModel(self.model_name)
        
        # NEW: Agent Model (Initialized with Tools for autonomous actions)
        self.agent_model = genai.GenerativeModel(
            model_name=self.model_name,
            tools=AI_TOOLS
        )

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
            
            # Generate Response with JSON Mode fallback for older SDK versions
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
        """
        High-level flow for Chatbot Personas.
        Now Supports: Legacy JSON Parsing (for audio) AND Agentic Function Calling (for text chat).
        """
        
        # SCENARIO A: Audio/Media or Explicit Schema provided -> Use Legacy JSON Mode
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
                formatted_history = []
                if chat_history:
                    for msg in chat_history:
                        role = "user" if msg.get("sender_type") == "user" else "model"
                        formatted_history.append({"role": role, "parts": [msg.get("content", "")]})

                agent_session = self.agent_model.start_chat(
                    history=formatted_history,
                    enable_automatic_function_calling=True
                )

                agent_prompt = f"""
                [SYSTEM PERSONA - ADHERE STRICTLY]:
                {system_prompt}
                
                [USER NAME]: {sender_name}
                [USER MESSAGE]: {text_input}
                
                [INSTRUCTIONS]:
                1. If the user asks about availability, autonomously use the 'check_calendar_availability' tool.
                2. If the user wants to book, autonomously use the 'book_appointment' tool.
                3. If you need to qualify a budget/timeframe, autonomously use the 'qualify_lead' tool.
                4. Always respond naturally, in character, and in the user's language (mostly Hebrew).
                5. If they are angry or asking complex questions outside your scope, include the exact word "[HANDOFF]" in your response so a human can take over.
                """

                logger.info("Sending message to AI Agent and awaiting potential tool execution...")
                response = await run_in_threadpool(agent_session.send_message, agent_prompt)
                
                final_text = response.text
                needs_human = "[HANDOFF]" in final_text or "human" in final_text.lower()

                return {
                    "intent": "agent_handled",
                    "reply_text": final_text.replace("[HANDOFF]", "").strip(),
                    "needs_human_escalation": needs_human
                }

            except Exception as e:
                logger.error(f"Agent Execution Error: {e}")
                return {
                    "error": str(e), 
                    "reply_text": "אני קצת עמוסה כרגע, אפשר לנסות שוב עוד דקה?", 
                    "needs_human_escalation": True
                }

# Singleton Instance
ai_engine = AIEngine()