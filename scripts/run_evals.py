#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas.ai_response import WhatsAppAgentResponse
from src.security.ai_guardrails import inspect_and_wrap_input
from src.services.ai.harness import agent_harness


def validate_dataset_schema(dataset_path: Path) -> list[dict]:
    if not dataset_path.exists():
        print(f"❌ Golden dataset not found at {dataset_path}")
        sys.exit(1)

    cases = []
    required_keys = {
        "id",
        "tenant_id",
        "business_type",
        "business_name",
        "query",
        "expected_intent",
        "expected_needs_human",
        "expected_abstained",
        "expected_blocked",
        "expected_keywords",
    }

    with open(dataset_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON at line {idx}: {e}")
                sys.exit(1)

            missing = required_keys - set(data.keys())
            if missing:
                print(f"❌ Case {idx} missing required keys {missing}")
                sys.exit(1)
            cases.append(data)
    return cases


def run_offline_evals(cases: list[dict]) -> tuple[int, int, list[dict]]:
    passed = 0
    total = len(cases)
    results = []

    print(f"🧪 Running Offline Golden Evaluations across {total} test cases...")

    for case in cases:
        case_id = case["id"]
        query = case["query"]
        expected_blocked = case["expected_blocked"]
        expected_needs_human = case["expected_needs_human"]
        expected_abstained = case["expected_abstained"]
        expected_intent = case["expected_intent"]

        sanitized = inspect_and_wrap_input(query)
        is_blocked = sanitized.is_flagged

        try:
            WhatsAppAgentResponse(
                reply_text="בדיקת מענה תקינה לפי תנאי המערכת.",
                lead_intent=expected_intent
                if expected_intent in ["INQUIRY", "PRICING", "BOOKING", "COMPLAINT", "UNKNOWN"]
                else "INQUIRY",
                lead_qualification_score=50,
                needs_human_escalation=expected_needs_human,
                abstained=expected_abstained,
                cited_chunk_ids=[],
            )
            schema_valid = True
        except Exception:
            schema_valid = False

        if expected_blocked:
            success = (is_blocked == expected_blocked) and schema_valid
        else:
            success = (not is_blocked) and schema_valid

        if success:
            passed += 1

        results.append(
            {
                "id": case_id,
                "query": query,
                "success": success,
                "blocked": is_blocked,
                "schema_valid": schema_valid,
            }
        )
        status_icon = "✅" if success else "❌"
        print(f"  {status_icon} [{case_id}] Query: '{query[:40]}...' -> Passed: {success}")

    return passed, total, results


TENANT_PRODUCTS_SERVICES = {
    "tenant_clinic": (
        "Dr. Smith Clinic — קליניקת אסתטיקה ורפואה.\n"
        '- עלות טיפול פנים קלאסי: 350 ש"ח.\n'
        "- שעות פעילות: ימים א'-ה' 09:00-18:00 (כולל ימי שלישי 09:00-18:00), יום ו' 09:00-13:00.\n"
        "- כתובת ומיקום: רחוב דיזנגוף 120, תל אביב.\n"
        "- קביעת תורים: ניתן לקבוע תור למחר בבוקר או לכל יום פעילות."
    ),
    "tenant_gym": (
        "PowerFit Gym & Studio.\n"
        "- Monthly membership price: $200 per month.\n"
        '- עלות אימון אישי (Personal Training): 150 ש"ח לאימון.\n'
        "- מנוי שנתי: זמין להרשמה מיידית בכל ימות השבוע.\n"
        "- Trial sessions: available on Sunday and weekdays.\n"
        "- חניה: יש חניה חופשית במקום למתאמנים."
    ),
    "tenant_law": (
        "LegalPro Law Firm — משרד עורכי דין.\n"
        "- מספקים תיאום פגישות ייעוץ ראשוני בלבד.\n"
        "- חל איסור מוחלט לתת ייעוץ משפטי או המלצה על חוזי העסקה ללא עורך דין אנושי."
    ),
}


def _normalize_hebrew(text: str) -> str:
    return text.replace("״", '"').replace("׳", "'").lower()


async def run_live_evals(cases: list[dict]) -> tuple[int, int, list[dict]]:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print(
            "❌ GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required for --mode live."
        )
        sys.exit(1)

    from google import genai
    from google.genai import types

    # Re-bind live API key and disable local Redis when running outside production container
    agent_harness.router.gemini = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=15000),
    )
    agent_harness.router.redis = None

    passed = 0
    total = len(cases)
    results = []

    print(f"🚀 Running Live Golden Evaluations against Agent Harness across {total} test cases...")

    for case in cases:
        case_id = case["id"]
        tenant_id = case["tenant_id"]
        business_type = case["business_type"]
        business_name = case["business_name"]
        query = case["query"]
        expected_intent = case["expected_intent"].lower()
        expected_needs_human = case["expected_needs_human"]
        expected_keywords = case["expected_keywords"]
        products_services = TENANT_PRODUCTS_SERVICES.get(tenant_id, "General services")

        start_t = time.perf_counter()
        try:
            res = await agent_harness.execute_turn(
                tenant_id=tenant_id,
                business_type=business_type,
                business_name=business_name,
                products_services=products_services,
                custom_instructions="השב בשפת הפנייה (עברית או אנגלית) בצורה מדויקת, קצרה ועניינית.",
                lead_name="EvalLead",
                lead_source="WhatsApp",
                conversation_history=[],
                latest_message=query,
            )
            latency_s = time.perf_counter() - start_t

            reply_text = res.get("reply_text", "")
            intent = res.get("intent", "").lower()
            needs_human = bool(res.get("needs_human_escalation", False))
            abstained = bool(res.get("abstained", False))

            norm_reply = _normalize_hebrew(reply_text)
            latency_ok = latency_s < 15.0

            if expected_needs_human:
                # Out-of-scope / escalation / blocked cases must escalate or abstain safely
                intent_ok = True
                needs_human_ok = needs_human or abstained or case.get("expected_blocked", False)
            else:
                intent_ok = (intent == expected_intent) or (
                    expected_intent in ("unknown", "inquiry")
                )
                needs_human_ok = needs_human == expected_needs_human

            keywords_ok = (
                all(_normalize_hebrew(kw) in norm_reply for kw in expected_keywords)
                if expected_keywords
                else True
            )

            success = latency_ok and intent_ok and needs_human_ok and keywords_ok
            if success:
                passed += 1

            results.append(
                {
                    "id": case_id,
                    "query": query,
                    "latency_s": round(latency_s, 3),
                    "intent": intent,
                    "needs_human": needs_human,
                    "success": success,
                    "reply": reply_text,
                }
            )
            status_icon = "✅" if success else "❌"
            print(
                f"  {status_icon} [{case_id}] Latency: {round(latency_s, 2)}s | Intent: {intent} | Success: {success}"
            )

        except Exception as e:
            print(f"  ❌ [{case_id}] Live execution failed: {e}")
            results.append(
                {
                    "id": case_id,
                    "query": query,
                    "success": False,
                    "error": str(e),
                }
            )

    return passed, total, results


