import asyncio
import logging
from src.services.providers.twilio import TwilioProvider
# כאן אנחנו מניחים שהקבצים האלה קיימים. אם לא - הסקריפט יצעק.
# תוריד את ההערה (uncomment) אם הספקים האלה כבר ממומשים אצלך:
# from src.services.providers.pelephone import PelephoneProvider
# from src.services.providers.bezeq import BezeqProvider

# הגדרת לוגים לראות מה קורה
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InventoryCheck")

async def check_provider(provider_name, provider_instance):
    print(f"\n--- 🇮🇱 בודק מלאי אצל {provider_name} ---")
    try:
        # מנסים למצוא מספרים מקומיים בישראל (Mobile או Local)
        # שים לב: בטוויליו ישראל, לרוב יש מספרים מקומיים (03/04/09) או ניידים
        numbers = await provider_instance.search_numbers(
            country_code="IL", 
            type="local" # או "mobile"
        )
        
        if numbers:
            print(f"✅ נמצאו {len(numbers)} מספרים זמינים לרכישה:")
            for num in numbers[:5]: # מציג רק את ה-5 הראשונים
                print(f"   📞 {num.get('phoneNumber')} | מחיר: {num.get('price')} {num.get('currency')}")
        else:
            print("❌ לא נמצאו מספרים זמינים (המלאי ריק או שאין תמיכה).")

    except Exception as e:
        print(f"⚠️ שגיאה בבדיקת {provider_name}: {e}")

async def main():
    # 1. בדיקת Twilio
    try:
        twilio = TwilioProvider()
        await check_provider("Twilio", twilio)
    except Exception as e:
        print(f"Skipping Twilio: {e}")

    # 2. בדיקת ספקים ישראליים (אם הקוד שלהם קיים)
    # try:
    #     pelephone = PelephoneProvider()
    #     await check_provider("Pelephone", pelephone)
    # except NameError:
    #     print("Skipping Pelephone (Module not imported)")
    
    # try:
    #     bezeq = BezeqProvider()
    #     await check_provider("Bezeq", bezeq)
    # except NameError:
    #     print("Skipping Bezeq (Module not imported)")

if __name__ == "__main__":
    asyncio.run(main())