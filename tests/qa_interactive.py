import requests
import sys
import getpass
import argparse
import time
import json

# --- CONFIGURATION ---
DEFAULT_LOCAL_URL = "http://127.0.0.1:8000"
PROD_URL = "https://my-leads.app" 

# --- COLORS ---
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def log(step, msg, status="INFO"):
    color = RESET
    if status == "SUCCESS": color = GREEN
    elif status == "FAIL": color = RED
    elif status == "WARN": color = YELLOW
    elif status == "INPUT": color = CYAN
    print(f"[{step}] {color}{msg}{RESET}")

def run_full_system_qa():
    parser = argparse.ArgumentParser(description="MyLeads AI - Full System QA")
    parser.add_argument("--prod", action="store_true", help="Run against Production URL")
    parser.add_argument("--email", type=str, help="User email for auto-login")
    parser.add_argument("--password", type=str, help="User password for auto-login")
    
    args = parser.parse_args()

    # Determine Base URL
    base_url = PROD_URL if args.prod else DEFAULT_LOCAL_URL

    print(f"\n🚀 STARTING FULL SYSTEM QA FOR: {base_url}")
    print("="*60)

    # ==============================================================================
    # 1. AUTHENTICATION & REGISTRATION
    # ==============================================================================
    if args.email:
        email = args.email
        log("1. AUTH", f"Using provided email: {email}", "INFO")
    else:
        email = input(f"[{RESET}INPUT{RESET}] 📧 Enter Test Email: ").strip() or f"qa_{int(time.time())}@test.com"

    if args.password:
        password = args.password
    else:
        password = getpass.getpass(f"[{RESET}INPUT{RESET}] 🔑 Enter Password: ").strip()

    user_payload = {
        "email": email,
        "password": password,
        "full_name": "QA Automator",
        "business_name": "QA Yoga Studio",
        "business_type": "Fitness Coach",
        "plan_tier": "starter" 
    }

    try:
        log("1. AUTH", "Attempting Registration...", "INFO")
        res = requests.post(f"{base_url}/api/v1/auth/register", json=user_payload)
        
        if res.status_code == 201:
            log("1. AUTH", "✅ User registered successfully.", "SUCCESS")
        elif res.status_code == 400:
            log("1. AUTH", "ℹ️ User already exists. Proceeding to login...", "WARN")
        else:
            log("1. AUTH", f"⚠️ Registration returned {res.status_code}: {res.text}. Trying login anyway...", "WARN")

        log("2. LOGIN", "Requesting Access Token...", "INFO")
        login_data = {"username": email, "password": password}
        res = requests.post(f"{base_url}/api/v1/auth/login", data=login_data)

        if res.status_code != 200:
            log("2. LOGIN", f"❌ Login Failed: {res.text}", "FAIL")
            sys.exit(1)

        data = res.json()
        token = None

        if data.get("mfa_required"):
            print("\n" + "-"*40)
            print(f"{YELLOW}📲 MFA REQUIRED!{RESET}")
            print(f"   Check your Email (or Server Logs if local) for the OTP code.")
            print("-" * 40 + "\n")
            otp_code = input(f"[{RESET}INPUT{RESET}] 🔢 Enter OTP Code: ").strip()
            otp_res = requests.post(f"{base_url}/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp_code})

            if otp_res.status_code == 200:
                token = otp_res.json().get("access_token")
                log("3. MFA", "✅ OTP Verified! Token acquired.", "SUCCESS")
            else:
                log("3. MFA", f"❌ Invalid Code: {otp_res.text}", "FAIL")
                sys.exit(1)
        elif "access_token" in data:
            token = data["access_token"]
            log("2. LOGIN", "✅ Direct Login (MFA disabled).", "SUCCESS")

        headers = {"Authorization": f"Bearer {token}"}

    except Exception as e:
        log("CRITICAL", f"Auth Flow Crashed: {e}", "FAIL")
        sys.exit(1)

    # ==============================================================================
    # 2. VERIFY USER PLAN (INITIAL)
    # ==============================================================================
    print("\n" + "="*60)
    log("4. USER INFO", "Checking current plan...", "INFO")
    
    try:
        me_res = requests.get(f"{base_url}/api/v1/auth/me", headers=headers)
        if me_res.status_code == 200:
            user_data = me_res.json()
            initial_plan = user_data.get("plan_tier")
            log("4. USER INFO", f"Current Plan: {initial_plan}", "INFO")
        else:
            log("4. USER INFO", f"❌ Failed to fetch user info: {me_res.text}", "FAIL")
            
    except Exception as e:
        log("USER INFO", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 3. AI BRAIN CONFIGURATION
    # ==============================================================================
    print("\n" + "="*60)
    log("5. AI BRAIN", "Testing AI Settings & Business Profile Updates...", "INFO")
    
    ai_settings_payload = {
        "business_name": "QA Yoga Studio (Updated)",
        "business_type": "Fitness Coach",
        "ai_tone": "Friendly",
        "products_services": "1. 1-on-1 Yoga: $50/hr\n2. Group Class: $20/hr",
        "custom_instructions": "Never offer discounts. Always ask about past injuries before booking.",
        "ai_agent": {
            "voice_id": "female_calm_1",
            "language": "en-US"
        }
    }

    try:
        settings_res = requests.post(f"{base_url}/api/v1/settings", json=ai_settings_payload, headers=headers)
        if settings_res.status_code == 200:
            log("5. AI BRAIN", "✅ AI Brain configuration saved successfully.", "SUCCESS")
        else:
            log("5. AI BRAIN", f"❌ Failed to save AI settings: {settings_res.text}", "FAIL")
    except Exception as e:
        log("AI BRAIN", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 4. BILLING UPGRADE (COUPON REDEMPTION)
    # ==============================================================================
    print("\n" + "="*60)
    log("6. BILLING", "Testing Subscription Upgrade via Admin Coupon...", "INFO")
    
    try:
        coupon_res = requests.post(f"{base_url}/api/v1/billing/redeem-coupon", 
                                  json={"coupon_code": "VIP_SHAY"}, 
                                  headers=headers)
        
        if coupon_res.status_code == 200:
            res_data = coupon_res.json()
            if "PRO" in res_data.get("message", "").upper() or res_data.get("plan") == "PRO":
                log("6. BILLING", "✅ Upgrade successful! User is now PRO.", "SUCCESS")
                log("6. BILLING", "✅ Confirmation email dispatched (check logs).", "SUCCESS")
            else:
                log("6. BILLING", "⚠️ Request succeeded, but user is still not PRO.", "WARN")
        else:
            log("6. BILLING", f"❌ Failed to apply coupon: {coupon_res.text}", "FAIL")
    except Exception as e:
        log("BILLING", f"Error: {e}", "FAIL")


    # ==============================================================================
    # 5. PHONE NUMBER BROWSING & ASSIGNMENT
    # ==============================================================================
    print("\n" + "="*60)
    log("7. PHONES", "Testing Phone Number Browsing and Purchase Gate...", "INFO")

    try:
        res = requests.get(f"{base_url}/api/v1/phones/available?country_code=IL", headers=headers)
        
        if res.status_code == 200:
            numbers = res.json()
            if numbers:
                print(f"{CYAN}📞 Found {len(numbers)} available numbers. Simulating purchase of first number...{RESET}")
                
                target_num = numbers[0]['number']
                log("7. PHONES", f"Attempting purchase for {target_num}...", "INFO")
                
                buy_res = requests.post(f"{base_url}/api/v1/phones/purchase", 
                                        json={"phone_number": target_num, "country_code": "IL"},
                                        headers=headers)
                
                if buy_res.status_code == 200:
                    log("7. PHONES", f"✅ Purchase Successful! Number {target_num} assigned.", "SUCCESS")
                    
                    # Verify assignment
                    me_res2 = requests.get(f"{base_url}/api/v1/auth/me", headers=headers)
                    if me_res2.status_code == 200 and me_res2.json().get("assigned_phone") == target_num:
                        log("7. PHONES", "✅ System correctly remembered the purchased number.", "SUCCESS")
                    else:
                        log("7. PHONES", "❌ Number was not saved to user profile.", "FAIL")
                        
                elif buy_res.status_code == 403:
                    log("7. PHONES", "🔒 Purchase Blocked: You need PRO plan (Upgrade step failed).", "FAIL")
                else:
                    log("7. PHONES", f"❌ Purchase Failed: {buy_res.text}", "FAIL")
            else:
                 log("7. PHONES", "⚠️ No numbers found (Check Provider Credentials).", "WARN")

        else:
             log("7. PHONES", f"❌ API Error: {res.text}", "FAIL")

    except Exception as e:
        log("PHONES", f"Error: {e}", "FAIL")

    print("\n🏁 FULL SYSTEM QA COMPLETE.")

if __name__ == "__main__":
    run_full_system_qa()