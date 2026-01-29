import os
import logging
from src.services.providers.twilio import TwilioProvider
from src.services.providers.telnyx import TelnyxProvider
from src.services.providers.vonage import VonageProvider

# הגדרת לוגים פשוטה
logging.basicConfig(level=logging.INFO, format='%(message)s')

def compare_providers():
    print("\n🛒 --- השוואת מחירי מספרים (ישראל) --- 🛒\n")
    
    country = "IL"
    
    # 1. Twilio
    print("🔵 TWILIO:")
    try:
        tw = TwilioProvider()
        results = tw.search_numbers(country_code=country)
        if not results: print("   ❌ No results or Auth failed.")
        for r in results:
            print(f"   📱 {r['phone_number']} | 📍 {r['locality']} | 💰 {r.get('price', '?')} {r.get('currency', '')}")
    except Exception as e: print(f"   ❌ Error: {e}")

    # 2. Telnyx
    print("\n🟢 TELNYX:")
    try:
        tl = TelnyxProvider()
        results = tl.search_numbers(country_code=country)
        if not results: print("   ❌ No results or Auth failed.")
        for r in results:
            print(f"   📱 {r['phone_number']} | 💰 {r.get('price', '?')} {r.get('currency', '')}")
    except Exception as e: print(f"   ❌ Error: {e}")

    # 3. Vonage
    print("\n💜 VONAGE:")
    try:
        vn = VonageProvider()
        results = vn.search_numbers(country_code=country)
        if not results: print("   ❌ No results or Auth failed.")
        for r in results:
            print(f"   📱 {r['phone_number']} | 💰 {r.get('price', '?')} {r.get('currency', '')}")
    except Exception as e: print(f"   ❌ Error: {e}")

    print("\n-------------------------------------------")

if __name__ == "__main__":
    compare_providers()