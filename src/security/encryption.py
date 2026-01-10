# Professional English Comment:
# Handles symmetric encryption for Personally Identifiable Information (PII)
# such as phone numbers and transcripts. Uses the Fernet (AES-128) implementation.
# This ensures data at rest is unreadable without the specific application key.

from cryptography.fernet import Fernet
from typing import Optional
from src.config import settings

class PIIProtector:
    """
    Singleton class for handling encryption/decryption operations.
    Wraps the cryptography library to provide a simple interface for the ORM.
    """

    def __init__(self):
        # Validate that the encryption key exists in the environment settings
        if not settings.ENCRYPTION_KEY:
            raise ValueError("CRITICAL: ENCRYPTION_KEY is missing from configuration. PII cannot be secured.")

        self._cipher = Fernet(settings.ENCRYPTION_KEY)

    def encrypt(self, plaintext: str) -> Optional[str]:
        """
        Encrypts a plaintext string.
        Returns the URL-safe base64-encoded ciphertext.
        """
        if plaintext is None:
            return None
        # Fernet requires bytes input
        return self._cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        Decrypts a ciphertext string.
        Returns the original plaintext.
        """
        if ciphertext is None:
            return None
        try:
            return self._cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception:
            # In a production environment, this should log a high-severity security audit event.
            # Returning a placeholder prevents the application from crashing on UI rendering.
            return "[DECRYPTION_FAILED]"

# Global instance to be used by SQLAlchemy TypeDecorators in models.py
protector = PIIProtector()
