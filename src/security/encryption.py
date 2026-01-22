# Professional English Comment:
# Handles symmetric encryption for Personally Identifiable Information (PII)
# such as phone numbers and transcripts. Uses the Fernet (AES-128) implementation.
# This ensures data at rest is unreadable without the specific application key.

from cryptography.fernet import Fernet
from typing import Optional
import logging
from src.config import settings

logger = logging.getLogger("Security")

class PIIProtector:
    """
    Singleton class for handling encryption/decryption operations.
    Wraps the cryptography library to provide a simple interface for the ORM.
    """

    def __init__(self):
        self._cipher = None

    def _get_cipher(self) -> Fernet:
        """
        Lazy-loads the cipher instance. This ensures that AWS SSM secrets 
        are fully loaded before the encryption engine attempts to initialize.
        """
        if self._cipher is None:
            if not settings.ENCRYPTION_KEY:
                logger.critical("ENCRYPTION_KEY is missing from configuration. System cannot secure PII.")
                raise ValueError("CRITICAL: ENCRYPTION_KEY is required for PII security.")
            
            try:
                self._cipher = Fernet(settings.ENCRYPTION_KEY)
            except Exception as e:
                logger.error(f"Failed to initialize Fernet cipher: {e}")
                raise ValueError("INVALID_ENCRYPTION_KEY: Key must be a 32-byte url-safe base64-encoded string.")
        
        return self._cipher

    def encrypt(self, plaintext: str) -> Optional[str]:
        """
        Encrypts a plaintext string.
        Returns the URL-safe base64-encoded ciphertext.
        """
        if plaintext is None:
            return None
        
        try:
            cipher = self._get_cipher()
            # Fernet requires bytes input
            return cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return None

    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        Decrypts a ciphertext string.
        Returns the original plaintext or a placeholder on failure.
        """
        if ciphertext is None:
            return None
            
        try:
            cipher = self._get_cipher()
            return cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception as e:
            # Professional English Comment:
            # In a production environment, decryption failure should be treated as a 
            # security audit event. We return a placeholder to avoid crashing the UI 
            # while signaling data integrity issues.
            logger.error(f"Decryption failed for ciphertext. Key might be rotated or invalid: {e}")
            return "[DECRYPTION_FAILED]"

# Global instance to be used by SQLAlchemy models and services.
# The internal cipher is initialized only upon first usage.
protector = PIIProtector()