# src/security/encryption.py
# Handles symmetric encryption for Personally Identifiable Information (PII)
# such as phone numbers and transcripts. Uses the Fernet (AES-128) implementation.
# This ensures data at rest is unreadable without the specific application key.

import logging

from cryptography.fernet import Fernet

from src.config import settings

logger = logging.getLogger("Security")


class PIIProtector:
    """Singleton class for handling encryption and decryption operations.

    Wraps the cryptography library to provide a clean interface for the ORM.
    """

    def __init__(self):
        self._cipher = None

    def _get_cipher(self) -> Fernet:
        """Lazy-loads the cipher instance.

        Enforces a fail-fast strategy: ephemeral fallback keys are strictly
        permitted only under testing environments to prevent data loss.
        """
        if self._cipher is None:
            key = getattr(settings, "ENCRYPTION_KEY", None)
            env = getattr(settings, "ENVIRONMENT", "development").lower()

            if not key:
                # Restrict ephemeral fallback keys exclusively to test execution
                if env in ("test", "testing"):
                    logger.warning(
                        "ENCRYPTION_KEY missing in test environment. Using ephemeral key."
                    )
                    self._cipher = Fernet(Fernet.generate_key())
                else:
                    logger.critical("FATAL: ENCRYPTION_KEY is unset in a non-test environment.")
                    raise RuntimeError(
                        "CRITICAL_SECURITY_CONFIGURATION_ERROR: ENCRYPTION_KEY must be set in non-test environments. "
                        "Generating ephemeral keys in development or production causes irreversible data loss."
                    )
            else:
                try:
                    self._cipher = Fernet(key)
                except Exception as e:
                    logger.critical(f"Failed to initialize Fernet cipher: {e}")
                    raise ValueError(
                        "INVALID_ENCRYPTION_KEY: Key must be a valid 32-byte url-safe base64-encoded string."
                    )

        return self._cipher

    def encrypt(self, plaintext: str) -> str | None:
        """Encrypts a plaintext string.

        Returns the URL-safe base64-encoded ciphertext string.
        """
        if plaintext is None:
            return None

        try:
            cipher = self._get_cipher()
            # Fernet requires bytes input and produces bytes output
            return cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption operation failed: {e}")
            return None

    def decrypt(self, ciphertext: str) -> str | None:
        """Decrypts a ciphertext string.

        Returns the original plaintext string or a fallback token on failure.
        """
        if ciphertext is None:
            return None

        try:
            cipher = self._get_cipher()
            return cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception as e:
            # Decryption failure is logged as a critical security issue.
            # A placeholder is returned to prevent unhandled service crashes.
            logger.error(f"Decryption failed for ciphertext. Key might be rotated or invalid: {e}")
            return "[DECRYPTION_FAILED]"


# Global instance to be used by SQLAlchemy models and services.
# The internal cipher is initialized only upon first usage.
protector = PIIProtector()
