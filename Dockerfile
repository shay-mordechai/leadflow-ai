# Professional English Comment:
# Optimized Dockerfile for FastAPI. 
# Uses a non-root user and slim base for enhanced security and reduced footprint.

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies (Removed Postgres libs since we use SQLite)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    gcc \
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

# Create storage and data directories for SQLite and media
RUN mkdir -p storage/audio data

# SECURITY: Run as a non-privileged user. 
# Prevents container breakout attacks and follows the Principle of Least Privilege.
RUN useradd -m leadflowuser && chown -R leadflowuser:leadflowuser /app
USER leadflowuser

# Expose the port for FastAPI
EXPOSE 8000

# Professional English Comment:
# Gunicorn is configured with 1 worker for SQLite concurrency safety.
# Logs are piped directly to the container engine.
CMD ["gunicorn", "src.main:app", \
    "--workers", "1", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--bind", "0.0.0.0:8000", \
    "--timeout", "120", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--log-level", "info"]