# src/services/providers/aggregator.py
import logging
from typing import List, Dict, Optional
from src.services.providers.twilio import twilio_provider
from src.services.providers.plivo import plivo_provider  # Assuming it exists
from src.services.providers.vonage import vonage_provider # Assuming it exists

logger = logging.getLogger("ProviderAggregator")

class ProviderAggregator:
    """
    Least-Cost Routing (LCR) engine for phone number provisioning.
    Queries all enabled VoIP/SMS providers and selects the cheapest option.
    """
    def __init__(self):
        self.providers = [
            twilio_provider,
            # plivo_provider,
            # vonage_provider
        ]

    def find_cheapest_number(self, country_code: str = "IL", contains: str = None) -> Optional[Dict]:
        """
        Aggregates available numbers from all configured providers,
        sorts them by monthly price, and returns the cheapest option.
        """
        all_options: List[Dict] = []

        for provider in self.providers:
            if provider.is_configured:
                try:
                    numbers = provider.search_numbers(country_code=country_code, contains=contains)
                    all_options.extend(numbers)
                except Exception as e:
                    logger.error(f"Failed to query provider: {e}")

        if not all_options:
            logger.warning("No numbers found across any configured providers.")
            return None

        # Sort by price ascending (cheapest first)
        all_options.sort(key=lambda x: x.get("price_monthly", 999.0))
        
        cheapest = all_options[0]
        logger.info(f"💡 LCR Selected cheapest number: {cheapest['number']} from {cheapest['provider']} at ${cheapest['price_monthly']}/mo")
        return cheapest

    def provision_number(self, provider_name: str, phone_number: str, friendly_name: str) -> Optional[str]:
        """
        Routes the purchase request to the specific provider that won the LCR auction.
        """
        for provider in self.providers:
            if getattr(provider, 'provider_name', '').lower() == provider_name.lower() or provider_name.lower() in str(type(provider)).lower():
                return provider.buy_number(phone_number, friendly_name)
        
        logger.error(f"Provider {provider_name} not found or unconfigured for purchase.")
        return None

number_aggregator = ProviderAggregator()