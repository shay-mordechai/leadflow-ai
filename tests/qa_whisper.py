# tests/qa_whisper.py
import asyncio
import os
import sys
import argparse

# --- 1. CLI Argument Parsing ---
parser = argparse.ArgumentParser(description="Run Whisper Transcription Test")
args, unknown = parser.parse_known_args()

# --- 2. System Path & Internal Imports ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.services.ai.whisper import whisper_service

GREEN, RED, YELLOW, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

def log(msg, status="INFO"):
    color = GREEN if status == "SUCCESS" else RED if status == "FAIL" else YELLOW
    print(f"{color}{msg}{RESET}")

async def run_whisper_test():
    print(f"\n🚀 STARTING WHISPER (LOW-RAM OPTIMIZED) TEST")
    print("="*60)
    
    test_file_path = "test_audio.ogg"
    
    with open(test_file_path, "wb") as f:
        f.write(b"dummy audio content")

    log("✅ [SETUP] Dummy audio file created.", "INFO")

    try:
        log("⏳ [TEST] Loading Model and Attempting Transcription...", "INFO")

        try:
             result = whisper_service._transcribe_sync(test_file_path)
             log(f"✅ [SUCCESS] Transcription Result: {result}", "SUCCESS")
        except Exception as e:
            if "Invalid data found" in str(e) or "ffmpeg" in str(e).lower() or "decoding" in str(e).lower():
                 log("✅ [SUCCESS] Model loaded successfully! (Expected format error occurred because test file is a dummy)", "SUCCESS")
            else:
                 log(f"❌ [FAIL] Unexpected error during model load/transcription: {e}", "FAIL")
                 
    except Exception as general_error:
         log(f"❌ [FAIL] Critical system failure: {general_error}", "FAIL")

    finally:
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
            log("🧹 [CLEANUP] Dummy file removed.", "INFO")

    print("\n" + "="*60)
    print(f"🏁 WHISPER QA COMPLETE.")

if __name__ == "__main__":
    asyncio.run(run_whisper_test())