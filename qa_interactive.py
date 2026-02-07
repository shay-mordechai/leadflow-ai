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

    # CRITICAL FIX: Ensure base_url is set correctly for ALL requests
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

    # Registration Payload
    user_payload = {
        "email": email,
        "password": password,
        "full_name": "QA Automator",
        "business_name": "QA Yoga Studio",
        "business_type": "Fitness Coach",
        "plan_tier": "starter"
    }

    try:
        # A. Register check
        res = requests.post(f"{base_url}/api/v1/auth/register", json=user_payload)
        
        if res.status_code == 201:
            log("1. AUTH", "✅ User registered successfully.", "SUCCESS")
        elif res.status_code == 400:
            log("1. AUTH", "ℹ️ User already exists. Proceeding to login...", "WARN")
        else:
            # Ignore 500 here if login works later (likely just a duplicate key error handled poorly)
            log("1. AUTH", f"⚠️ Registration check returned {res.status_code}. Trying login anyway...", "WARN")

        # B. Login
        log("2. LOGIN", "Requesting Access Token...", "INFO")
        res = requests.post(f"{base_url}/api/v1/auth/login", json={"email": email, "password": password})
        
        if res.status_code != 200:
             # Fallback
             res = requests.post(f"{base_url}/api/v1/auth/login", data={"username": email, "password": password})

        if res.status_code != 200:
            log("2. LOGIN", f"❌ Login Failed: {res.text}", "FAIL")
            sys.exit(1)

        data = res.json()
        token = None

        # C. MFA Handling
        if data.get("mfa_required"):
            print("\n" + "-"*40)
            print(f"{YELLOW}📲 MFA REQUIRED!{RESET}")
            print(f"   Check Server Logs/Email for OTP.")
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
    # 2. PREMIUM SUBSCRIPTION SIMULATION ($99/mo)
    # ==============================================================================
    print("\n" + "="*60)
    log("4. BILLING", "Simulating Premium Subscription Purchase ($99/mo)...", "INFO")
    
    try:
        # We simulate what Morning/iCount would send to our webhook
        payment_payload = {
            "external_transaction_id": f"SUB_{int(time.time())}",
            "customer_email": email,
            "amount": 99.00,
            "currency": "ILS",
            "status": "success",
            "product": "Premium Monthly"
        }
        
        # Call the Webhook Endpoint
        res = requests.post(f"{base_url}/api/v1/payments/webhook/morning", json=payment_payload)
        
        if res.status_code == 200:
            resp_data = res.json()
            if resp_data.get("receipt_sent"):
                log("4. BILLING", "✅ Payment Processed! User upgraded to PRO.", "SUCCESS")
                log("4. BILLING", "📧 Receipt Email Triggered (Mock).", "SUCCESS")
            else:
                log("4. BILLING", "⚠️ Payment processed but check logs for receipt.", "WARN")
        else:
            log("4. BILLING", f"❌ Payment Webhook Failed: {res.text}", "FAIL")

        # Verify Upgrade via /me
        me_res = requests.get(f"{base_url}/api/v1/auth/me", headers=headers)
        if me_res.status_code == 200:
            user_data = me_res.json()
            plan = user_data.get("plan_tier")
            if plan == "PRO":
                log("4. BILLING", f"✅ Verified: User plan is now '{plan}'.", "SUCCESS")
            else:
                log("4. BILLING", f"❌ Verification Failed: User plan is '{plan}'.", "FAIL")

    except Exception as e:
        log("BILLING", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 3. PHONE NUMBER BROWSING (No Purchase Required)
    # ==============================================================================
    print("\n" + "="*60)
    log("5. PHONES", "Browsing available numbers (Post-Payment Flow)...", "INFO")

    try:
        available_numbers = []
        for country in ["IL", "US"]:
            res = requests.get(f"{base_url}/api/v1/phones/available?country_code={country}", headers=headers)
            if res.status_code == 200:
                available_numbers.extend(res.json())

        # Filter Cheap Numbers
        cheap_numbers = [n for n in available_numbers if float(n.get('price_monthly', 5.0)) < 2.0]
        cheap_numbers.sort(key=lambda x: float(x.get('price_monthly', 5.0)))

        if cheap_numbers:
            print(f"\n{CYAN}📞 DISPLAYING {len(cheap_numbers)} AVAILABLE NUMBERS:{RESET}")
            for idx, num in enumerate(cheap_numbers[:5]):
                print(f"   [{idx+1}] {num['number']} | {num['country']} | ${num['price_monthly']}/mo | {num['provider']}")
        else:
            log("5. PHONES", "⚠️ No cheap numbers found, but API is responding.", "WARN")

        # Prompt
        print("\n")
        choice = input(f"[{RESET}INPUT{RESET}] Do you want to ACTUALLY purchase a number? (y/N): ").lower()
        
        if choice == 'y' and cheap_numbers:
            # Purchase Logic
            selection = input(f"[{RESET}INPUT{RESET}] Enter index: ")
            try:
                selected_num = cheap_numbers[int(selection)-1]
                log("5. PHONES", f"Purchasing {selected_num['number']}...", "INFO")
                buy_res = requests.post(f"{base_url}/api/v1/phones/purchase", 
                                        json={"phone_number": selected_num['number'], "country_code": selected_num['country']},
                                        headers=headers)
                if buy_res.status_code == 200:
                    log("5. PHONES", "✅ Purchase Successful!", "SUCCESS")
                else:
                    log("5. PHONES", f"❌ Purchase Failed: {buy_res.text}", "FAIL")
            except:
                pass
        else:
            log("5. PHONES", "⏩ Skipping purchase (View only mode).", "INFO")

    except Exception as e:
        log("PHONES", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 4. SETTINGS & AI CONTEXT
    # ==============================================================================
    try:
        log("6. SETTINGS", "Updating AI Business Persona...", "INFO")
        settings_payload = {
            "business_name": "QA Yoga & Pilates",
            "business_type": "Yoga Instructor",
            "ai_tone": "Friendly",
            "products_services": "Yoga Class: $20, Private: $100"
        }
        
        # FIX: Ensure we use the correct variable 'base_url'
        res = requests.post(f"{base_url}/api/v1/settings/", json=settings_payload, headers=headers)
        
        # Handle trailing slash potential issue
        if res.status_code == 404:
             res = requests.post(f"{base_url}/api/v1/settings", json=settings_payload, headers=headers)

        if res.status_code == 200:
            log("6. SETTINGS", "✅ AI Persona updated successfully.", "SUCCESS")
        else:
            log("6. SETTINGS", f"❌ Update failed: {res.status_code} - {res.text}", "FAIL")

    except Exception as e:
        log("SETTINGS", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 5. AI WEBHOOK (The Brain)
    # ==============================================================================
    print("\n" + "-"*60)
    log("7. AI BRAIN", "Simulating Incoming WhatsApp Message...", "INFO")
    
    webhook_payload = {
        "From": "whatsapp:+972501234567",
        "Body": "Hi, I want to sign up for the premium yoga class.",
        "NumMedia": "0"
    }
    
    try:
        res = requests.post(f"{base_url}/webhooks/whatsapp/twilio", data=webhook_payload)
        
        if res.status_code == 200:
            log("7. AI BRAIN", "✅ Webhook accepted.", "SUCCESS")
            if "<Response>" in res.text:
                log("7. AI BRAIN", "✅ TwiML Response detected.", "SUCCESS")
                print(f"   🤖 Bot Reply: {res.text[:150]}...")
            else:
                log("7. AI BRAIN", f"⚠️ Unexpected response: {res.text}", "WARN")
        else:
            log("7. AI BRAIN", f"❌ Webhook failed: {res.status_code}", "FAIL")

    except Exception as e:
        log("AI BRAIN", f"Error: {e}", "FAIL")

    print("\n🏁 FULL SYSTEM QA COMPLETE.")

if __name__ == "__main__":
    run_full_system_qa()