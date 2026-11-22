import os
import re
import subprocess
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class FilePatch(BaseModel):
    file_path: str = Field(description="Relative repository path to the file to update")
    updated_content: str = Field(description="Complete updated content of the file")


class RemediationPlan(BaseModel):
    root_cause: str = Field(description="Concise explanation of why the CI run failed")
    patches: list[FilePatch] = Field(
        default_factory=list,
        description="Minimal file updates required to fix the failure (empty if human intervention is required)",
    )


def extract_referenced_files(log_text: str) -> dict[str, str]:
    """Read repository files explicitly mentioned in stack traces or build logs."""
    candidates = set(
        re.findall(
            r"(?:src|tests|alembic|frontend|\.github)/[A-Za-z0-9_./-]+\.(?:py|ts|tsx|yml|yaml|toml|txt|json)",
            log_text,
        )
    )
    for core_file in (
        "Dockerfile",
        "requirements.txt",
        "alembic.ini",
        "frontend/Dockerfile",
        "frontend/package.json",
    ):
        if core_file in log_text:
            candidates.add(core_file)

    repo_root = Path.cwd()
    contents: dict[str, str] = {}
    for rel_path in sorted(candidates)[:8]:
        target = (repo_root / rel_path).resolve()
        if target.is_file() and str(target).startswith(str(repo_root)):
            text = target.read_text(encoding="utf-8", errors="replace")
            contents[rel_path] = text[:12000]
    return contents


def run_verification_gates() -> None:
    """Validate patched files with Ruff and Pytest before allowing PR creation."""
    subprocess.run(["ruff", "check", "src", "tests", "alembic"], check=True)

    test_env = os.environ.copy()
    test_env.update(
        {
            "PYTHONPATH": ".",
            "ENVIRONMENT": "test",
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            "GOOGLE_API_KEY": "dummy_google_api_key_for_tests_only",
        }
    )
    subprocess.run(["pytest", "tests/", "-q"], env=test_env, check=True)


def main() -> None:
    log_path = Path("/tmp/failed_log.txt")
    if not log_path.exists():
        print("No failed log found.")
        return

    failed_log = log_path.read_text(encoding="utf-8", errors="replace")[-12000:]
    context_files = extract_referenced_files(failed_log)

    files_block = "\n\n".join(
        f"--- FILE: {path} ---\n{content}" for path, content in context_files.items()
    )

    prompt = (
        "You are a senior DevSecOps engineer fixing a failed GitHub Actions workflow on branch 'main'.\n"
        "Analyze the failed log and referenced files below. Provide the minimal, safe fix.\n"
        "If the failure is due to missing external secrets, network outages, or requires architectural decisions, "
        "return an empty patches list.\n\n"
        f"=== FAILED CI LOG ===\n{failed_log}\n\n"
        f"=== REFERENCED REPOSITORY FILES ===\n{files_block}"
    )

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RemediationPlan,
            temperature=0.1,
        ),
    )

    plan = RemediationPlan.model_validate_json(response.text)
    print(f"Root cause: {plan.root_cause}")

    if not plan.patches:
        print("No automated patches generated.")
        return

    repo_root = Path.cwd()
    for patch in plan.patches:
        target = (repo_root / patch.file_path).resolve()
        if not str(target).startswith(str(repo_root)) or ".git" in target.parts:
            raise ValueError(f"Refusing unsafe path write: {patch.file_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(patch.updated_content, encoding="utf-8")
        print(f"Patched: {patch.file_path}")

    run_verification_gates()


if __name__ == "__main__":
    main()
