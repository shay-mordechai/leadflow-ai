# src/services/whatsapp_adapter.py

from sqlalchemy.orm import Session
from src.database.models import Tenant
from src.services.ai_engine import ai_engine
from src.security.hashing import verify_hash

class WhatsAppAdapter:
    """
    Professional English Comment:
    WhatsApp Adapter.
    Handles Incoming Webhooks, Tenant Authentication, and Message sending.
    """

    def send_message(self, to_phone: str, text: str):
        """
        Sends a message via the configured WhatsApp provider (Mock/Twilio/Meta).
        """
        print(f"\n[WhatsApp Outgoing -> {to_phone}]:\n{text}\n")

    def _is_forwarded_lead(self, text: str) -> bool:
        """
        Heuristic detection to check if a message is a forwarded lead.
        """
        triggers = ["forwarded", "מועבר", "הועבר", "שם:", "טלפון:", "name:", "phone:"]
        normalized = text.lower()
        return any(t in normalized for t in triggers)

    def process_incoming_webhook(self, db: Session, sender_phone: str, message_text: str, api_key: str):
        """
        Main logic flow: Auth -> Detect -> Analyze -> Reply.
        """
        # 1. Authenticate Tenant using the API Key
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        current_tenant = None

        for t in tenants:
            if verify_hash(api_key, t.api_key_hash):
                current_tenant = t
                break

        if not current_tenant:
            print("Error: Unauthorized Webhook Attempt")
            return

        # 2. Check if it's a lead
        if self._is_forwarded_lead(message_text):
            print(f"Detected potential lead for Business: {current_tenant.business_type}")

            # 3. AI Analysis via Gemini
            analysis = ai_engine.analyze_lead_message(
                text=message_text,
                business_type=current_tenant.business_type or "General Business",
                city_coverage=current_tenant.city_coverage
            )

            # 4. Format Result for User
            response_text = (
                f"📊 **LeadFlowAI Analysis**\n"
                f"------------------------\n"
                f"🏢 Type: {current_tenant.business_type}\n"
                f"👤 Name: {analysis.get('lead_name', 'Unknown')}\n"
                f"📍 City: {analysis.get('location', 'Unknown')}\n"
                f"🔥 Score: {analysis.get('intent_score')}/10\n\n"
                f"📝 Summary: {analysis.get('summary')}"
            )

            self.send_message(sender_phone, response_text)
        else:
            print("Standard message received (Not a forwarded lead).")

whatsapp_adapter = WhatsAppAdapter()
