import requests
import sys
import getpass
import argparse
import time
import json

# --- CONFIGURATION ---
DEFAULT_LOCAL_URL = "http://127.0.0.1:8000"
PROD_URL = "https://my-leads.app" # Ensure this matches your Cloudflare domain

# --- COLORS ---
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def log(step, msg, status="INFO"):
    """Helper for formatted logging."""
    color = RESET
    if status == "SUCCESS": color = GREEN
    elif status == "FAIL": color = RED
    elif status == "WARN": color = YELLOW
    elif status == "INPUT": color = CYAN
    
    print(f"[{step}] {color}{msg}{RESET}")

def run_full_system_qa():
    parser = argparse.ArgumentParser(description="LeadFlow AI - Full System QA")
    parser.add_argument("--prod", action="store_true", help="Run against Production URL")
    args = parser.parse_args()

    base_url = PROD_URL if args.prod else DEFAULT_LOCAL_URL

    print(f"\n🚀 STARTING FULL SYSTEM QA FOR: {base_url}")
    print("="*60)

    # ==============================================================================
    # 1. AUTHENTICATION & REGISTRATION
    # ==============================================================================
    email = input(f"[{RESET}INPUT{RESET}] 📧 Enter Test Email (default: qa@test.com): ").strip() or "qa@test.com"
    password = getpass.getpass(f"[{RESET}INPUT{RESET}] 🔑 Enter Password: ").strip()

    log("1. AUTH", f"Attempting to register {email}...", "INFO")
    
    user_payload = {
        "email": email,
        "password": password,
        "full_name": "QA Automator",
        "business_name": "QA Yoga Studio",
        "business_type": "Fitness Coach",
        "plan_tier": "start" # Default free plan
    }

    try:
        # A. Register
        res = requests.post(f"{base_url}/api/v1/auth/register", json=user_payload)
        if res.status_code == 201:
            log("1. AUTH", "✅ User registered successfully.", "SUCCESS")
        elif res.status_code == 400:
            log("1. AUTH", "ℹ️ User already exists. Proceeding to login.", "WARN")
        else:
            log("1. AUTH", f"❌ Registration failed: {res.text}", "FAIL")
            sys.exit(1)

        # B. Login
        log("2. LOGIN", "Requesting Access Token...", "INFO")
        res = requests.post(f"{base_url}/api/v1/auth/login", json={
            "email": email, # Note: Backend expects 'email', not 'username' in JSON body mostly
            "password": password
        })
        
        # Fallback for OAuth2 form data if JSON fails
        if res.status_code != 200:
             res = requests.post(f"{base_url}/api/v1/auth/login", data={
                "username": email,
                "password": password
            })

        if res.status_code != 200:
            log("2. LOGIN", f"❌ Login Failed: {res.text}", "FAIL")
            sys.exit(1)

        data = res.json()
        token = None

        # C. MFA Handling
        if data.get("mfa_required"):
            print("\n" + "-"*40)
            print(f"{YELLOW}📲 MFA REQUIRED!{RESET}")
            if not args.prod:
                print("👉 LOCAL: Check your terminal logs for the 6-digit code.")
            else:
                print("👉 PROD: Check your Email (if configured) or Server Logs via SSH.")
            print("-" * 40 + "\n")

            otp_code = input(f"[{RESET}INPUT{RESET}] 🔢 Enter OTP Code: ").strip()

            otp_res = requests.post(f"{base_url}/api/v1/auth/verify-otp", json={
                "email": email,
                "otp_code": otp_code
            })

            if otp_res.status_code == 200:
                token = otp_res.json().get("access_token")
                log("3. MFA", "✅ OTP Verified! Token acquired.", "SUCCESS")
            else:
                log("3. MFA", f"❌ Invalid Code: {otp_res.text}", "FAIL")
                sys.exit(1)
        
        elif "access_token" in data:
            token = data["access_token"]
            log("2. LOGIN", "✅ Direct Login (MFA disabled).", "SUCCESS")

        # Set Headers for subsequent requests
        headers = {"Authorization": f"Bearer {token}"}

    except Exception as e:
        log("CRITICAL", f"Auth Flow Crashed: {e}", "FAIL")
        sys.exit(1)

    # ==============================================================================
    # 2. PAYMENTS & PLANS
    # ==============================================================================
    try:
        log("4. PAYMENTS", "Attempting to redeem 'LAUNCH2026' coupon...", "INFO")
        res = requests.post(
            f"{base_url}/api/v1/payments/redeem-coupon",
            json={"coupon_code": "LAUNCH2026"},
            headers=headers
        )

        if res.status_code == 200:
            log("4. PAYMENTS", "✅ Coupon applied! Plan upgraded.", "SUCCESS")
        elif "already used" in res.text.lower():
            log("4. PAYMENTS", "ℹ️ Coupon already used (Expected).", "WARN")
        else:
            log("4. PAYMENTS", f"❌ Coupon failed: {res.text}", "FAIL")

        # Verify Plan via /me endpoint
        res = requests.get(f"{base_url}/api/v1/auth/me", headers=headers)
        user_info = res.json()
        plan = user_info.get("plan_tier", "unknown")
        
        if plan in ["PRO", "premium"]:
            log("5. PLAN CHECK", f"✅ User is on tier: {plan}", "SUCCESS")
        else:
            log("5. PLAN CHECK", f"⚠️ User is on tier: {plan} (Expected 'PRO' after coupon)", "WARN")

    except Exception as e:
        log("PAYMENTS", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 3. SETTINGS & AI PERSONA
    # ==============================================================================
    try:
        log("6. SETTINGS", "Updating AI Persona...", "INFO")
        settings_payload = {
            "business_name": "QA Yoga & Pilates",
            "business_type": "Yoga Instructor",
            "ai_tone": "Friendly",
            "products_services": "Yoga Class: $20, Private: $100"
        }
        
        res = requests.post(f"{base_url}/api/v1/settings/", json=settings_payload, headers=headers)
        
        if res.status_code == 200:
            log("6. SETTINGS", "✅ AI Persona updated successfully.", "SUCCESS")
        else:
            log("6. SETTINGS", f"❌ Update failed: {res.text}", "FAIL")

    except Exception as e:
        log("SETTINGS", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 4. PHONE NUMBER AVAILABILITY
    # ==============================================================================
    try:
        log("7. PHONES", "Checking available numbers (US)...", "INFO")
        res = requests.get(f"{base_url}/api/v1/phones/available?country_code=US", headers=headers)
        
        if res.status_code == 200:
            numbers = res.json()
            log("7. PHONES", f"✅ Success! Found {len(numbers)} numbers.", "SUCCESS")
        elif res.status_code == 403:
            log("7. PHONES", "❌ Access Denied (Plan requirements not met).", "FAIL")
        else:
            log("7. PHONES", f"⚠️ Provider Error: {res.text}", "WARN")

    except Exception as e:
        log("PHONES", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 5. AI WEBHOOK SIMULATION (The "Brain" Test)
    # ==============================================================================
    print("\n" + "-"*60)
    log("8. AI BRAIN", "Simulating Incoming WhatsApp Message (Webhook)...", "INFO")
    
    # Simulate Form Data sent by Twilio
    webhook_payload = {
        "From": "whatsapp:+972501234567",
        "Body": "Hi, I want to book a yoga class for tomorrow morning.",
        "NumMedia": "0"
    }
    
    try:
        res = requests.post(f"{base_url}/webhooks/whatsapp/twilio", data=webhook_payload)
        
        if res.status_code == 200:
            log("8. AI BRAIN", "✅ Webhook accepted (200 OK).", "SUCCESS")
            
            # Check for TwiML (Twilio Markup XML) in response
            if "<Response>" in res.text:
                log("8. AI BRAIN", "✅ TwiML Response detected.", "SUCCESS")
                print(f"   🤖 Bot Reply (Raw): {res.text[:100]}...")
            else:
                log("8. AI BRAIN", f"⚠️ Unexpected response format: {res.text}", "WARN")
        else:
            log("8. AI BRAIN", f"❌ Webhook failed: {res.status_code}", "FAIL")

    except Exception as e:
        log("AI BRAIN", f"Error: {e}", "FAIL")

    # ==============================================================================
    # 6. AUDIO PIPELINE CHECK (Instructions)
    # ==============================================================================
    print("\n" + "="*60)
    print(f"{CYAN}ℹ️  AUDIO & PDF PIPELINE TEST INSTRUCTIONS{RESET}")
    print("   To test the Whisper/PDF flow, follow these manual steps:")
    print("   1. Open WhatsApp.")
    print("   2. Send a VOICE NOTE to the bot's number.")
    print("   3. Wait ~30 seconds.")
    print("   4. Check the Admin Email (configured in .env) for a PDF receipt.")
    print("="*60)
    print("\n🏁 FULL SYSTEM QA COMPLETE.")

if __name__ == "__main__":
    run_full_system_qa()