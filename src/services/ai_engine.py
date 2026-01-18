# src/services/ai_engine.py
import json
import logging
import google.generativeai as genai
from typing import Dict, Optional
from src.config import settings

# Setup Logger
logger = logging.getLogger(__name__)

# Configure Gemini with the API key from settings
genai.configure(api_key=settings.GOOGLE_API_KEY)

class AIEngine:
    def __init__(self):
        # Using gemini-1.5-flash as it is currently the most stable/cost-effective for this task.
        # If 'gemini-2.5-flash' is a valid preview model you have access to, you can keep it.
        model_name = "gemini-1.5-flash" 
        self.model = genai.GenerativeModel(
            model_name,
            # CRITICAL: Enforce JSON output natively. This prevents parsing errors.
            generation_config={"response_mime_type": "application/json"}
        )

    def _build_system_prompt(self, business_type: str, city_coverage: Optional[str]) -> str:
        """Constructs the system instructions for the AI context."""
        cities = city_coverage if city_coverage else "General Service / Remote"

        return f"""
        You are an expert AI Assistant representing a business in the field of: {business_type}.
        Your goal is to analyze incoming lead inquiries and extract structured data.

        **Business Context:**
        - Industry: {business_type}
        - Service Areas: {cities}

        **Analysis Tasks:**
        1. **Intent Score:** Rate the lead's intent from 1 (Spam/Irrelevant) to 10 (High Value/Urgent).
        2. **Location:** Extract the city or region mentioned.
        3. **Summary:** Write a concise summary of the request in Hebrew.
        4. **Reply Draft:** Draft a polite, professional WhatsApp reply in Hebrew (1-2 sentences).
           - Address the user by name if available.
           - Example: "היי [שם], ראיתי שהתעניינת ב[שירות]. מתי נוח לדבר?"
        5. **Follow-up:** Set 'needs_followup' to true if the user asks to be contacted later (e.g., "talk to me next week").

        **Required Output Structure (JSON):**
        {{
            "lead_name": "string or null",
            "lead_phone": "string or null (extract if present in body)",
            "location": "string or null",
            "intent_score": integer,
            "summary": "Hebrew string",
            "suggested_reply": "Hebrew string",
            "needs_followup": boolean
        }}
        """

    def analyze_lead_message(self, text: str, business_type: str, city_coverage: str = None) -> Dict:
        """
        Sends the text to Gemini and returns a structured dictionary.
        """
        system_instructions = self._build_system_prompt(business_type, city_coverage)
        full_prompt = f"{system_instructions}\n\n**Incoming Message to Analyze:**\n{text}"

        try:
            logger.info(f"Sending request to Gemini for business: {business_type}")
            
            response = self.model.generate_content(full_prompt)
            
            # Since we enforced JSON mode, response.text should be valid JSON.
            # We assume the API returns valid JSON, but keeping the try/except is good practice.
            data = json.loads(response.text)
            
            return data

        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing Error from AI response: {response.text}")
            return self._get_error_fallback("Error parsing AI response")
            
        except Exception as e:
            logger.error(f"AI Engine General Error: {str(e)}")
            return self._get_error_fallback("System Error during AI analysis")

    def _get_error_fallback(self, reason: str) -> Dict:
        """Returns a safe default structure in case of failure."""
        return {
            "lead_name": None,
            "intent_score": 0,
            "summary": reason,
            "suggested_reply": "היי, קיבלתי את ההודעה. אחזור אליך בהקדם.",
            "needs_followup": True,
            "location": "Unknown"
        }

# Singleton instance
ai_engine = AIEngine()