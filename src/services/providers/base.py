# src/services/providers/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class PhoneProviderStrategy(ABC):
    """
    Abstract Base Class for Phone Providers (Twilio, Telnyx, Vonage).
    Enforces a standard interface for the PhoneServiceManager.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def search_numbers(self, country_code: str, number_type: str, limit: int = 5) -> List[Dict]:
        """Returns a standardized list of available numbers."""
        pass

    @abstractmethod
    def purchase_number(self, phone_number: str, user_id: str) -> Optional[str]:
        """Purchases a specific number and configures webhooks."""
        pass