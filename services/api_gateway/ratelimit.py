"""
Rate limiting middleware for ANTS API Gateway.
Implements token bucket algorithm with Redis backend.
"""
from fastapi import HTTPException, Request
from typing import Optional
from datetime import datetime, timedelta
import time
import structlog
from collections import defaultdict

logger = structlog.get_logger()


class RateLimitConfig:
    """Configuration for rate limiting."""
    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 100,
        cost_per_request: int = 1
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.cost_per_request = cost_per_request
        self.refill_rate = requests_per_minute / 60.0  # tokens per second


class TokenBucket:
    """Token bucket for rate limiting."""
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()

    def refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.
        Returns True if successful, False if not enough tokens.
        """
        self.refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Get time to wait in seconds before tokens are available.
        """
        self.refill()

        if self.tokens >= tokens:
            return 0.0

        needed_tokens = tokens - self.tokens
        return needed_tokens / self.refill_rate


class RateLimiter:
    """
    Rate limiter using token bucket algorithm.
    In production, this should use Redis for distributed rate limiting.
    """

    def __init__(self):
        # In-memory buckets: key -> TokenBucket
        # Key format: "{tenant_id}:{endpoint}" or "{api_key}:{endpoint}"
        self.buckets: dict[str, TokenBucket] = {}

        # Default rate limits per endpoint
        self.endpoint_limits = {
            "/v1/agents/invoke": RateLimitConfig(
                requests_per_minute=60,
                burst_size=100,
                cost_per_request=1
            ),
            "/v1/memory/search": RateLimitConfig(
                requests_per_minute=120,
                burst_size=200,
                cost_per_request=1
            ),
            "default": RateLimitConfig(
                requests_per_minute=100,
                burst_size=150,
                cost_per_request=1
            )
        }

    def _get_bucket_key(self, request: Request, tenant_id: str) -> str:
        """Generate bucket key for request."""
        # Normalize path (remove query params, trailing slashes)
        path = request.url.path.rstrip("/")

        # Format: tenant_id:endpoint
        return f"{tenant_id}:{path}"

    def _get_or_create_bucket(self, key: str, config: RateLimitConfig) -> TokenBucket:
        """Get existing bucket or create new one."""
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(
                capacity=config.burst_size,
                refill_rate=config.refill_rate
            )

        return self.buckets[key]

    def _get_config_for_path(self, path: str) -> RateLimitConfig:
        """Get rate limit config for specific path."""
        # Try exact match first
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]

        # Try prefix matching
        for endpoint_pattern, config in self.endpoint_limits.items():
            if path.startswith(endpoint_pattern):
                return config

        # Default
        return self.endpoint_limits["default"]

    async def check_rate_limit(
        self,
        request: Request,
        tenant_id: str,
        cost: Optional[int] = None
    ) -> dict:
        """
        Check rate limit for request.
        Raises HTTPException if limit exceeded.
        Returns metadata about rate limit status.
        """
        path = request.url.path.rstrip("/")
        config = self._get_config_for_path(path)

        # Get bucket
        bucket_key = self._get_bucket_key(request, tenant_id)
        bucket = self._get_or_create_bucket(bucket_key, config)

        # Determine cost
        request_cost = cost or config.cost_per_request

        # Try to consume tokens
        if bucket.consume(request_cost):
            logger.debug(
                "rate_limit_allowed",
                tenant_id=tenant_id,
                path=path,
                tokens_remaining=bucket.tokens
            )

            return {
                "allowed": True,
                "limit": config.burst_size,
                "remaining": int(bucket.tokens),
                "reset_in_seconds": int((config.burst_size - bucket.tokens) / config.refill_rate)
            }
        else:
            # Rate limit exceeded
            wait_time = bucket.get_wait_time(request_cost)

            logger.warning(
                "rate_limit_exceeded",
                tenant_id=tenant_id,
                path=path,
                wait_time_seconds=wait_time
            )

            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Retry after {int(wait_time)} seconds",
                headers={
                    "Retry-After": str(int(wait_time)),
                    "X-RateLimit-Limit": str(config.burst_size),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + wait_time))
                }
            )

    def get_status(self, tenant_id: str, path: str) -> dict:
        """Get current rate limit status without consuming tokens."""
        bucket_key = f"{tenant_id}:{path}"

        if bucket_key not in self.buckets:
            config = self._get_config_for_path(path)
            return {
                "limit": config.burst_size,
                "remaining": config.burst_size,
                "reset_in_seconds": 0
            }

        bucket = self.buckets[bucket_key]
        bucket.refill()
        config = self._get_config_for_path(path)

        return {
            "limit": config.burst_size,
            "remaining": int(bucket.tokens),
            "reset_in_seconds": int((config.burst_size - bucket.tokens) / config.refill_rate)
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


async def apply_rate_limit(request: Request, tenant_id: str):
    """
    Middleware function to apply rate limiting.
    Should be called in endpoint dependencies.
    """
    metadata = await rate_limiter.check_rate_limit(request, tenant_id)

    # Add rate limit headers to response (this requires response object)
    # In actual implementation, this would be done via middleware
    return metadata


class RateLimitMiddleware:
    """
    ASGI middleware for automatic rate limiting.
    Adds rate limit headers to all responses.
    """

    def __init__(self, app, rate_limiter: RateLimiter):
        self.app = app
        self.rate_limiter = rate_limiter

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract tenant_id from headers or auth
        # This is simplified - in production, extract from validated auth
        headers = dict(scope.get("headers", []))
        tenant_id = headers.get(b"x-tenant-id", b"default").decode()

        request = Request(scope, receive)

        try:
            # Check rate limit
            metadata = await self.rate_limiter.check_rate_limit(request, tenant_id)

            # Wrap send to add rate limit headers
            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    headers = message.setdefault("headers", [])
                    headers.extend([
                        (b"x-ratelimit-limit", str(metadata["limit"]).encode()),
                        (b"x-ratelimit-remaining", str(metadata["remaining"]).encode()),
                        (b"x-ratelimit-reset", str(metadata["reset_in_seconds"]).encode()),
                    ])

                await send(message)

            await self.app(scope, receive, send_with_headers)

        except HTTPException as e:
            # Rate limit exceeded - send error response
            response_body = {
                "detail": e.detail,
                "status_code": e.status_code
            }

            import json
            body = json.dumps(response_body).encode()

            await send({
                "type": "http.response.start",
                "status": e.status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    *[(k.encode(), v.encode()) for k, v in e.headers.items()]
                ]
            })
            await send({
                "type": "http.response.body",
                "body": body
            })
