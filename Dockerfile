# Professional English Comment:
# Multi-stage Dockerfile optimized for FastAPI and Celery.
# This image handles both the API and the Worker depending on the startup command.

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install system dependencies for audio processing (ffmpeg is crucial for Whisper)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create storage directory for audio files
RUN mkdir -p storage/audio

# Expose the port for FastAPI
EXPOSE 8000

# The actual command will be provided in docker-compose or AWS Task definition
# Note: Using Shell Form (no brackets) to prevent syntax errors on startup.
# Optimized for t3.micro (2 vCPUs -> 2 Workers)
CMD gunicorn src.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120