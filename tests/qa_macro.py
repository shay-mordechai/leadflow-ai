# tests/qa_macro.py
import requests, sys, getpass, argparse, time
from requests.exceptions import Timeout

DEFAULT_LOCAL_URL = "http://127.0.0.1:8000"
PROD_URL = "https://my-leads.app" 
REQ_TIMEOUT = 15

GREEN, RED, YELLOW, CYAN, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m"

def log(step, msg, status="INFO"):
    color = GREEN if status == "SUCCESS" else RED if status == "FAIL" else YELLOW if status == "WARN" else CYAN if status == "INPUT" else RESET
    print(f"[{step}] {color}{msg}{RESET}")

def run_macro_qa():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true")
    args = parser.parse_args()
    base_url = PROD_URL if args.prod else DEFAULT_LOCAL_URL

    print(f"\n🚀 STARTING MACRO QA (CORE FLOW) FOR: {base_url}\n" + "="*60)
    email = f"macro_{int(time.time())}@test.com"
    password = "YourPassword123!"

    # 1. AUTH & LOGIN
    requests.post(f"{base_url}/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Macro QA", "business_name": "Macro Biz", "plan_tier": "starter"})
    res = requests.post(f"{base_url}/api/v1/auth/login", data={"username": email, "password": password})
    if res.status_code != 200: sys.exit(log("AUTH", "Login Failed", "FAIL"))
    
    otp_code = input(f"[{RESET}INPUT{RESET}] 🔢 Enter OTP Code (Check Logs): ").strip()
    token = requests.post(f"{base_url}/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp_code}).json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    user_id = requests.get(f"{base_url}/api/v1/auth/me", headers=headers).json().get("id")
    log("AUTH", "✅ Registered, Logged In, and Token Acquired.", "SUCCESS")

    # 2. UPGRADE TO PRO
    requests.post(f"{base_url}/api/v1/billing/redeem-coupon", json={"coupon_code": "VIP_SHAY"}, headers=headers)
    log("BILLING", "✅ Upgraded to PRO status.", "SUCCESS")

    # 3. WEBHOOK (LEAD INJECTION)
    test_phone = f"+97250{int(time.time())}"[:13]
    webhook_res = requests.post(f"{base_url}/api/v1/leads/webhook/{user_id}", json={"name": "Macro Lead", "phone": test_phone, "source": "facebook_ad"})
    
    if webhook_res.status_code in [200, 201]:
        log("WEBHOOK", f"✅ Lead {test_phone} successfully injected via webhook.", "SUCCESS")
    else:
        log("WEBHOOK", f"❌ Webhook Failed: {webhook_res.text}", "FAIL")

    print("\n🏁 MACRO QA COMPLETE.\n")

if __name__ == "__main__":
    run_macro_qa()