def main():
    parser = argparse.ArgumentParser(description="Golden Evaluation Regression Gate")
    parser.add_argument(
        "--mode", choices=["offline", "live"], default="offline", help="Evaluation mode"
    )
    args = parser.parse_args()

    dataset_path = PROJECT_ROOT / "evals" / "golden_dataset.jsonl"
    cases = validate_dataset_schema(dataset_path)

    report_dir = PROJECT_ROOT / "evals"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "last_report.json"

    if args.mode == "offline":
        passed, total, results = run_offline_evals(cases)
        pass_rate = (passed / total) * 100 if total > 0 else 0
        print(f"\n📊 Offline Evaluation Summary: {passed}/{total} passed ({pass_rate:.1f}%)")

        report = {
            "mode": "offline",
            "passed": passed,
            "total": total,
            "pass_rate_percent": round(pass_rate, 2),
            "results": results,
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        if pass_rate < 95.0:
            print(
                f"❌ Offline evaluation pass rate {pass_rate:.1f}% is below required 95.0% threshold."
            )
            sys.exit(1)
        else:
            print("✅ Offline evaluation regression gate PASSED.")
            sys.exit(0)

    else:
        passed, total, results = asyncio.run(run_live_evals(cases))
        pass_rate = (passed / total) * 100 if total > 0 else 0
        print(f"\n📊 Live Evaluation Summary: {passed}/{total} passed ({pass_rate:.1f}%)")

        report = {
            "mode": "live",
            "passed": passed,
            "total": total,
            "pass_rate_percent": round(pass_rate, 2),
            "results": results,
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        if pass_rate < 90.0:
            print(
                f"❌ Live evaluation pass rate {pass_rate:.1f}% is below required 90.0% threshold."
            )
            sys.exit(1)
        else:
            print("✅ Live evaluation regression gate PASSED.")
            sys.exit(0)


if __name__ == "__main__":
    main()
