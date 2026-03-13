# Dockerfile
# Optimized Dockerfile for FastAPI with AI processing capabilities (Whisper).
# Uses a non-root user and slim base for enhanced security and reduced footprint.

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set HuggingFace Cache directory to a writable location for the non-root user
# This is critical for faster-whisper to download models without permission errors
ENV HF_HOME=/app/data/huggingface_cache

WORKDIR /app

# Install system dependencies
# Includes ffmpeg and libraries for audio processing (PyAV/faster-whisper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    build-essential \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

# SECURITY & SIZE OPTIMIZATION: 
# Using --no-cache-dir for all installations to keep the image lean.
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# FIX: Pre-create ALL required storage directories (including kyc) to prevent PermissionError
RUN mkdir -p storage/audio storage/kyc data/huggingface_cache

# SECURITY: Run as a non-privileged user. 
# Prevents container breakout attacks and follows the Principle of Least Privilege.
RUN useradd -m leadflowuser && chown -R leadflowuser:leadflowuser /app
USER leadflowuser

# Expose the port for FastAPI
EXPOSE 8000

# Gunicorn is configured with 1 worker for SQLite concurrency safety.
# Timeout is set to 120s to allow AI models (Whisper/Gemini) time to process.
# Logs are piped directly to the container engine.
CMD ["gunicorn", "src.main:app", \
    "--workers", "1", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--bind", "0.0.0.0:8000", \
    "--timeout", "120", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--log-level", "info"]