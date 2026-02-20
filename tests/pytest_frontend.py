# tests/pytest_frontend.py
import os
import subprocess
import pytest
import logging

logger = logging.getLogger(__name__)

# Resolve the absolute path to the frontend directory
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

def test_frontend_directory_exists():
    """
    Sanity check: Ensures the frontend directory and package.json exist
    before attempting to build.
    """
    assert os.path.exists(FRONTEND_DIR), f"Frontend directory missing at {FRONTEND_DIR}"
    
    package_json_path = os.path.join(FRONTEND_DIR, "package.json")
    assert os.path.exists(package_json_path), "package.json is missing!"

def test_nextjs_production_build():
    """
    CRITICAL CI STEP: Runs the actual Next.js build process.
    This simulates a production build to catch Server-Side Rendering (SSR) errors,
    TypeScript type mismatches, and missing imports BEFORE deployment.
    """
    # Step 1: Install dependencies using clean install (npm ci)
    print("\n📦 Installing frontend dependencies...")
    install_process = subprocess.run(
        ["npm", "install"], # Using 'install' instead of 'ci' just in case package-lock is out of sync
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True
    )
    
    assert install_process.returncode == 0, f"npm install failed!\nSTDERR: {install_process.stderr}"

    # Step 2: Run the Next.js build
    print("\n🔨 Running Next.js build...")
    
    # We pass the production env variables so the build mimics production exactly
    env = os.environ.copy()
    env["NEXT_PUBLIC_API_URL"] = "https://my-leads.app"
    
    build_process = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        env=env
    )
    
    # If the build fails (e.g., SSR TypeError, missing font, etc.), this assertion will fail the test
    if build_process.returncode != 0:
        pytest.fail(f"Frontend build crashed!\n\nSTDOUT:\n{build_process.stdout}\n\nSTDERR:\n{build_process.stderr}")

    # If we reached here, the build was successful!
    assert build_process.returncode == 0
    print("✅ Frontend build completed successfully.")