# src/services/ai_engine.py

import json
import google.generativeai as genai
from typing import Dict, Optional
from src.config import settings

genai.configure(api_key=settings.GOOGLE_API_KEY)

class AIEngine:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-pro')

    def _clean_json_text(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _build_system_prompt(self, business_type: str, city_coverage: Optional[str]) -> str:
        cities = city_coverage if city_coverage else "General/Remote"

        return f"""
        You are an expert AI Assistant for a {business_type}.
        Analyze the incoming message (lead inquiry) and extract structured data.

        **Context:**
        - Industry: {business_type}
        - Service Areas: {cities}

        **Tasks:**
        1. **Score:** Intent Score 1-10.
        2. **Location:** Extract city.
        3. **Summary:** Short Hebrew summary.
        4. **Reply Draft:** Write a polite, professional Hebrew WhatsApp reply (1-2 sentences) addressed to the lead.
           Example: "Hi [Name], I saw you're interested in [Service]. When is a good time to talk?"
        5. **Follow-up:** Detect if the lead asks to talk later (e.g., "call me next week"). Set 'needs_followup' to true.

        **Output JSON:**
        {{
            "lead_name": "string or null",
            "lead_phone": "string or null",
            "location": "string or null",
            "intent_score": integer,
            "summary": "Hebrew string",
            "suggested_reply": "Hebrew string",
            "needs_followup": boolean
        }}
        """

    def analyze_lead_message(self, text: str, business_type: str, city_coverage: str = None) -> Dict:
        system_instructions = self._build_system_prompt(business_type, city_coverage)
        full_prompt = f"{system_instructions}\n\nAnalyze this message:\n{text}"

        try:
            response = self.model.generate_content(full_prompt)
            cleaned_text = self._clean_json_text(response.text)
            data = json.loads(cleaned_text)
            return data

        except json.JSONDecodeError:
            return {
                "lead_name": None,
                "intent_score": 0,
                "summary": "Error parsing AI",
                "suggested_reply": "היי, אשמח לשמוע פרטים נוספים.",
                "needs_followup": False,
                "location": "Unknown"
            }
        except Exception as e:
            print(f"AI Engine Error: {str(e)}")
            return {
                "lead_name": None,
                "intent_score": 0,
                "summary": "System Error",
                "suggested_reply": "",
                "needs_followup": False,
                "location": "Unknown"
            }

ai_engine = AIEngine()
