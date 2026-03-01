# tests/qa_micro.py
import requests, sys, argparse, time
from requests.exceptions import Timeout, RequestException

DEFAULT_LOCAL_URL = "http://127.0.0.1:8000"
PROD_URL = "https://my-leads.app" 
REQ_TIMEOUT = 10
LOGIN_TIMEOUT = 25

GREEN, RED, YELLOW, CYAN, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m"

def log(step, msg, status="INFO"):
    color = GREEN if status == "SUCCESS" else RED if status == "FAIL" else YELLOW if status == "WARN" else CYAN if status == "INPUT" else RESET
    print(f"[{step}] {color}{msg}{RESET}")

def run_micro_qa():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true")
    parser.add_argument("--email", type=str)
    parser.add_argument("--password", type=str)
    args = parser.parse_args()
    
    # When using SSH Tunnel, we rely on the LOCAL_URL to securely reach Production
    base_url = PROD_URL if args.prod else DEFAULT_LOCAL_URL

    ts = int(time.time())
    email = args.email if args.email else f"owner_{ts}@test.com"
    password = args.password if args.password else "SecurePassword123!"
    owner_phone = "+972541112222" # Simulated business owner phone number

    print(f"\n🔬 STARTING MICRO QA (ADVANCED AI & COMMANDS) FOR: {base_url}")
    print(f"👤 Testing with User: {email}\n" + "="*60)
    
    # --- 1. REGISTRATION & LOGIN ---
    log("AUTH", "Authenticating to get a real token...", "INFO")
    try:
        requests.post(f"{base_url}/api/v1/auth/register", json={
            "email": email, "password": password, "full_name": "Shay Owner", 
            "business_name": "Yoga Studio", "business_type": "Fitness"
        }, timeout=REQ_TIMEOUT)
        
        login_res = requests.post(f"{base_url}/api/v1/auth/login", data={"username": email, "password": password}, timeout=LOGIN_TIMEOUT)
        if login_res.status_code != 200: sys.exit(log("AUTH", f"Login failed: {login_res.text}", "FAIL"))
        
        otp_code = input(f"[{RESET}INPUT{RESET}] 🔢 Enter OTP Code: ").strip()
        auth_res = requests.post(f"{base_url}/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp_code}, timeout=REQ_TIMEOUT)
        token = auth_res.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        user_id = requests.get(f"{base_url}/api/v1/auth/me", headers=headers, timeout=REQ_TIMEOUT).json().get("id")
        log("AUTH", "✅ Authentication successful.", "SUCCESS")
    except Exception as e:
        sys.exit(log("AUTH", f"Auth flow failed: {e}", "FAIL"))

    # --- SETUP: Business Profile & Tag ---
    log("SETUP", "Setting up Owner Phone and Tags...", "INFO")
    requests.patch(f"{base_url}/api/v1/users/me", json={"personal_whatsapp": owner_phone}, headers=headers)
    requests.post(f"{base_url}/api/v1/tags", json={"name": "Kiryat Netafim"}, headers=headers)

    # --- TEST 1: OWNER COMMAND MODE ---
    log("2. OWNER-CMD", "Simulating OWNER sending a broadcast command via WhatsApp...", "INFO")
    cmd_payload = {
        "From": f"whatsapp:{owner_phone}", 
        "To": "whatsapp:+97233829709", 
        "Body": "Send a message to all the girls from Kiryat Netafim that tomorrow's class is canceled"
    }
    cmd_res = requests.post(f"{base_url}/webhooks/twilio/sms", data=cmd_payload)
    if cmd_res.status_code == 200:
        log("2. OWNER-CMD", "✅ System recognized Owner. Check server logs to see Gemini parsing the Broadcast intent.", "SUCCESS")
    else:
        log("2. OWNER-CMD", f"❌ Command failed: {cmd_res.status_code}", "FAIL")

    # --- TEST 2: HUMAN HANDOFF ---
    log("3. HANDOFF", "Simulating Lead asking for a human...", "INFO")
    lead_phone = f"+97250999{str(ts)[-4:]}"
    
    # First, inject the lead so the system recognizes the incoming phone number
    webhook_url = f"{base_url}/api/v1/leads/webhook/{user_id}"
    requests.post(webhook_url, json={"name": "Angry Lead", "phone": lead_phone, "source": "QA_Micro"})
    time.sleep(2) # Give the DB a moment to save the lead
    
    # Now, send the "angry" message triggering the Handoff protocol
    handoff_payload = {
        "From": f"whatsapp:{lead_phone}", 
        "To": "whatsapp:+97233829709", 
        "Body": "I want to speak to a human representative urgently"
    }
    requests.post(f"{base_url}/webhooks/twilio/sms", data=handoff_payload)
    
    log("3. HANDOFF", "Waiting 5 seconds for Gemini AI to process the intent...", "INFO")
    time.sleep(5) 
    
    # Check Handoff Status
    try:
        # Standard request - the Tunnel handles the networking securely
        leads_res = requests.get(f"{base_url}/api/v1/leads/", headers=headers, timeout=REQ_TIMEOUT)
             
        if leads_res.status_code == 200:
            leads = leads_res.json()
            test_lead = next((l for l in leads if lead_phone in l.get('phone_number', '')), None)
            
            if test_lead and test_lead.get('bot_active') is False:
                log("3. HANDOFF", "✅ Bot successfully muted itself after human request.", "SUCCESS")
            elif test_lead:
                log("3. HANDOFF", "❌ Lead found, but bot is still ACTIVE. Gemini might have failed to trigger [HANDOFF].", "FAIL")
            else:
                log("3. HANDOFF", "❌ Lead not found in the database.", "FAIL")
        else:
            log("3. HANDOFF", f"❌ API Error during Handoff check: {leads_res.status_code}", "FAIL")
            
    except Exception as e:
        log("3. HANDOFF", f"❌ Failed to verify handoff status: {e}", "FAIL")

    print("\n🏁 MICRO QA COMPLETE.\n")

if __name__ == "__main__":
    run_micro_qa()

# Usage:
# 1. Open SSH Tunnel in background: ssh -f -N -L 8000:localhost:8000 production
# 2. Run test: python3 tests/qa_micro.py --email your@email.com --password "YourPassword123!"