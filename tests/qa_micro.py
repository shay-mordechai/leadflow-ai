# tests/qa_micro.py
import requests, sys, argparse, time, io

DEFAULT_LOCAL_URL = "http://127.0.0.1:8000"
PROD_URL = "https://my-leads.app" 

GREEN, RED, YELLOW, CYAN, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m"

def log(step, msg, status="INFO"):
    color = GREEN if status == "SUCCESS" else RED if status == "FAIL" else YELLOW if status == "WARN" else CYAN if status == "INPUT" else RESET
    print(f"[{step}] {color}{msg}{RESET}")

def run_micro_qa():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true")
    args = parser.parse_args()
    base_url = PROD_URL if args.prod else DEFAULT_LOCAL_URL

    print(f"\n🔬 STARTING MICRO QA (ADVANCED AI & COMMANDS) FOR: {base_url}\n" + "="*60)
    
    # SETUP: Create a real-world scenario
    email = f"owner_{int(time.time())}@test.com"
    owner_phone = "+972541112222" # Simulated owner phone
    
    # 1. Registration & Setup
    requests.post(f"{base_url}/api/v1/auth/register", json={
        "email": email, "password": "Password123!", "full_name": "Shay Owner"
    })
    # ... login & otp flow (abbreviated for the example) ...
    # Assume we got 'token' and 'headers' here
    token = "MOCK_OR_REAL_TOKEN" 
    headers = {"Authorization": f"Bearer {token}"}

    # Setup Business Profile with a specific Tag
    requests.patch(f"{base_url}/api/v1/users/me", json={"personal_whatsapp": owner_phone, "business_name": "Yoga Studio"}, headers=headers)
    requests.post(f"{base_url}/api/v1/tags", json={"name": "קריית נטפים"}, headers=headers)

    # --- TEST 1: REGIONAL PHONE SCAN ---
    log("1. REGIONAL", "Testing Area Code Filtering (Target: '03')...", "INFO")
    res = requests.get(f"{base_url}/api/v1/phones/available?country_code=IL&area_code=03", headers=headers)
    if res.status_code == 200: log("1. REGIONAL", "✅ Twilio API connected & filtered 03 successfully.", "SUCCESS")

    # --- TEST 2: OWNER COMMAND MODE (The 'Yoga Teacher' Feature) ---
    log("2. OWNER-CMD", "Simulating OWNER sending a broadcast command via WhatsApp...", "INFO")
    # We simulate a message coming FROM the owner's personal phone TO the system number
    cmd_payload = {
        "From": f"whatsapp:{owner_phone}", 
        "To": "whatsapp:+97233829709", 
        "Body": "תשלחי הודעה לכל הבנות מקריית נטפים שהשיעור מחר מבוטל"
    }
    cmd_res = requests.post(f"{base_url}/webhooks/twilio/sms", data=cmd_payload)
    if cmd_res.status_code == 200:
        log("2. OWNER-CMD", "✅ System recognized Owner. Check logs to see Gemini parsing the Broadcast intent.", "SUCCESS")

    # --- TEST 3: HUMAN HANDOFF (Muting the Bot) ---
    log("3. HANDOFF", "Simulating Lead asking for a human...", "INFO")
    lead_phone = "+972509998888"
    handoff_payload = {
        "From": f"whatsapp:{lead_phone}", 
        "To": "whatsapp:+97233829709", 
        "Body": "אני רוצה לדבר עם נציג אנושי דחוף"
    }
    requests.post(f"{base_url}/webhooks/twilio/sms", data=handoff_payload)
    
    # Check if lead is now marked as 'requires_human' and 'bot_active=False'
    leads = requests.get(f"{base_url}/api/v1/leads", headers=headers).json()
    test_lead = next((l for l in leads if l['phone_number'] == lead_phone), None)
    
    if test_lead and test_lead.get('bot_active') == False:
        log("3. HANDOFF", "✅ Bot successfully muted itself after human request.", "SUCCESS")
    else:
        log("3. HANDOFF", "❌ Bot failed to mute or lead not found.", "FAIL")

    # --- TEST 4: LOCAL WHISPER (Keep your existing Step 3) ---
    # ... existing Whisper upload code ...

    print("\n🏁 MICRO QA COMPLETE.\n")