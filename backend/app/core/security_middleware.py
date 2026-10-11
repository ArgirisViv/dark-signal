"""
Security middleware and utilities for the Dark Signal API.
Provides rate limiting, security headers, and input validation.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import asyncio
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple rate limiting middleware.
    Limits requests per IP address to prevent abuse.
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        self.cleanup_interval = 60  # Cleanup old entries every 60 seconds
        self.last_cleanup = datetime.now(timezone.utc)
    
    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Cleanup old entries periodically
        if (datetime.now(timezone.utc) - self.last_cleanup).seconds > self.cleanup_interval:
            self._cleanup_old_entries()
            self.last_cleanup = datetime.now(timezone.utc)
        
        # Check rate limit
        now = datetime.now(timezone.utc)
        minute_ago = now - timedelta(minutes=1)
        
        # Remove requests older than 1 minute
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if req_time > minute_ago
        ]
        
        # Check if exceeded limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": True,
                    "message": "Too many requests. Please try again later.",
                    "retry_after": 60
                }
            )
        
        # Add current request
        self.requests[client_ip].append(now)
        
        # Continue to next middleware
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self.requests_per_minute - len(self.requests[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int((now + timedelta(minutes=1)).timestamp()))
        
        return response
    
    def _cleanup_old_entries(self):
        """Remove old IP entries from memory"""
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        ips_to_remove = []
        
        for client_ip, requests in self.requests.items():
            self.requests[client_ip] = [
                req_time for req_time in requests
                if req_time > hour_ago
            ]
            if not self.requests[client_ip]:
                ips_to_remove.append(client_ip)
        
        for client_ip in ips_to_remove:
            del self.requests[client_ip]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses to protect against common web vulnerabilities.
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy
        if (
            request.url.path.startswith("/api/docs")
            or request.url.path.startswith("/api/redoc")
            or request.url.path.startswith("/docs")
            or request.url.path.startswith("/redoc")
        ):
            response.headers["Content-Security-Policy"] = (
                "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'"
            )
        
        # HSTS (Strict-Transport-Security)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Permissions Policy
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "ambient-light-sensor=(), "
            "autoplay=(), "
            "camera=(), "
            "encrypted-media=(), "
            "fullscreen=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "midi=(), "
            "payment=(), "
            "picture-in-picture=(), "
            "speaker=(), "
            "usb=(), "
            "vr=(), "
            "xr-spatial-tracking=()"
        )
        
        return response


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Validate and sanitize input data to prevent injection attacks.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Check for suspicious patterns in query parameters
        query_params = request.query_params
        
        for key, value in query_params.items():
            if self._contains_suspicious_content(value):
                logger.warning(f"Suspicious input detected: {key}={value}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": True,
                        "message": "Invalid input detected",
                        "details": f"Parameter '{key}' contains invalid characters"
                    }
                )
        
        response = await call_next(request)
        return response
    
    @staticmethod
    def _contains_suspicious_content(value: str) -> bool:
        """Check for SQL injection and other suspicious patterns"""
        suspicious_patterns = [
            "' or '1'='1",
            "'; DROP TABLE",
            "<script>",
            "javascript:",
            "onclick=",
            "onerror=",
            "--",
            "/*",
            "xp_",
            "sp_"
        ]
        
        value_lower = str(value).lower()
        return any(pattern.lower() in value_lower for pattern in suspicious_patterns)
