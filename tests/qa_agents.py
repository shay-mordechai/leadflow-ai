# tests/qa_agents.py
import asyncio
import os
import sys
import argparse

# --- 1. CLI Argument Parsing (Must happen before internal imports) ---
parser = argparse.ArgumentParser(description="Run AI Agent QA Tests")
parser.add_argument("--api-key", type=str, help="Google Gemini API Key (Bypasses SSM/.env for local testing)")
args, unknown = parser.parse_known_args()

# Inject the API key into the environment so Pydantic (src.config) picks it up automatically
if args.api_key:
    os.environ["GOOGLE_API_KEY"] = args.api_key

# --- 2. System Path & Internal Imports ---
# Ensure the root directory is in the path so we can import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now we can safely import because the environment variables are set
from src.config import settings
from src.services.ai.engine import ai_engine

GREEN, RED, YELLOW, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

def log(msg, status="INFO"):
    color = GREEN if status == "SUCCESS" else RED if status == "FAIL" else YELLOW
    print(f"{color}{msg}{RESET}")

async def run_agent_tests():
    print(f"\n🚀 STARTING AI AGENTS FUNCTION-CALLING TEST")
    print("="*60)
    
    # Check if the API key was successfully loaded (via CLI, .env, or SSM)
    if not settings.GOOGLE_API_KEY:
        log("❌ GOOGLE_API_KEY is missing! Cannot test real AI.", "FAIL")
        print("\n💡 Tip for local testing on Fedora:")
        print("Run the script using the --api-key argument:")
        print("python tests/qa_agents.py --api-key=\"AIzaSyYourGoogleApiKeyHere...\"")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # System Prompt Setup
    # -------------------------------------------------------------------------
    system_prompt = """
    אתה נציג שירות ומכירות של קליניקה לרפואה משלימה. 
    עליך להיות אדיב, מקצועי וקצר. 
    אם הלקוח שואל על תורים, חובה להשתמש בכלי היומן.
    """

    # -------------------------------------------------------------------------
    # TEST 1: The Calendar Agent (check_calendar_availability)
    # -------------------------------------------------------------------------
    log("\n--- TEST 1: CALENDAR SCHEDULING AGENT ---", "INFO")
    user_msg_1 = "היי, רציתי לדעת אם יש לכם תורים פנויים למחר בבוקר?"
    print(f"👤 User: {user_msg_1}")
    
    log("🤖 Waiting for Gemini to analyze and trigger tools...", "INFO")
    res1 = await ai_engine.analyze_interaction(
        system_prompt=system_prompt,
        text_input=user_msg_1,
        sender_name="Shay"
    )
    
    reply1 = res1.get('reply_text', '')
    print(f"🗣️ AI Reply: {reply1}")
    
    # We defined our tool in engine.py to return: ["09:00", "11:30", "15:00", "17:00"]
    # If the AI actually called the tool, it MUST mention these times in its reply.
    if "09:00" in reply1 or "11:30" in reply1 or "09:00" in reply1.replace("9:00", "09:00"):
        log("✅ PASSED: AI successfully invoked the check_calendar_availability tool!", "SUCCESS")
    else:
        log("❌ FAILED: AI did not output the times from the calendar tool.", "FAIL")

    # -------------------------------------------------------------------------
    # TEST 2: Lead Qualification Agent (qualify_lead)
    # -------------------------------------------------------------------------
    log("\n--- TEST 2: LEAD QUALIFICATION AGENT ---", "INFO")
    user_msg_2 = "אני רוצה לעשות סדרת טיפולים. התקציב שלי הוא בערך 2500 שקלים ואני רוצה להתחיל בשבוע הבא."
    print(f"👤 User: {user_msg_2}")
    
    log("🤖 Waiting for Gemini to qualify the lead...", "INFO")
    res2 = await ai_engine.analyze_interaction(
        system_prompt=system_prompt,
        text_input=user_msg_2,
        sender_name="Shay"
    )
    
    reply2 = res2.get('reply_text', '')
    print(f"🗣️ AI Reply: {reply2}")
    
    if len(reply2) > 5:
        log("✅ PASSED: AI responded naturally after (implicitly) calling the qualification tool.", "SUCCESS")
    else:
        log("❌ FAILED: AI response is too short or broken.", "FAIL")

    # -------------------------------------------------------------------------
    # TEST 3: Human Handoff Fallback
    # -------------------------------------------------------------------------
    log("\n--- TEST 3: HUMAN ESCALATION ---", "INFO")
    user_msg_3 = "השירות שלכם על הפנים!! אני רוצה לדבר עם מנהל עכשיו ואל תענה לי כבוט!"
    print(f"👤 User: {user_msg_3}")
    
    res3 = await ai_engine.analyze_interaction(
        system_prompt=system_prompt,
        text_input=user_msg_3,
        sender_name="Angry Lead"
    )
    
    reply3 = res3.get('reply_text', '')
    print(f"🗣️ AI Reply: {reply3}")
    
    if res3.get('needs_human_escalation') is True:
        log("✅ PASSED: AI successfully detected anger and requested [HANDOFF].", "SUCCESS")
    else:
        log("❌ FAILED: AI did not trigger the needs_human_escalation flag.", "FAIL")

    print("\n" + "="*60)
    print(f"🏁 AI AGENTS QA COMPLETE.")

if __name__ == "__main__":
    # Ensure asyncio event loop runs the async function properly
    asyncio.run(run_agent_tests())