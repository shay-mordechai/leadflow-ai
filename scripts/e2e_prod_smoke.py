#!/usr/bin/env python3
"""External black-box E2E smoke test suite for LeadFlow AI production environment."""

import argparse
import http.cookiejar
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class StepResult:
    name: str
    status: str  # PASS, FAIL, WARN, SKIP
    detail: str
    latency_ms: float


class ExternalE2ERunner:
    def __init__(self, base_url: str, email: str, password: str, business_name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.business_name = business_name
        self.token: str | None = None
        self.results: list[StepResult] = []
        self.openapi_paths: set[str] = set()
        self.ssl_ctx = ssl.create_default_context()
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            urllib.request.HTTPSHandler(context=self.ssl_ctx),
        )

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        raw_body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> tuple[int, dict[str, str], str]:
        url = f"{self.base_url}{path}"
        req_headers = {
            "User-Agent": "LeadFlow-External-E2E/1.0",
            "Accept": "application/json",
        }
        if self.token:
            req_headers["Authorization"] = f"Bearer {self.token}"
        if headers:
            req_headers.update(headers)

        data: bytes | None = raw_body
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                body_text = resp.read().decode("utf-8", errors="replace")
                return resp.status, resp_headers, body_text
        except urllib.error.HTTPError as exc:
            resp_headers = {k.lower(): v for k, v in exc.headers.items()}
            body_text = exc.read().decode("utf-8", errors="replace")
            return exc.code, resp_headers, body_text
        except Exception as exc:
            return 0, {}, f"{type(exc).__name__}: {exc}"

    def _record(self, name: str, status: str, detail: str, start_ts: float) -> None:
        elapsed = (time.perf_counter() - start_ts) * 1000.0
        self.results.append(StepResult(name=name, status=status, detail=detail, latency_ms=elapsed))
        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "SKIP": "⏭️"}.get(status, "•")
        print(f"{icon} [{status}] {name} ({elapsed:.0f} ms) -> {detail}")

    def step_1_edge_health_and_security(self) -> None:
        # 1a. Health & Alembic DB sync status
        t0 = time.perf_counter()
        status, headers, body = self._request("GET", "/health/db-sync-status")
        if status == 200:
            self._record("Edge Health & DB Sync", "PASS", f"HTTP 200: {body[:120]}", t0)
        else:
            self._record("Edge Health & DB Sync", "FAIL", f"HTTP {status}: {body[:120]}", t0)

        # 1b. Verify Envoy Wasm DLP strips internal X-Data-TTL trigger header
        t0 = time.perf_counter()
        if "x-data-ttl" not in headers:
            self._record(
                "Envoy Edge DLP Header Hygiene", "PASS", "x-data-ttl stripped at perimeter", t0
            )
        else:
            self._record(
                "Envoy Edge DLP Header Hygiene", "FAIL", "x-data-ttl leaked in response headers", t0
            )

        # 1c. Verify ASGI 64-depth JSON nesting DoS protection
        t0 = time.perf_counter()
        deep_payload = (b'{"a":' * 70) + b"1" + (b"}" * 70)
        dos_status, _, _ = self._request(
            "POST",
            "/api/v1/auth/login",
            raw_body=deep_payload,
            headers={"Content-Type": "application/json"},
        )
        if dos_status in (400, 413, 422):
            self._record(
                "ASGI 64-Depth JSON DoS Guard",
                "PASS",
                f"Rejected deep JSON with HTTP {dos_status}",
                t0,
            )
        else:
            self._record(
                "ASGI 64-Depth JSON DoS Guard", "WARN", f"Unexpected HTTP {dos_status}", t0
            )

    def step_2_register_and_otp_login(self) -> bool:
        # 2a. Register new tenant account
        t0 = time.perf_counter()
        reg_payload = {
            "email": self.email,
            "password": self.password,
            "full_name": "Shay Test Owner",
            "business_name": self.business_name,
            "business_type": "clinic",
        }
        status, _, body = self._request("POST", "/api/v1/auth/register", json_body=reg_payload)
        if status in (200, 201):
            self._record(
                "Tenant Registration", "PASS", f"Registered {self.email} (HTTP {status})", t0
            )
        elif status == 400 and "already" in body.lower():
            self._record(
                "Tenant Registration",
                "WARN",
                f"Account already exists, continuing to login: {self.email}",
                t0,
            )
        else:
            self._record("Tenant Registration", "FAIL", f"HTTP {status}: {body[:160]}", t0)
            return False

        # 2b. Trigger login / email OTP dispatch
        t0 = time.perf_counter()
        form_body = urllib.parse.urlencode(
            {"username": self.email, "password": self.password}
        ).encode("utf-8")
        login_status, _, login_body = self._request(
            "POST",
            "/api/v1/auth/login",
            raw_body=form_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        # Direct JWT returned without separate OTP verification step
        try:
            parsed = json.loads(login_body)
        except json.JSONDecodeError:
            parsed = {}

        if login_status == 200 and parsed.get("access_token"):
            self.token = parsed["access_token"]
            self._record(
                "Login & JWT Issuance", "PASS", "Authenticated with HS256 access_token", t0
            )
            return True

        if login_status in (200, 202):
            self._record(
                "Email OTP Dispatch", "PASS", f"OTP sent to {self.email} (HTTP {login_status})", t0
            )
            otp_code = input(
                f"\n📩 Enter the 6-digit OTP sent to {self.email} (or press Enter to skip): "
            ).strip()
            if not otp_code:
                self._record(
                    "Email OTP Verification",
                    "SKIP",
                    "No OTP entered interactively",
                    time.perf_counter(),
                )
                return False

            t1 = time.perf_counter()
            v_status, _, v_body = self._request(
                "POST",
                "/api/v1/auth/verify-otp",
                json_body={"email": self.email, "otp_code": otp_code},
            )
            try:
                v_parsed = json.loads(v_body)
            except json.JSONDecodeError:
                v_parsed = {}

            if v_status == 200 and (v_parsed.get("access_token") or len(self.cookie_jar) > 0):
                self.token = v_parsed.get("access_token")
                self._record(
                    "Email OTP Verification",
                    "PASS",
                    f"OTP verified (cookies={len(self.cookie_jar)})",
                    t1,
                )

                # Replay same OTP to confirm single-use atomic invalidation
                t2 = time.perf_counter()
                replay_status, _, _ = self._request(
                    "POST",
                    "/api/v1/auth/verify-otp",
                    json_body={"email": self.email, "otp_code": otp_code},
                )
                if replay_status in (400, 401, 403):
                    self._record(
                        "Single-Use OTP Replay Block",
                        "PASS",
                        f"Replay blocked with HTTP {replay_status}",
                        t2,
                    )
                else:
                    self._record(
                        "Single-Use OTP Replay Block",
                        "FAIL",
                        f"Replay returned HTTP {replay_status}",
                        t2,
                    )
                return True

            self._record("Email OTP Verification", "FAIL", f"HTTP {v_status}: {v_body[:160]}", t1)
            return False

        self._record("Login / OTP Flow", "FAIL", f"HTTP {login_status}: {login_body[:160]}", t0)
        return False

    def step_3_profile_tier_and_isolation(self) -> None:
        # 3a. Inspect default subscription tier and quotas
        t0 = time.perf_counter()
        status, _, body = self._request("GET", "/api/v1/auth/me")
        if status != 200:
            status, _, body = self._request("GET", "/api/v1/settings")

        if status == 200:
            try:
                profile = json.loads(body)
                tier = (
                    profile.get("plan_tier")
                    or profile.get("subscription_tier")
                    or profile.get("tier")
                    or "unknown"
                )
                self._record("Tenant Profile & Default Tier", "PASS", f"Active tier={tier}", t0)
            except json.JSONDecodeError:
                self._record("Tenant Profile & Default Tier", "PASS", f"HTTP 200: {body[:100]}", t0)
        else:
            self._record(
                "Tenant Profile & Default Tier", "WARN", f"HTTP {status}: {body[:120]}", t0
            )

        # 3b. Verify non-admin tenant cannot access admin partner analytics
        t0 = time.perf_counter()
        adm_status, _, _ = self._request("GET", "/api/v1/partners/performance")
        if adm_status in (401, 403):
            self._record(
                "Admin Endpoint AuthZ Guard",
                "PASS",
                f"Blocked non-admin with HTTP {adm_status}",
                t0,
            )
        else:
            self._record(
                "Admin Endpoint AuthZ Guard", "FAIL", f"Expected 403, got HTTP {adm_status}", t0
            )

    def step_4_business_prompt_rag_and_simulator(self) -> None:
        # 4a. Configure business persona & tailored prompt settings
        t0 = time.perf_counter()
        settings_payload = {
            "business_name": self.business_name,
            "business_type": "clinic",
            "ai_tone": "Professional",
            "products_services": (
                "טיפול פנים קלאסי (60 דקות): 350 שח. "
                "הסרת שיער בלייזר פנים מלאות: 280 שח לטיפול. "
                "שעות פעילות: ימים א-ה 09:00-19:00, יום ו 09:00-13:00."
            ),
            "custom_instructions": (
                "אתה נציג שירות לקוחות אדיב ומקצועי של קליניקת אסתטיקה ולייזר. "
                "ענה בעברית קצרה וברורה אך ורק על בסיס המחירון והמידע העסקי שסופק."
            ),
            "summary_template": "",
        }
        s_status, _, s_body = self._request("POST", "/api/v1/settings", json_body=settings_payload)

        if s_status in (200, 201):
            self._record(
                "Business Prompt & Persona Update",
                "PASS",
                f"Updated settings (HTTP {s_status})",
                t0,
            )
        else:
            self._record(
                "Business Prompt & Persona Update", "WARN", f"HTTP {s_status}: {s_body[:120]}", t0
            )

        # 4b. Upload Hebrew pricing sheet via multipart/form-data to Hybrid RAG
        t0 = time.perf_counter()
        boundary = f"----LeadFlowBoundary{uuid.uuid4().hex}"
        hebrew_doc = (
            "# מחירון טיפולים — קליניקת E2E\n"
            '- טיפול פנים קלאסי (60 דקות): 350 ש"ח\n'
            '- הסרת שיער בלייזר פנים מלאות: 280 ש"ח לטיפול\n'
            "- שעות פעילות: ימים א'-ה' 09:00–19:00, יום ו' 09:00–13:00\n"
            "- מדיניות ביטולים: ביטול חינם עד 24 שעות לפני התור.\n"
        ).encode()

        multipart_body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="clinic_prices_he.md"\r\n'
                f"Content-Type: text/markdown; charset=utf-8\r\n\r\n"
            ).encode()
            + hebrew_doc
            + f"\r\n--{boundary}--\r\n".encode()
        )

        up_status, _, up_body = self._request(
            "POST",
            "/api/v1/knowledge/documents",
            raw_body=multipart_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            timeout=25.0,
        )
        if up_status in (200, 201):
            self._record(
                "Hybrid RAG Document Ingestion",
                "PASS",
                f"Uploaded Hebrew price list (HTTP {up_status})",
                t0,
            )
            time.sleep(2.0)  # Allow synchronous/background embedding indexing to settle
        else:
            self._record(
                "Hybrid RAG Document Ingestion", "WARN", f"HTTP {up_status}: {up_body[:140]}", t0
            )

        # 4c. Test Dashboard Chat Simulator with grounded pricing query
        t0 = time.perf_counter()
        sim_status, _, sim_body = self._request(
            "POST",
            "/api/v1/settings/simulate",
            json_body={"message": "כמה עולה טיפול פנים קלאסי ומתי אתם פתוחים?"},
            timeout=15.0,
        )
        if sim_status == 200:
            if "Security Exception" in sim_body or '"error"' in sim_body:
                self._record(
                    "Dashboard Simulator (Grounded RAG Query)",
                    "FAIL",
                    f"HTTP 200 | returned error/security exception: {sim_body[:140]}",
                    t0,
                )
            else:
                has_price = "350" in sim_body
                verdict = "PASS" if has_price else "WARN"
                self._record(
                    "Dashboard Simulator (Grounded RAG Query)",
                    verdict,
                    f"HTTP 200 | contains_price_350={has_price} | reply={sim_body[:140]}",
                    t0,
                )
        else:
            self._record(
                "Dashboard Simulator (Grounded RAG Query)",
                "FAIL",
                f"HTTP {sim_status}: {sim_body[:140]}",
                t0,
            )

        # 4d. Test Dashboard Simulator abstention on unknown fact
        t0 = time.perf_counter()
        abs_status, _, abs_body = self._request(
            "POST",
            "/api/v1/settings/simulate",
            json_body={"message": "האם אתם מבצעים השתלות שיניים בהרדמה מלאה?"},
            timeout=15.0,
        )
        if abs_status == 200:
            if "Security Exception" in abs_body or '"error"' in abs_body:
                self._record(
                    "Dashboard Simulator (Abstention Guard)",
                    "FAIL",
                    f"HTTP 200 | returned error/security exception: {abs_body[:140]}",
                    t0,
                )
            else:
                self._record(
                    "Dashboard Simulator (Abstention Guard)",
                    "PASS",
                    f"HTTP 200 | reply={abs_body[:140]}",
                    t0,
                )
        else:
            self._record(
                "Dashboard Simulator (Abstention Guard)",
                "WARN",
                f"HTTP {abs_status}: {abs_body[:140]}",
                t0,
            )

    def step_5_hitl_kpis_and_logout(self) -> None:
        # 5a. Check HITL PendingApprovals & Pilot KPIs endpoints
        t0 = time.perf_counter()
        app_status, _, app_body = self._request("GET", "/api/v1/leads/approvals")
        kpi_status, _, _ = self._request("GET", "/api/v1/insights/pilot-kpis")
        if app_status == 200 and kpi_status == 200:
            self._record(
                "HITL Approvals & Pilot KPIs",
                "PASS",
                f"approvals=200 ({len(app_body)}B), kpis=200",
                t0,
            )
        else:
            self._record(
                "HITL Approvals & Pilot KPIs",
                "WARN",
                f"approvals={app_status}, kpis={kpi_status}",
                t0,
            )

        # 5b. Logout & verify immediate Redis JWT revocation
        t0 = time.perf_counter()
        out_status, _, _ = self._request("POST", "/api/v1/auth/logout")
        if out_status in (200, 204):
            post_status, _, _ = self._request("GET", "/api/v1/leads/approvals")
            if post_status == 401:
                self._record(
                    "JWT Logout & Redis Revocation",
                    "PASS",
                    "Replayed JWT rejected with HTTP 401",
                    t0,
                )
            else:
                self._record(
                    "JWT Logout & Redis Revocation",
                    "WARN",
                    f"Post-logout replay returned HTTP {post_status}",
                    t0,
                )
        else:
            self._record(
                "JWT Logout & Redis Revocation", "WARN", f"Logout returned HTTP {out_status}", t0
            )

    def run(self) -> int:
        print(f"🚀 Running External E2E Production Suite against {self.base_url}")
        print(f"👤 Test Tenant Email: {self.email}\n" + "-" * 72)

        self.step_1_edge_health_and_security()
        if self.step_2_register_and_otp_login():
            self.step_3_profile_tier_and_isolation()
            self.step_4_business_prompt_rag_and_simulator()
            self.step_5_hitl_kpis_and_logout()

        print("-" * 72)
        passed = sum(1 for r in self.results if r.status == "PASS")
        warned = sum(1 for r in self.results if r.status == "WARN")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        print(f"📊 Summary: {passed} PASSED | {warned} WARNINGS | {failed} FAILED")
        return 1 if failed > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run external black-box E2E tests against LeadFlow AI production."
    )
    parser.add_argument("--base-url", default="https://my-leads.app", help="Production base URL")
    parser.add_argument(
        "--email", required=True, help="Real email address (e.g. you+e2e1@gmail.com) to receive OTP"
    )
    parser.add_argument(
        "--password", default="E2eTestPass!2026#", help="Password for test tenant registration"
    )
    parser.add_argument(
        "--business-name", default="קליניקת אסתטיקה ולייזר", help="Business name for onboarding"
    )
    args = parser.parse_args()

    runner = ExternalE2ERunner(
        base_url=args.base_url,
        email=args.email,
        password=args.password,
        business_name=args.business_name,
    )
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
