from abc import ABC, abstractmethod
from typing import Optional

class PhoneProviderStrategy(ABC):
    """
    Abstract Base Class that defines the interface for all phone providers.
    Every new provider (Twilio, Telnyx, Vonage) must implement these methods.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the name of the provider (e.g., 'TWILIO')"""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Checks if the API keys are present in settings"""
        pass

    @abstractmethod
    def search_and_buy_number(self, country_code: str, number_type: str, user_id: str) -> Optional[str]:
        """
        Attempts to search and buy a number.
        
        Args:
            country_code: 'IL', 'US', etc.
            number_type: 'local' (landline) or 'mobile'.
            user_id: The ID of the user requesting the number (for tagging/friendly name).
            
        Returns:
            str: The purchased phone number in E.164 format (e.g., +97250...) or None if failed.
        """
        pass