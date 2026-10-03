# src/services/providers/aggregator.py
import logging
from typing import List, Dict, Optional

# --- Graceful Imports for WIP Integrations ---
# This prevents the entire app/tests from crashing if a provider file 
# is missing or incomplete during development.

try:
    from src.services.providers.twilio import twilio_provider
except ImportError:
    twilio_provider = None

try:
    from src.services.providers.plivo import plivo_provider  
except ImportError:
    plivo_provider = None

try:
    from src.services.providers.vonage import vonage_provider 
except ImportError:
    vonage_provider = None

logger = logging.getLogger("ProviderAggregator")

class ProviderAggregator:
    """
    Least-Cost Routing (LCR) engine for phone number provisioning.
    Queries all enabled VoIP/SMS providers and selects the cheapest option.
    """
    def __init__(self):
        # Dynamically load only the providers that were successfully imported
        _all_providers = [twilio_provider, plivo_provider, vonage_provider]
        self.providers = [p for p in _all_providers if p is not None]

    def find_cheapest_number(self, country_code: str = "IL", contains: str = None) -> Optional[Dict]:
        """
        Aggregates available numbers from all configured providers,
        sorts them by monthly price, and returns the cheapest option.
        """
        all_options: List[Dict] = []

        for provider in self.providers:
            if getattr(provider, 'is_configured', False):
                try:
                    # Some providers might not support the 'contains' kwarg natively, handled in their strategy
                    numbers = provider.search_numbers(country_code=country_code) 
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
            # Check matching provider name
            if getattr(provider, 'provider_name', '').lower() == provider_name.lower() or provider_name.lower() in str(type(provider)).lower():
                
                # FIXED: Called 'purchase_number' instead of 'buy_number' to match PlivoProvider interface
                if hasattr(provider, 'purchase_number'):
                    return provider.purchase_number(phone_number, friendly_name)
                elif hasattr(provider, 'buy_number'):
                    return provider.buy_number(phone_number, friendly_name)
        
        logger.error(f"Provider {provider_name} not found or unconfigured for purchase.")
        return None

number_aggregator = ProviderAggregator()