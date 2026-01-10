# Professional English Comment:
# Conversation Manager Service.
# Handles bi-directional communication logic between the AI Bot and the Lead.

from .whatsapp_adapter import whatsapp_adapter
from src.database.models import Lead, Tenant

class ConversationManager:
    def __init__(self, db):
        self.db = db

    def process_incoming_message(self, lead: Lead, message_text: str):
        """
        Professional English Comment:
        Main entry point for incoming messages.
        Decides whether to ask for city, route the lead, or just respond.
        """
        # Logic: If city is missing, try to extract it or ask for it
        if not lead.city:
            return self._handle_city_discovery(lead, message_text)

        # If city exists, continue to general lead qualification
        return self._handle_general_chat(lead, message_text)

    def _handle_city_discovery(self, lead: Lead, text: str):
        # Here we would use GPT to check if the city is in the text
        # If not found:
        response = "היי! אשמח לעזור לך. באיזו עיר אתה מגורר כדי שאוכל להתאים לך את המאמן הקרוב ביותר?"
        whatsapp_adapter.send_message(lead.phone_number, response)

    def _handle_general_chat(self, lead: Lead, text: str):
        # General AI responses logic
        pass
