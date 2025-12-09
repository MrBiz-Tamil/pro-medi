"""
Security Headers Middleware
Adds important security headers to all responses to protect against common attacks.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Headers added:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables XSS filtering in browsers
    - Strict-Transport-Security: Enforces HTTPS (when in production)
    - Content-Security-Policy: Controls resources the browser can load
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking - deny embedding in frames
        response.headers["X-Frame-Options"] = "DENY"
        
        # Enable XSS filtering (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Strict Transport Security - enforce HTTPS for 1 year
        # Only add if request is over HTTPS (check X-Forwarded-Proto for proxied requests)
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if request.url.scheme == "https" or forwarded_proto == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy - restrict resource loading
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' wss: https:; "
            "frame-ancestors 'none';"
        )
        
        # Referrer Policy - only send origin for cross-origin requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy - disable unnecessary browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        
        return response
