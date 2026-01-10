import re
import bleach
from typing import Tuple, Optional

class SecurityValidator:
    """
    OWASP Input Validation & Sanitization Utility.
    """

    # Strict Regex for Israeli Mobile Numbers (05X-XXXXXXX or +972-5X-XXXXXXX)
    # Prevents Injection via phone fields and ensures data integrity.
    ISRAEL_PHONE_REGEX = re.compile(r'^(?:\+972|0)(5[0-248-9])\-?\d{7}$')

    @staticmethod
    def sanitize_text(text: Optional[str]) -> str:
        """
        Sanitizes input strings to prevent Stored Cross-Site Scripting (XSS).
        Removes all HTML tags and dangerous attributes.
        """
        if not text:
            return ""

        # 'strip=True' removes the tags entirely (e.g. <script>alert(1)</script> -> alert(1))
        # This renders the payload inert in an HTML context.
        cleaned = bleach.clean(text, tags=[], attributes={}, strip=True)
        return cleaned.strip()

    @staticmethod
    def validate_israeli_phone(phone: str) -> Tuple[bool, str]:
        """
        Validates and normalizes phone numbers.
        Returns: (is_valid, normalized_number)
        """
        if not phone:
            return False, ""

        # Remove common separators (dashes, spaces)
        clean_num = re.sub(r'[\s\-]', '', phone)

        match = SecurityValidator.ISRAEL_PHONE_REGEX.match(clean_num)
        if match:
            # Normalize to 05X format for DB consistency
            if clean_num.startswith('+972'):
                clean_num = '0' + clean_num[4:]
            return True, clean_num

        return False, ""
