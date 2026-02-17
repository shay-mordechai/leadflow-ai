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
    parser = argparse.ArgumentParser(description="LeadFlow AI - Full System QA")
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
        email = input(f"[{RESET}INPUT{RESET}] 📧 Enter Test Email: ").strip() or "qa@test.com"

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
    # 2. VERIFY USER PLAN
    # ==============================================================================
    print("\n" + "="*60)
    log("4. USER INFO", "Checking current plan...", "INFO")
    
    try:
        me_res = requests.get(f"{base_url}/api/v1/auth/me", headers=headers)
        if me_res.status_code == 200:
            user_data = me_res.json()
            plan = user_data.get("plan_tier")
            log("4. USER INFO", f"Current Plan: {plan}", "INFO")
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
        # FIX: Removed the trailing slash here!
        settings_res = requests.post(f"{base_url}/api/v1/settings", json=ai_settings_payload, headers=headers)
        if settings_res.status_code == 200:
            log("5. AI BRAIN", "✅ AI Brain configuration saved successfully.", "SUCCESS")
            
            # Verify it was saved by fetching it back
            get_settings_res = requests.get(f"{base_url}/api/v1/settings", headers=headers)
            if get_settings_res.status_code == 200:
                saved_data = get_settings_res.json()
                if saved_data.get("custom_instructions") == ai_settings_payload["custom_instructions"]:
                     log("5. AI BRAIN", "✅ Data consistency verified in Database.", "SUCCESS")
                else:
                     log("5. AI BRAIN", "⚠️ Data saved but fetched data does not match payload.", "WARN")
        else:
            log("5. AI BRAIN", f"❌ Failed to save AI settings: {settings_res.text}", "FAIL")
            
    except Exception as e:
        log("AI BRAIN", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 4. PHONE NUMBER BROWSING (PRO FEATURE)
    # ==============================================================================
    print("\n" + "="*60)
    log("6. PHONES", "Browsing available numbers...", "INFO")

    try:
        res = requests.get(f"{base_url}/api/v1/phones/available?country_code=IL", headers=headers)
        
        if res.status_code == 200:
            numbers = res.json()
            if numbers:
                israeli_nums = [n for n in numbers if n['number'].startswith('+972')]
                foreign_nums = [n for n in numbers if not n['number'].startswith('+972')]

                print(f"\n{CYAN}📞 RESULTS SUMMARY:{RESET}")
                print(f"   🇮🇱 Israeli Numbers Found: {len(israeli_nums)}")
                print(f"   🌎 Foreign Numbers Found: {len(foreign_nums)}")
                print("-" * 30)

                print(f"{CYAN}📞 SHOWING TOP RESULTS:{RESET}")
                for idx, num in enumerate(numbers[:20]):
                    prefix = "🇮🇱" if num['number'].startswith('+972') else "🌎"
                    print(f"   [{idx+1}] {prefix} {num['number']} | {num['provider']} | {num['price_monthly']} USD")
                
                print("\n")
                choice = input(f"[{RESET}INPUT{RESET}] Simulate Purchase (Will check Plan)? (y/N): ").lower()
                if choice == 'y':
                    target_num = numbers[0]['number']
                    log("6. PHONES", f"Attempting purchase for {target_num}...", "INFO")
                    buy_res = requests.post(f"{base_url}/api/v1/phones/purchase", 
                                            json={"phone_number": target_num, "country_code": "IL"},
                                            headers=headers)
                    
                    if buy_res.status_code == 200:
                        log("6. PHONES", "✅ Purchase Successful!", "SUCCESS")
                    elif buy_res.status_code == 403:
                        log("6. PHONES", "🔒 Purchase Blocked: You need PRO plan (Expected for Starter users).", "WARN")
                    else:
                        log("6. PHONES", f"❌ Purchase Failed: {buy_res.text}", "FAIL")
            else:
                 log("6. PHONES", "⚠️ No numbers found (Check Provider Credentials).", "WARN")

        elif res.status_code == 403:
             log("6. PHONES", "🔒 Access Denied: Phone browsing restricted to PRO plan.", "WARN")
        else:
             log("6. PHONES", f"❌ API Error: {res.text}", "FAIL")

    except Exception as e:
        log("PHONES", f"Error: {e}", "FAIL")

    print("\n🏁 FULL SYSTEM QA COMPLETE.")

if __name__ == "__main__":
    run_full_system_qa()