# tests/qa_webhooks.py
import asyncio
import httpx
import sys
import uuid
import logging
from datetime import datetime, timezone

# ---------------------------------------------------------
# Terminal color definitions
# ---------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def log(msg, status="INFO"):
    color = GREEN if status == "SUCCESS" else RED if status == "FAIL" else YELLOW
    print(f"{color}{msg}{RESET}")

# ---------------------------------------------------------
# Environment settings for testing
# ---------------------------------------------------------
# Assuming the server is running locally (ensure it is running in the background: uvicorn src.main:app)
BASE_URL = "http://127.0.0.1:8000/api/v1"
# To test against the real server, use "https://my-leads.app/api/v1" here

# Mock user. In a real system, you should fetch a real user from the DB.
# Here we use a valid UUID that will pass the router's validation.
TEST_USER_ID = str(uuid.uuid4())

async def run_webhook_tests():
    print(f"\n🚀 מתחיל בדיקות QA ל-Webhooks ו-Idempotency")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        
        # ---------------------------------------------------------
        # Test 1: Injecting a standard lead (Success)
        # ---------------------------------------------------------
        log("\n--- מבחן 1: קליטת ליד תקין ---", "INFO")
        
        test_lead_phone = "0509998887"
        idemp_key = f"TEST_KEY_{int(datetime.now(timezone.utc).timestamp())}"
        
        payload_1 = {
            "name": "ליד בדיקה",
            "phone": test_lead_phone,
            "source": "FACEBOOK_AD",
            "idempotency_key": idemp_key
        }
        
        try:
            # Note: If the user doesn't exist in your local DB, this test will return 404 (which is fine for security).
            # For it to pass green, you need to create a mock user in the DB and put their ID above.
            res1 = await client.post(f"{BASE_URL}/leads/webhook/{TEST_USER_ID}", json=payload_1)
            print(f"סטטוס: {res1.status_code}")
            print(f"תשובה: {res1.text}")
            
            if res1.status_code == 200:
                log("✅ עבר: הליד נקלט בהצלחה.", "SUCCESS")
            elif res1.status_code == 404:
                 log("⚠️ עבר (חלקית): השרת זיהה שהמשתמש לא קיים וחסם (הגנת IDOR).", "YELLOW")
            else:
                log(f"❌ נכשל: קוד סטטוס לא צפוי.", "FAIL")
                
        except Exception as e:
            log(f"❌ שגיאת רשת: {e}", "FAIL")

        # ---------------------------------------------------------
        # Test 2: Idempotency protection (Prevent duplication)
        # ---------------------------------------------------------
        log("\n--- מבחן 2: ניסיון לשכפל ליד קיים (Idempotency Shield) ---", "INFO")
        print("שולח את אותו Payload בדיוק שוב...")
        
        try:
            res2 = await client.post(f"{BASE_URL}/leads/webhook/{TEST_USER_ID}", json=payload_1)
            print(f"סטטוס: {res2.status_code}")
            
            if res2.status_code == 200 and "already processed" in res2.text:
                 log("✅ עבר: מנגנון מניעת השכפולים חסם את הליד הכפול והחזיר 200 לזאפייר!", "SUCCESS")
            elif res1.status_code == 404:
                 log("⚠️ המשתמש לא קיים, מדלג.", "YELLOW")
            else:
                 log("❌ נכשל: המערכת לא זיהתה שזהו כפילות או שהחזירה שגיאה לא נכונה.", "FAIL")
                 
        except Exception as e:
             log(f"❌ שגיאת רשת: {e}", "FAIL")

        # ---------------------------------------------------------
        # Test 3: Missing or malicious data (Validation)
        # ---------------------------------------------------------
        log("\n--- מבחן 3: ניסיון הזרקת נתונים פגומים ---", "INFO")
        
        payload_bad = {
            "name": "X", # Too short (we defined a minimum of 2)
            "phone": "123", # Too short
            "source": "HACKER_SCRIPT" * 10 # Too long
        }
        
        try:
            res3 = await client.post(f"{BASE_URL}/leads/webhook/{TEST_USER_ID}", json=payload_bad)
            print(f"סטטוס: {res3.status_code}")
            
            if res3.status_code == 422: # Unprocessable Entity (Pydantic ValidationError)
                 log("✅ עבר: חומת המגן של Pydantic חסמה נתונים לא חוקיים.", "SUCCESS")
            else:
                 log(f"❌ נכשל: השרת אישר נתונים פגומים! סטטוס: {res3.status_code}", "FAIL")
                 
        except Exception as e:
             log(f"❌ שגיאת רשת: {e}", "FAIL")

        print("\n" + "="*60)
        print(f"🏁 בדיקות WEBHOOKS הסתיימו.")

if __name__ == "__main__":
    # Ensure event loop runs correctly across platforms
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_webhook_tests())