# src/middleware/rate)limit.py
import time
from collections import defaultdict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-Memory Rate Limiter.
    Limits requests based on IP address to prevent abuse.
    Default Config: 100 requests per minute per IP.
    """
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Dictionary to store request timestamps: {ip: [timestamp1, timestamp2]}
        self.clients = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Bypass rate limiting for static files and health checks
        if request.url.path.startswith("/static") or request.url.path == "/health":
            return await call_next(request)

        # SECURITY FIX: Get the Real IP from Cloudflare
        # If running locally without CF, fallback to client.host
        client_ip = request.headers.get("CF-Connecting-IP", request.client.host)
        
        current_time = time.time()

        # Get client history
        request_history = self.clients[client_ip]

        # Filter out requests older than the defined window
        valid_requests = [t for t in request_history if current_time - t < self.window_seconds]
        
        # Update the history
        self.clients[client_ip] = valid_requests

        # Check if limit is reached
        if len(valid_requests) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )

        # Record the current request timestamp
        self.clients[client_ip].append(current_time)

        response = await call_next(request)
        return response