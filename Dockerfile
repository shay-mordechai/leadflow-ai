# Professional English Comment:
# Optimized Dockerfile for FastAPI/Celery. 
# Uses a non-root user and slim base for enhanced security and reduced footprint.

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
# Added libpq-dev for database stability and cleaned apt cache to save space
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

# SECURITY & SIZE OPTIMIZATION: 
# Using --no-cache-dir for all installations to keep the image lean.
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create storage directory for audio files
RUN mkdir -p storage/audio

# SECURITY: Run as a non-privileged user. 
# Prevents container breakout attacks and follows the Principle of Least Privilege.
RUN useradd -m leadflowuser && chown -R leadflowuser:leadflowuser /app
USER leadflowuser

# Expose the port for FastAPI
EXPOSE 8000

# Professional English Comment:
# Gunicorn is configured to handle timeouts and pipe logs directly to the container engine.
CMD ["gunicorn", "src.main:app", \
    "--workers", "2", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--bind", "0.0.0.0:8000", \
    "--timeout", "120", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--log-level", "info"]