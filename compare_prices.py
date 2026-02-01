import logging
from src.services.providers.twilio import TwilioProvider
from src.services.providers.vonage import VonageProvider
from src.services.providers.plivo import PlivoProvider

# Simple logging setup
logging.basicConfig(level=logging.INFO, format='%(message)s')

def compare_providers():
    print("\n🛒 --- Compare Phone Number Prices (IL - Israel) --- 🛒\n")
    
    country = "IL"
    
    # ---------------------------------------------------------
    # 1. Twilio
    # ---------------------------------------------------------
    print("🔵 TWILIO:")
    try:
        tw = TwilioProvider()
        results = tw.search_numbers(country_code=country)
        
        if not results:
            print("   ❌ No results or Auth failed.")
        else:
            for r in results:
                # Using .get() for safety
                print(f"   📱 {r.get('phone_number')} | 📍 {r.get('locality')} | 💰 {r.get('price')} {r.get('currency')}")
                
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # ---------------------------------------------------------
    # 2. Vonage
    # ---------------------------------------------------------
    print("\n💜 VONAGE:")
    try:
        vn = VonageProvider()
        results = vn.search_numbers(country_code=country)
        
        if not results:
            print("   ❌ No results or Auth failed.")
        else:
            for r in results:
                print(f"   📱 {r.get('phone_number')} | 💰 {r.get('price')} {r.get('currency')}")
                
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # ---------------------------------------------------------
    # 3. Plivo (New)
    # ---------------------------------------------------------
    # print("\n🟠 PLIVO:")
    # try:
    #     pl = PlivoProvider()
    #     results = pl.search_numbers(country_code=country)
        
    #     if not results:
    #         print("   ❌ No results or Auth failed.")
    #     else:
    #         for r in results:
    #             print(f"   📱 {r.get('phone_number')} | 💰 {r.get('price')} {r.get('currency')}")
                
    # except Exception as e:
    #     print(f"   ❌ Error: {e}")

    print("\n-------------------------------------------")

if __name__ == "__main__":
    compare_providers()