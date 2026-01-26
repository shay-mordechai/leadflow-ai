import json
import logging
import google.generativeai as genai
from typing import Dict, Optional
from src.config import settings
from src.config.prompts import get_business_config

# Setup Logger
logger = logging.getLogger(__name__)

# Configure Gemini with the API key from settings
genai.configure(api_key=settings.GOOGLE_API_KEY)

class AIEngine:
    def __init__(self):
        # Using gemini-1.5-flash as it is currently the most stable/cost-effective for this task.
        model_name = "gemini-1.5-flash" 
        
        self.model = genai.GenerativeModel(
            model_name,
            # CRITICAL: Enforce JSON output natively. This prevents parsing errors.
            generation_config={"response_mime_type": "application/json"}
        )

    def _build_analysis_prompt(self, business_type: str, business_name: str, city_coverage: Optional[str]) -> str:
        """
        Constructs the system instructions by combining:
        1. The specific Business Persona (from prompts.py)
        2. The Technical Analysis Requirements (JSON extraction)
        """
        cities = city_coverage if city_coverage else "General Service / Remote"
        
        # Retrieve the specific persona configuration
        # This gives us the 'system_role' (Tone/Rules)
        persona_config = get_business_config(business_type, business_name)
        business_persona = persona_config["system_role"]

        return f"""
        {business_persona}

        **Your Task: Lead Analysis**
        You are analyzing an incoming message to extract structured data and draft a reply.

        **Business Context:**
        - Industry: {business_type}
        - Service Areas: {cities}

        **Analysis Requirements:**
        1. **Intent Score:** Rate the lead's intent from 1 (Spam/Irrelevant) to 10 (High Value/Urgent).
        2. **Location:** Extract the city or region mentioned.
        3. **Summary:** Write a concise summary of the request in Hebrew.
        4. **Reply Draft:** Draft a reply in Hebrew based on your Persona rules above.
           - **Crucial:** Match the tone defined in your persona (e.g., use emojis for Yoga, formal for Real Estate).
           - Address the user by name if available.
        5. **Follow-up:** Set 'needs_followup' to true if the user asks to be contacted later.

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

    def analyze_lead_message(self, text: str, business_type: str, business_name: str = "My Business", city_coverage: str = None) -> Dict:
        """
        Sends the text to Gemini and returns a structured dictionary.
        Accepts 'business_name' to allow personalized persona injection.
        """
        system_instructions = self._build_analysis_prompt(business_type, business_name, city_coverage)
        full_prompt = f"{system_instructions}\n\n**Incoming Message to Analyze:**\n{text}"

        try:
            logger.info(f"Sending request to Gemini for business: {business_type} ({business_name})")
            
            response = self.model.generate_content(full_prompt)
            
            # Since we enforced JSON mode, response.text should be valid JSON.
            data = json.loads(response.text)
            
            return data

        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing Error from AI response: {response.text}")
            return self._get_error_fallback(f"Error parsing AI response: {str(e)}")
            
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