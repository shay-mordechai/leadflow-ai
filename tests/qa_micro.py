# tests/qa_micro.py
import requests, sys, argparse, time, io
from requests.exceptions import Timeout

DEFAULT_LOCAL_URL = "http://127.0.0.1:8000"
PROD_URL = "https://my-leads.app" 
REQ_TIMEOUT = 15

GREEN, RED, YELLOW, CYAN, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m"

def log(step, msg, status="INFO"):
    color = GREEN if status == "SUCCESS" else RED if status == "FAIL" else YELLOW if status == "WARN" else CYAN if status == "INPUT" else RESET
    print(f"[{step}] {color}{msg}{RESET}")

def run_micro_qa():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true")
    args = parser.parse_args()
    base_url = PROD_URL if args.prod else DEFAULT_LOCAL_URL

    print(f"\n🔬 STARTING MICRO QA (ADVANCED FEATURES) FOR: {base_url}\n" + "="*60)
    email = f"micro_{int(time.time())}@test.com"
    password = "YourPassword123!"

    # Quick Setup (Auth & PRO Upgrade)
    requests.post(f"{base_url}/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Micro QA", "business_name": "Micro Biz", "plan_tier": "starter"})
    requests.post(f"{base_url}/api/v1/auth/login", data={"username": email, "password": password})
    otp_code = input(f"[{RESET}INPUT{RESET}] 🔢 Enter OTP Code (Check Logs): ").strip()
    token = requests.post(f"{base_url}/api/v1/auth/verify-otp", json={"email": email, "otp_code": otp_code}).json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    requests.post(f"{base_url}/api/v1/billing/redeem-coupon", json={"coupon_code": "VIP_SHAY"}, headers=headers)
    user_id = requests.get(f"{base_url}/api/v1/auth/me", headers=headers).json().get("id")

    # 1. REGIONAL PHONE SCAN
    log("1. REGIONAL", "Testing Area Code Filtering (Target: '03')...", "INFO")
    res = requests.get(f"{base_url}/api/v1/phones/available?country_code=IL&area_code=03", headers=headers)
    if res.status_code == 200 and len(res.json()) > 0:
        log("1. REGIONAL", f"✅ Found {len(res.json())} numbers matching 03.", "SUCCESS")
    else:
        log("1. REGIONAL", "❌ Failed to find 03 numbers or API error.", "FAIL")

    # 2. CONVERSATIONAL MEMORY (TWILIO INBOUND)
    log("2. MEMORY", "Simulating inbound WhatsApp message (Checking AI Brain & Memory)...", "INFO")
    wa_payload = {"From": "whatsapp:+972501234567", "To": "whatsapp:+97233829709", "Body": "שלום, כמה עולה שיעור?"}
    wa_res = requests.post(f"{base_url}/webhooks/twilio/sms", data=wa_payload)
    if wa_res.status_code == 200:
        log("2. MEMORY", "✅ Twilio Webhook accepted WhatsApp message. Check server logs for Gemini AI response.", "SUCCESS")
    else:
        log("2. MEMORY", f"❌ Webhook failed: {wa_res.text}", "FAIL")

    # 3. PRIVATE SESSION UPLOAD (FASTER-WHISPER)
    log("3. WHISPER", "Testing Private Audio Upload (Local Transcription)...", "INFO")
    # Inject a dummy lead to attach the audio to
    test_phone = f"+97250{int(time.time())}"[:13]
    requests.post(f"{base_url}/api/v1/leads/webhook/{user_id}", json={"name": "Audio Lead", "phone": test_phone, "source": "manual"})
    leads = requests.get(f"{base_url}/api/v1/leads", headers=headers).json()
    
    if leads:
        target_lead = leads[0]['id']
        # Create a tiny 44-byte dummy WAV file in memory
        audio_file = io.BytesIO(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
        files = {'file': ('test_session.wav', audio_file, 'audio/wav')}
        up_res = requests.post(f"{base_url}/api/v1/sessions/upload/{target_lead}", headers=headers, files=files)
        
        if up_res.status_code == 200:
            log("3. WHISPER", "✅ Audio uploaded. Transcription queued on EC2! (Check podman logs to see Whisper in action)", "SUCCESS")
        else:
            log("3. WHISPER", f"❌ Upload failed: {up_res.text}", "FAIL")
    else:
        log("3. WHISPER", "❌ Could not find a lead to attach audio to.", "FAIL")

    print("\n🏁 MICRO QA COMPLETE.\n")

if __name__ == "__main__":
    run_micro_qa()