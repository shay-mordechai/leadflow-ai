# Optimized Dockerfile for FastAPI with AI processing capabilities (Whisper).
# Uses a non-root user and slim base for enhanced security and reduced footprint.

FROM python:3.11-slim

ARG CURRENT_IMAGE_SHA=unknown
ENV CURRENT_IMAGE_SHA=${CURRENT_IMAGE_SHA}

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV HF_HOME=/app/data/huggingface_cache

# SECURITY: Create user FIRST before adding any files
RUN useradd -m -u 1000 leadflowuser

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    postgresql-client \
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

# Install Python dependencies separately to cache the layer
COPY --chown=leadflowuser:leadflowuser requirements.txt .
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application directly as the non-root user
# This avoids the expensive 'chown -R' layer that causes disk space exhaustion
COPY --chown=leadflowuser:leadflowuser . .

# FIX: Pre-create required storage directories
RUN mkdir -p storage/audio storage/kyc data/huggingface_cache models \
    && chown -R leadflowuser:leadflowuser storage data models

# Switch to the non-privileged user
USER leadflowuser

# Expose the port for FastAPI
EXPOSE 8000

# Gunicorn configuration
CMD ["gunicorn", "src.main:app", \
    "--workers", "1", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--bind", "0.0.0.0:8000", \
    "--timeout", "120", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--log-level", "info"]