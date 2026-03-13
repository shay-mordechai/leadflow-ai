#!/bin/bash

# ==============================================================================
# 🚀 LeadFlow AI - Local Development Startup Script
# This script orchestrates the local environment: API Server, Celery Worker, and Redis.
# Optimized for local testing without affecting production.
# ==============================================================================

# Ensure Python can find the 'src' module
export PYTHONPATH=$(pwd)

# Set explicitly to development so it skips AWS SSM loading
export APP_ENV="development"

# Use local Redis database 1 for development (separates dev from test)
export REDIS_URL="redis://127.0.0.1:6379/1"

# --- FIX: Set Local Database Path ---
# Create a local 'data' directory in the project folder if it doesn't exist
mkdir -p data
# Override the production Docker path (/app/data/...) with a local path
export DATABASE_URL="sqlite:///./data/local_leads.db"

# --- Inject Fake Keys for Local Dev to Prevent Crash Warnings ---
# If you want to actually test AI locally, you should put your real keys in a .env file.
if [ -z "$GOOGLE_API_KEY" ]; then
    export GOOGLE_API_KEY="dummy_key_to_prevent_warnings_in_local_dev"
fi
if [ -z "$SECRET_KEY" ]; then
    export SECRET_KEY="dummy_local_secret_key_for_jwt_tokens_do_not_use_in_prod"
fi

echo "---------------------------------------------------"
echo "🛠️ Starting LeadFlow AI Local Environment"
echo "---------------------------------------------------"

# --- 1. Infrastructure: Redis ---
# Check if Redis is running via Podman/Docker, if not, try to start it
if ! podman ps --format '{{.Names}}' | grep -q "^leadflow-redis-dev$"; then
    echo "🐳 Starting local Redis container..."
    podman run -d --name leadflow-redis-dev --replace -p 6379:6379 docker.io/library/redis:7-alpine
else
    echo "✅ Local Redis is already running."
fi

# --- 2. Activate Virtual Environment & Auto-Install Dependencies ---
if [ -f "venv/bin/activate" ]; then
    echo "🐍 Activating Virtual Environment..."
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    echo "🐍 Activating Virtual Environment (.venv)..."
    source .venv/bin/activate
else
    echo "⚠️ Warning: No virtual environment found. Assuming dependencies are installed globally."
fi

echo "📦 Verifying and installing missing dependencies (including Celery)..."
# Suppress pip upgrade warnings and install quietly
python3 -m pip install -r requirements.txt -q --disable-pip-version-check

# Wait 2 seconds to ensure Redis is ready to accept connections
sleep 2

# --- 3. Start Celery Worker (Background) ---
echo "🤖 Starting Async Celery Worker..."
# Note: We now point to the correct new entrypoint 'src.worker.celery_app'
# We use 'info' log level but format it so it doesn't clash too much with FastAPI
celery -A src.worker.celery_app worker --loglevel=info --concurrency=2 > celery_dev.log 2>&1 &
CELERY_PID=$!
echo "   [Celery running in background. Logs: tail -f celery_dev.log]"

# --- 4. Start FastAPI Server (Foreground) ---
echo "🔥 Starting Uvicorn API Server on port 8000..."
echo "---------------------------------------------------"
echo "🌐 API Endpoint: http://127.0.0.1:8000"
echo "📚 Swagger Docs: http://127.0.0.1:8000/docs"
echo "💡 Press Ctrl+C to gracefully stop all services"
echo "---------------------------------------------------"

# Disable JSON Logging temporarily for local development readability by overriding the env var
export LOG_FORMAT="TEXT" 

# Run Uvicorn in the foreground so you see API requests live
uvicorn src.main:app --reload --port 8000
UVICORN_PID=$!

# --- Cleanup Procedure (When user presses Ctrl+C) ---
# This ensures we don't leave zombie Python/Celery processes running
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $CELERY_PID 2>/dev/null
    # Uvicorn stops itself on Ctrl+C, but just in case:
    kill $UVICORN_PID 2>/dev/null 
    echo "✅ Development environment shut down."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT
wait