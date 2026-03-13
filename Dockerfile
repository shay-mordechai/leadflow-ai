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

# Install system dependencies (Removed Postgres libs since we use SQLite)
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
# Installing PyTorch CPU version explicitly to save massive amounts of space.
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create storage and data directories for SQLite, media, and AI model caching
RUN mkdir -p storage/audio data/huggingface_cache

# SECURITY: Run as a non-privileged user. 
# Prevents container breakout attacks and follows the Principle of Least Privilege.
RUN useradd -m leadflowuser && chown -R leadflowuser:leadflowuser /app
USER leadflowuser

# Expose the port for FastAPI
EXPOSE 8000

# Professional English Comment:
# Execute uvicorn directly to ensure maximum stability and prevent container crash loops
CMD ["python3", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]