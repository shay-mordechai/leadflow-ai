import requests
import sys
import getpass
import argparse

# --- CONFIG ---
# ברירת מחדל: מקומי. אם תרצה פרודקשן תוסיף דגל.
DEFAULT_URL = "http://127.0.0.1:8000"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def log(step, msg, status="INFO"):
    color = RESET
    if status == "SUCCESS": color = GREEN
    elif status == "FAIL": color = RED
    elif status == "WARN": color = YELLOW
    elif status == "INPUT": color = "\033[96m"
    print(f"[{step}] {color}{msg}{RESET}")

def run_interactive_qa():
    # הוספת ארגומנטים לבחירת סביבה
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true", help="Run against Production URL")
    args = parser.parse_args()

    base_url = "https://my-leads.app" if args.prod else DEFAULT_URL

    print(f"\n🚀 STARTING INTERACTIVE QA FOR: {base_url}\n" + "="*50)

    # 1. Get User Credentials
    email = input("📧 Enter your Email: ").strip()
    if not email: email = "shay.test@example.com" # דיפולט נוח לבדיקות

    password = getpass.getpass("🔑 Enter your Password: ").strip()

    # 2. Register
    log("1. REGISTER", f"Checking if {email} needs registration...", "INFO")
    user_data = {
        "email": email,
        "password": password,
        "full_name": "QA Manual Tester",
        "business_name": "Real Studio",
        "business_type": "Yoga Instructor"
    }

    try:
        res = requests.post(f"{base_url}/api/v1/auth/register", json=user_data)
        if res.status_code == 201:
            log("1. REGISTER", "User created successfully", "SUCCESS")
        elif res.status_code == 400:
            log("1. REGISTER", "User already exists. Proceeding to login.", "WARN")
        else:
            log("1. REGISTER", f"Error: {res.text}", "FAIL")
            sys.exit(1)

        # 3. Login Request
        log("2. LOGIN", "Requesting Login...", "INFO")
        res = requests.post(f"{base_url}/api/v1/auth/login", data={
            "username": email,
            "password": password
        })

        if res.status_code != 200:
            log("2. LOGIN", f"Login Failed: {res.text}", "FAIL")
            sys.exit(1)

        data = res.json()
        token = None

        # 4. MFA Handling
        if data.get("mfa_required"):
            print("\n" + "-"*40)
            print("📲 MFA REQUIRED!")
            if not args.prod:
                print("👉 LOCAL: Check your terminal for the code")
            else:
                print("👉 PROD: Check the server logs via SSH")
            print("-" * 40 + "\n")

            otp_code = input(f"[{RESET}INPUT{RESET}] 🔢 Enter the 6-digit code: ").strip()

            otp_res = requests.post(f"{base_url}/api/v1/auth/verify-otp", json={
                "email": email,
                "otp_code": otp_code
            })

            if otp_res.status_code == 200:
                token = otp_res.json()["access_token"]
                log("3. MFA", "Code Accepted! Token acquired.", "SUCCESS")
            else:
                log("3. MFA", f"Code Rejected: {otp_res.text}", "FAIL")
                sys.exit(1)

        elif "access_token" in data:
            token = data["access_token"]
            log("2. LOGIN", "Direct Token acquired (No MFA)", "SUCCESS")

        headers = {"Authorization": f"Bearer {token}"}

        # 5. Redeem Coupon
        log("4. COUPON", "Applying 'LAUNCH2026'...")
        res = requests.post(
            f"{base_url}/api/v1/payments/redeem-coupon",
            json={"coupon_code": "LAUNCH2026"},
            headers=headers
        )
        if res.status_code == 200:
            log("4. COUPON", "Coupon accepted successfully", "SUCCESS")
        elif res.status_code == 400 and "already used" in res.text:
             log("4. COUPON", "Coupon already used (Expected for recurring test)", "WARN")
        else:
            log("4. COUPON", f"Coupon rejected: {res.text}", "FAIL")

        # 6. Verify DB Plan
        res = requests.get(f"{base_url}/api/v1/auth/me", headers=headers)
        new_plan = res.json().get("plan_type", "unknown")
        if new_plan == "premium":
            log("5. VERIFY DB", f"User is now '{new_plan}'! SUCCESS.", "SUCCESS")
        else:
            log("5. VERIFY DB", f"User is still '{new_plan}'. FAIL.", "FAIL")
            return

        # 7. Check Phone Access
        res = requests.get(f"{base_url}/api/v1/phones/available?country_code=US", headers=headers)
        if res.status_code == 200:
            count = len(res.json())
            log("6. PHONE ACCESS", f"Access Granted! Found {count} numbers.", "SUCCESS")
        elif res.status_code == 403:
            log("6. PHONE ACCESS", "Access Denied (403).", "FAIL")

        print("\n" + "="*50)
        print("🏁 QA COMPLETE")

    except Exception as e:
        log("CRITICAL", f"Script crashed: {str(e)}", "FAIL")

if __name__ == "__main__":
    run_interactive_qa()
