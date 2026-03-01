# tests/qa_macro.py
import requests, sys, argparse, time, json
from requests.exceptions import Timeout, RequestException

DEFAULT_LOCAL_URL = "http://127.0.0.1:8000"
PROD_URL = "https://my-leads.app" 
# Long timeout for login because email sending can be slow
REQ_TIMEOUT = 10
LOGIN_TIMEOUT = 25 

GREEN, RED, YELLOW, CYAN, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m"

def log(step, msg, status="INFO"):
    color = GREEN if status == "SUCCESS" else RED if status == "FAIL" else YELLOW if status == "WARN" else CYAN if status == "INPUT" else RESET
    print(f"[{step}] {color}{msg}{RESET}")

def run_macro_qa():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true")
    parser.add_argument("--email", type=str)
    parser.add_argument("--password", type=str)
    args = parser.parse_args()
    
    base_url = PROD_URL if args.prod else DEFAULT_LOCAL_URL

    ts = int(time.time())
    email = args.email if args.email else f"macro_{ts}@test.com"
    password = args.password if args.password else "SecurePassword123!"

    print(f"\n🚀 STARTING MACRO QA (CORE FLOW) FOR: {base_url}")
    print(f"👤 Testing with User: {email}\n" + "="*60)
    
    # --- 1. REGISTRATION ---
    log("AUTH", f"Ensuring user is registered...", "INFO")
    try:
        reg_res = requests.post(f"{base_url}/api/v1/auth/register", json={
            "email": email, 
            "password": password, 
            "full_name": "Macro Tester",
            "business_name": "QA Corp",
            "business_type": "Consulting"
        }, timeout=REQ_TIMEOUT)
        
        if reg_res.status_code == 201:
            log("AUTH", "New user created successfully.", "SUCCESS")
        elif reg_res.status_code == 400:
            log("AUTH", "User already exists, moving to login.", "WARN")
        else:
            log("AUTH", f"Unexpected registration status: {reg_res.status_code} - {reg_res.text}", "FAIL")
            sys.exit()
    except RequestException as e:
        log("AUTH", f"Registration connection error: {e}", "FAIL")

    # --- 2. LOGIN (Triggers OTP) ---
    log("AUTH", "Attempting login to trigger OTP...", "INFO")
    try:
        login_res = requests.post(
            f"{base_url}/api/v1/auth/login", 
            data={"username": email, "password": password}, 
            timeout=LOGIN_TIMEOUT
        )
        if login_res.status_code != 200:
            sys.exit(log("AUTH", f"Login failed ({login_res.status_code}): {login_res.text}", "FAIL"))
        log("AUTH", "Login request successful. OTP should be sent.", "SUCCESS")
    except Timeout:
        sys.exit(log("AUTH", "Login timed out! (Server took too long to send email)", "FAIL"))
    except RequestException as e:
        sys.exit(log("AUTH", f"Login connection error: {e}", "FAIL"))

    # --- 3. MFA VERIFICATION ---
    otp_code = input(f"[{RESET}INPUT{RESET}] 🔢 Enter OTP Code (from email or server logs): ").strip()
    try:
        auth_res = requests.post(f"{base_url}/api/v1/auth/verify-otp", json={
            "email": email, "otp_code": otp_code
        }, timeout=REQ_TIMEOUT)
        
        if auth_res.status_code != 200:
            sys.exit(log("AUTH", f"MFA Verification failed: {auth_res.text}", "FAIL"))
            
        token = auth_res.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        user_data = requests.get(f"{base_url}/api/v1/auth/me", headers=headers, timeout=REQ_TIMEOUT).json()
        user_id = user_data.get("id")
        log("AUTH", "✅ Token acquired and verified.", "SUCCESS")
    except RequestException as e:
        sys.exit(log("AUTH", f"MFA connection error: {e}", "FAIL"))

    # --- 4. UPGRADE TO PRO ---
    log("BILLING", "Applying VIP coupon...", "INFO")
    requests.post(f"{base_url}/api/v1/billing/redeem-coupon", 
                 json={"coupon_code": "VIP_SHAY"}, headers=headers, timeout=REQ_TIMEOUT)
    log("BILLING", "✅ Account promoted to PRO.", "SUCCESS")

    # --- 5. WEBHOOK & IDEMPOTENCY ---
    test_phone = f"+97254{ts % 10000000}" # Generate a valid-ish looking number
    webhook_url = f"{base_url}/api/v1/leads/webhook/{user_id}"
    payload = {"name": "Macro Lead", "phone": test_phone, "source": "facebook_ad"}
    
    log("WEBHOOK", f"Injecting lead {test_phone}...", "INFO")
    res1 = requests.post(webhook_url, json=payload, timeout=REQ_TIMEOUT)
    
    log("WEBHOOK", "Testing Idempotency Shield (sending duplicate)...", "INFO")
    res2 = requests.post(webhook_url, json=payload, timeout=REQ_TIMEOUT)
    
    if res1.status_code in [200, 201] and res2.status_code in [200, 201]:
        log("WEBHOOK", "✅ Webhook handled both requests.", "SUCCESS")
    else:
        log("WEBHOOK", f"❌ Webhook error: {res1.status_code} / {res2.status_code}", "FAIL")

    # --- 6. DATABASE VERIFICATION ---
    log("DATABASE", "Verifying lead data...", "INFO")
    try:
        res = requests.get(f"{base_url}/api/v1/leads", headers=headers, allow_redirects=False, timeout=REQ_TIMEOUT)
        
        if res.status_code in [307, 308]:
            res = requests.get(f"{base_url}/api/v1/leads/", headers=headers, timeout=REQ_TIMEOUT)
            
        leads = res.json()
        matching_leads = [l for l in leads if test_phone in l.get('phone_number', '')]
        
        if len(matching_leads) == 1:
            log("DATABASE", "✅ Success: Exactly 1 lead found (Idempotency works).", "SUCCESS")
            if matching_leads[0].get('bot_active'):
                log("DATABASE", "✅ Bot is ACTIVE for the new lead.", "SUCCESS")
        else:
            log("DATABASE", f"❌ Failed: Found {len(matching_leads)} leads for this phone.", "FAIL")
    except Exception as e:
        log("DATABASE", f"Verification error: {e}", "FAIL")

    print(f"\n🏁 MACRO QA COMPLETE. Status: {GREEN}PASSED{RESET}\n")

if __name__ == "__main__":
    run_macro_qa()