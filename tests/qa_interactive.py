import requests
import sys
import getpass
import argparse
import time
import json
import uuid

# --- CONFIGURATION ---
DEFAULT_LOCAL_URL = "http://127.0.0.1:8000"
PROD_URL = "https://my-leads.app" 
REQ_TIMEOUT = 15

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
    base_url = PROD_URL if args.prod else DEFAULT_LOCAL_URL

    print(f"\n🚀 STARTING FULL SYSTEM QA FOR: {base_url}")
    print("="*60)

    user_id = None
    token = None

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
        res = requests.post(f"{base_url}/api/v1/auth/register", json=user_payload, timeout=REQ_TIMEOUT)
        
        if res.status_code == 201:
            log("1. AUTH", "✅ User registered successfully.", "SUCCESS")
        elif res.status_code == 400:
            log("1. AUTH", "ℹ️ User already exists. Proceeding to login...", "WARN")
        else:
            log("1. AUTH", f"⚠️ Registration returned {res.status_code}: {res.text}. Trying login anyway...", "WARN")

        log("2. LOGIN", "Requesting Access Token...", "INFO")
        login_data = {"username": email, "password": password}
        res = requests.post(f"{base_url}/api/v1/auth/login", data=login_data, timeout=REQ_TIMEOUT)

        if res.status_code != 200:
            log("2. LOGIN", f"❌ Login Failed: {res.text}", "FAIL")
            sys.exit(1)

        data = res.json()

        if data.get("mfa_required"):
            print("\n" + "-"*40)
            print(f"{YELLOW}📲 MFA REQUIRED!{RESET}")
            print(f"   Check your Email (or Server Logs if local) for the OTP code.")
            print("-" * 40 + "\n")
            otp_code = input(f"[{RESET}INPUT{RESET}] 🔢 Enter OTP Code: ").strip()
            otp_res = requests.post(f"{base_url}/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp_code}, timeout=REQ_TIMEOUT)

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

    except requests.exceptions.Timeout:
        log("CRITICAL", "Auth Flow Timed Out. Server might be down.", "FAIL")
        sys.exit(1)
    except Exception as e:
        log("CRITICAL", f"Auth Flow Crashed: {e}", "FAIL")
        sys.exit(1)

    # ==============================================================================
    # 2. VERIFY USER PLAN (INITIAL) AND GET USER_ID
    # ==============================================================================
    print("\n" + "="*60)
    log("4. USER INFO", "Checking current plan...", "INFO")
    
    try:
        me_res = requests.get(f"{base_url}/api/v1/auth/me", headers=headers, timeout=REQ_TIMEOUT)
        if me_res.status_code == 200:
            user_data = me_res.json()
            initial_plan = user_data.get("plan_tier")
            user_id = user_data.get("id")
            log("4. USER INFO", f"Current Plan: {initial_plan}", "INFO")
            log("4. USER INFO", f"User ID: {user_id}", "INFO")
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
            "language": "he-IL"
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
            else:
                log("6. BILLING", "⚠️ Request succeeded, but user is still not PRO.", "WARN")
        else:
            log("6. BILLING", f"❌ Failed to apply coupon: {coupon_res.text}", "FAIL")
    except Exception as e:
        log("BILLING", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 5. PHONE NUMBER BROWSING & ASSIGNMENT (TESTING AREA CODE FILTER)
    # ==============================================================================
    print("\n" + "="*60)
    log("7. PHONES", "Testing Area Code Filtering (Target: '03' - Tel Aviv)...", "INFO")

    try:
        # We append area_code=03 to test the routing logic
        res = requests.get(f"{base_url}/api/v1/phones/available?country_code=IL&area_code=03", headers=headers)
        
        if res.status_code == 200:
            numbers = res.json()
            if numbers:
                log("7. PHONES", f"✅ Found {len(numbers)} total numbers matching filter.", "SUCCESS")
                
                print(f"\n{'#':<4} | {'Phone Number':<18} | {'Type':<15} | {'Provider':<10}")
                print("-" * 55)
                
                sorted_nums = sorted(numbers, key=lambda x: x.get('price_monthly', 1.0))[:10]
                
                for idx, num_data in enumerate(sorted_nums, 1):
                    phone = num_data.get('number', '')
                    provider = num_data.get('provider', 'Twilio') 
                    prefix_type = "Tel Aviv (03)" if "+9723" in phone else "Other/IL"
                    color = GREEN if "03" in prefix_type else RESET
                    
                    print(f"{idx:<4} | {color}{phone:<18}{RESET} | {prefix_type:<15} | {provider:<10}")
                
                print("-" * 55 + "\n")

                target_num = sorted_nums[0]['number']
                provider_to_buy = sorted_nums[0].get('provider', 'twilio')
                log("7. PHONES", f"Attempting test purchase for {target_num} via {provider_to_buy}...", "INFO")
                
                buy_res = requests.post(f"{base_url}/api/v1/phones/purchase", 
                                        json={
                                            "phone_number": target_num, 
                                            "country_code": "IL",
                                            "provider": provider_to_buy
                                        },
                                        headers=headers)
                
                if buy_res.status_code == 200 or "User already has a phone number" in buy_res.text:
                    log("7. PHONES", f"✅ Purchase Step Complete for {target_num}.", "SUCCESS")
                else:
                    log("7. PHONES", f"❌ Purchase Failed: {buy_res.text}", "FAIL")
            else:
                 log("7. PHONES", "🚨 DEBUG ALERT: Providers returned ZERO numbers for area code 03.", "FAIL")
        else:
             log("7. PHONES", f"❌ API Error: {res.text}", "FAIL")
    except Exception as e:
        log("PHONES", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 6. WEBHOOK & SPEED-TO-LEAD
    # ==============================================================================
    print("\n" + "="*60)
    log("8. WEBHOOK", "Simulating incoming lead from Facebook/Zapier...", "INFO")

    if not user_id:
        log("8. WEBHOOK", "❌ Cannot test webhook: Missing User ID.", "FAIL")
    else:
        test_phone_number = f"+97250{int(time.time())}"[:13] 
        
        webhook_payload = {
            "name": "David Facebook",
            "phone": test_phone_number,
            "email": "david@lead.com",
            "source": "facebook_ad"
        }

        try:
            webhook_res = requests.post(f"{base_url}/api/v1/leads/webhook/{user_id}", json=webhook_payload)
            
            if webhook_res.status_code in [200, 201]:
                log("8. WEBHOOK", f"✅ Webhook received lead successfully! (Phone: {test_phone_number})", "SUCCESS")
                log("8. WEBHOOK", "✅ Check server logs to see if 'Proactive WhatsApp message' was triggered.", "SUCCESS")
                
                leads_res = requests.get(f"{base_url}/api/v1/leads/", headers=headers)
                if leads_res.status_code == 200:
                    leads_data = leads_res.json()
                    found = any(lead.get("phone_number") == test_phone_number for lead in leads_data)
                    if found:
                        log("8. WEBHOOK", "✅ VERIFIED: Lead successfully appeared in User's Dashboard.", "SUCCESS")
                    else:
                        log("8. WEBHOOK", "❌ Lead saved by webhook, but not found in Dashboard.", "FAIL")
                else:
                     log("8. WEBHOOK", f"❌ Failed to fetch leads dashboard: {leads_res.text}", "FAIL")
            else:
                log("8. WEBHOOK", f"❌ Webhook Failed: {webhook_res.text}", "FAIL")

        except Exception as e:
            log("WEBHOOK", f"Error: {e}", "FAIL")

    print("\n🏁 FULL SYSTEM QA COMPLETE.")

if __name__ == "__main__":
    run_full_system_qa()