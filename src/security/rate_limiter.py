# src/security/rate_limiter.py
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

def get_real_ip(request: Request):
    """
    Security: Retrieves the actual client IP behind Cloudflare.
    If 'CF-Connecting-IP' is missing, falls back to direct connection IP.
    """
    return request.headers.get("CF-Connecting-IP", get_remote_address(request))

# Global Limiter Instance
limiter = Limiter(key_func=get_real_ip)