from pydantic import BaseModel, EmailStr, Field, field_validator
import re

# --- Constants for Regex Patterns ---
# שמות: עברית, אנגלית, רווחים, גרש ומקף בלבד
NAME_REGEX = r"^[a-zA-Zא-ת\s\-']+$"
# טלפון: פורמט ישראלי או בינלאומי בסיסי (05X-XXXXXXX או +972...)
PHONE_REGEX = r"^(\+972|05)[0-9\-]{8,15}$"
# תחום עיסוק (שדה חופשי): אותיות, מספרים, רווחים ומקפים בלבד (למניעת SQLi/XSS)
SAFE_TEXT_REGEX = r"^[a-zA-Zא-ת0-9\s\-\.]+$"

class UserRegister(BaseModel):
    # שדות חובה
    name: str = Field(..., min_length=2, max_length=50, description="User full name")
    email: EmailStr
    password: str = Field(..., min_length=8, description="Plain text password")
    business_type: str = Field(..., max_length=50) # הערך מה-Select (באנגלית)
    
    # שדות אופציונליים מהטופס החדש
    other_business_type: str | None = Field(None, max_length=50)
    personal_whatsapp: str | None = Field(None, max_length=20)
    business_whatsapp: str | None = Field(None, max_length=20)
    city_coverage: str | None = Field(None, max_length=50)
    needs_new_number: bool = False

    # --- Validators ---

    @field_validator('name', 'city_coverage')
    @classmethod
    def validate_names(cls, v: str | None):
        if v and not re.match(NAME_REGEX, v):
            raise ValueError("השדה מכיל תווים לא חוקיים (מותר רק אותיות, רווחים ומקפים)")
        return v

    @field_validator('personal_whatsapp', 'business_whatsapp')
    @classmethod
    def validate_phones(cls, v: str | None):
        if v:
            # ניקוי רווחים ומקפים לפני בדיקה אם רוצים, או בדיקה נוקשה
            clean_v = v.replace("-", "").replace(" ", "")
            if not re.match(r"^\+?[0-9]{9,15}$", clean_v):
                raise ValueError("מספר הטלפון אינו תקין")
        return v

    @field_validator('other_business_type')
    @classmethod
    def validate_strict_text(cls, v: str | None):
        if v:
            # ולידציה נוקשה לשדה הטקסט החופשי "אחר"
            if not re.match(SAFE_TEXT_REGEX, v):
                raise ValueError("שדה 'אחר' מכיל תווים אסורים. נא להשתמש באותיות ומספרים בלבד.")
            
            # שכבת הגנה נוספת: הסרת תגיות HTML אם בכל זאת עברו (Sanitization)
            v = re.sub(r'[<>]', '', v)
        return v