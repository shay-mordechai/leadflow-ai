#!/bin/bash

# Professional English Comment:
# Optimized startup script for Fedora Kinoite using Podman and Virtual Environment.
# Handles asynchronous service management and ensures clean shutdown.

export PYTHONPATH=.

# --- 1. Activate Virtual Environment ---
if [ -f "venv/bin/activate" ]; then
    echo "🐍 Activating Virtual Environment..."
    source venv/bin/activate
else
    echo "❌ Error: venv not found. Please run 'python3 -m venv venv' first."
    exit 1
fi

# --- 2. Start Infrastructure with Podman ---
echo "🐳 Starting Podman containers (Postgres & Redis)..."
# podman-compose orchestrates rootless containers without requiring sudo.
podman-compose up -d

# Wait for services to initialize
sleep 3

# --- 3. Start Celery Worker ---
echo "🤖 Starting Celery Worker (Logging to celery.log)..."
python3 -m celery -A src.worker.tasks:celery_app worker --loglevel=info > celery.log 2>&1 &
CELERY_PID=$!

# --- 4. Start Uvicorn Server ---
echo "🔥 Starting Uvicorn API Server..."
# Using 'python3 -m uvicorn' ensures the executable from the active venv is used.
python3 -m uvicorn src.main:app --reload &
UVICORN_PID=$!

echo "---------------------------------------------------"
echo "🌐 API Documentation: http://127.0.0.1:8000/docs"
echo "📜 View Celery logs: tail -f celery.log"
echo "💡 Press Ctrl+C to stop all services"
echo "---------------------------------------------------"

# Cleanup on exit (Ctrl+C)
# Trap ensures that background processes (Celery/Uvicorn) are terminated
# when the user interrupts the script.
trap "echo '🛑 Stopping services...'; kill $CELERY_PID $UVICORN_PID 2>/dev/null; exit" SIGINT SIGTERM EXIT

# Keep the script alive to monitor background tasks
wait
