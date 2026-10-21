# src/services/providers/base.py
from abc import ABC, abstractmethod


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
    def search_numbers(
        self, country_code: str, number_type: str = "local", limit: int = 5
    ) -> list[dict]:
        """Returns a standardized list of available numbers."""

    @abstractmethod
    def purchase_number(self, phone_number: str, user_id: str) -> str | None:
        """Purchases a specific number and configures webhooks."""
