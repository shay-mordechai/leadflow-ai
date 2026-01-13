import time
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-Memory Rate Limiter.
    Limits requests based on IP address.
    Config: 100 requests per minute.
    """
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Dict to store request timestamps: {ip: [timestamp1, timestamp2]}
        self.clients = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Bypass for static files to reduce overhead
        if request.url.path.startswith("/static"):
            return await call_next(request)

        client_ip = request.client.host
        current_time = time.time()

        # Get client history
        request_history = self.clients[client_ip]

        # Filter out requests older than the window
        valid_requests = [t for t in request_history if current_time - t < self.window_seconds]
        self.clients[client_ip] = valid_requests

        # Check limit
        if len(valid_requests) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )

        # Add current request
        self.clients[client_ip].append(current_time)

        response = await call_next(request)
        return response
