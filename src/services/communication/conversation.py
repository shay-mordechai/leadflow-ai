# src/services/communication/conversation.py
# Handles bi-directional communication logic between the AI Bot and the Lead.

from src.database.models import Lead
# Adjusted import path for the new folder structure
from src.services.communication.whatsapp_adapter import whatsapp_adapter

class ConversationManager:
    """
    Orchestrates the conversation flow.
    Decides if a message needs an AI reply, a qualification question, or a human handover.
    """
    def __init__(self, db):
        self.db = db

    def process_incoming_message(self, lead: Lead, message_text: str):
        """
        Main entry point for incoming messages.
        Decides whether to ask for city, route the lead, or just respond.
        """
        # Logic: If city is missing, try to extract it or ask for it
        if not lead.city:
            return self._handle_city_discovery(lead, message_text)

        # If city exists, continue to general lead qualification
        return self._handle_general_chat(lead, message_text)

    def _handle_city_discovery(self, lead: Lead, text: str):
        # In a real scenario, we would use NLP here to extract the city first.
        # For now, we ask explicitly.
        response = "היי! אשמח לעזור לך. באיזו עיר אתה מתגורר כדי שאוכל להתאים לך את השירות הקרוב ביותר?"
        whatsapp_adapter.send_message(lead.phone_number, response)

    def _handle_general_chat(self, lead: Lead, text: str):
        # Placeholder for AI Engine integration
        # Future: ai_engine.analyze_interaction(...)
        pass