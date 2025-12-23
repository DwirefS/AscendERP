"""
Rate Limiter

Token bucket algorithm for rate limiting:
- Agent execution throttling
- API request rate limiting
- Per-tenant resource quotas
- DDoS protection

Multi-tier limits:
- Per-user limits
- Per-tenant limits
- Global system limits
"""

import time
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from threading import Lock
import redis
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: float):
        """
        Initialize exception.

        Args:
            message: Error message
            retry_after: Seconds until rate limit resets
        """
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    max_requests: int  # Maximum requests allowed
    window_seconds: int  # Time window in seconds
    burst_size: Optional[int] = None  # Burst capacity (defaults to max_requests)

    def __post_init__(self):
        if self.burst_size is None:
            self.burst_size = self.max_requests


class RateLimiter:
    """
    Token bucket rate limiter with Redis backend.

    Supports:
    - Per-key rate limiting (user, tenant, IP, etc.)
    - Multiple limit tiers (user, tenant, global)
    - Distributed rate limiting via Redis
    - Graceful degradation if Redis unavailable
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        default_config: Optional[RateLimitConfig] = None,
    ):
        """
        Initialize Rate Limiter.

        Args:
            redis_client: Redis client for distributed limiting
            default_config: Default rate limit configuration
        """
        self.redis_client = redis_client
        self.default_config = default_config or RateLimitConfig(
            max_requests=100, window_seconds=60  # 100 requests per minute
        )

        # Local cache (fallback if Redis unavailable)
        self._local_cache: Dict[str, Tuple[float, int]] = {}
        self._lock = Lock()

    def check_rate_limit(
        self,
        key: str,
        config: Optional[RateLimitConfig] = None,
        cost: int = 1,
    ) -> Tuple[bool, float]:
        """
        Check if request is within rate limit.

        Args:
            key: Rate limit key (e.g., "user:123", "tenant:abc", "ip:1.2.3.4")
            config: Rate limit configuration (uses default if not provided)
            cost: Cost of this request (default 1, can be higher for expensive ops)

        Returns:
            Tuple of (allowed, retry_after_seconds)

        Raises:
            RateLimitExceeded: If rate limit exceeded
        """
        config = config or self.default_config

        # Try Redis first (distributed limiting)
        if self.redis_client:
            try:
                return self._check_redis(key, config, cost)
            except Exception as e:
                logger.warning(f"Redis rate limiting failed, using local: {e}")

        # Fallback to local (in-process only)
        return self._check_local(key, config, cost)

    def _check_redis(
        self, key: str, config: RateLimitConfig, cost: int
    ) -> Tuple[bool, float]:
        """
        Check rate limit using Redis (distributed).

        Uses token bucket algorithm with Redis for atomic operations.
        """
        now = time.time()
        redis_key = f"ratelimit:{key}"

        # Lua script for atomic token bucket update
        lua_script = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local cost = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])

        -- Get current state
        local state = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(state[1]) or max_tokens
        local last_refill = tonumber(state[2]) or now

        -- Refill tokens based on time elapsed
        local elapsed = now - last_refill
        local refill = math.floor(elapsed * refill_rate)
        tokens = math.min(max_tokens, tokens + refill)

        -- Update last_refill time
        if refill > 0 then
            last_refill = now
        end

        -- Check if enough tokens
        if tokens >= cost then
            tokens = tokens - cost
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
            redis.call('EXPIRE', key, math.ceil(max_tokens / refill_rate))
            return {1, 0}  -- Allowed, retry_after=0
        else
            -- Not enough tokens
            local retry_after = (cost - tokens) / refill_rate
            return {0, retry_after}  -- Denied, retry_after
        end
        """

        # Calculate refill rate (tokens per second)
        refill_rate = config.max_requests / config.window_seconds

        try:
            result = self.redis_client.eval(
                lua_script,
                1,
                redis_key,
                config.burst_size,
                refill_rate,
                cost,
                now,
            )

            allowed = bool(result[0])
            retry_after = float(result[1])

            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for key '{key}': retry after {retry_after:.2f}s"
                )
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {key}", retry_after=retry_after
                )

            return (True, 0.0)

        except RateLimitExceeded:
            raise
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            raise

    def _check_local(
        self, key: str, config: RateLimitConfig, cost: int
    ) -> Tuple[bool, float]:
        """
        Check rate limit using local cache (single-process only).

        NOT suitable for distributed systems - use Redis in production.
        """
        now = time.time()

        with self._lock:
            # Get current state
            if key in self._local_cache:
                last_refill, tokens = self._local_cache[key]
            else:
                last_refill = now
                tokens = config.burst_size

            # Refill tokens
            elapsed = now - last_refill
            refill_rate = config.max_requests / config.window_seconds
            refill = int(elapsed * refill_rate)

            if refill > 0:
                tokens = min(config.burst_size, tokens + refill)
                last_refill = now

            # Check if enough tokens
            if tokens >= cost:
                tokens -= cost
                self._local_cache[key] = (last_refill, tokens)
                return (True, 0.0)
            else:
                # Not enough tokens
                retry_after = (cost - tokens) / refill_rate
                logger.warning(
                    f"Rate limit exceeded (local) for key '{key}': retry after {retry_after:.2f}s"
                )
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {key}", retry_after=retry_after
                )

    def reset_limit(self, key: str):
        """
        Reset rate limit for a key.

        Args:
            key: Rate limit key to reset
        """
        if self.redis_client:
            try:
                redis_key = f"ratelimit:{key}"
                self.redis_client.delete(redis_key)
                logger.info(f"Rate limit reset for key '{key}' in Redis")
            except Exception as e:
                logger.error(f"Error resetting Redis rate limit: {e}")

        with self._lock:
            if key in self._local_cache:
                del self._local_cache[key]
                logger.info(f"Rate limit reset for key '{key}' locally")

    def get_limit_status(self, key: str, config: Optional[RateLimitConfig] = None) -> Dict[str, any]:
        """
        Get current rate limit status for a key.

        Args:
            key: Rate limit key
            config: Rate limit configuration

        Returns:
            Dict with limit, remaining, reset_at
        """
        config = config or self.default_config
        now = time.time()

        if self.redis_client:
            try:
                redis_key = f"ratelimit:{key}"
                state = self.redis_client.hmget(redis_key, "tokens", "last_refill")

                tokens = float(state[0]) if state[0] else config.burst_size
                last_refill = float(state[1]) if state[1] else now

                # Calculate refill
                elapsed = now - last_refill
                refill_rate = config.max_requests / config.window_seconds
                refill = int(elapsed * refill_rate)
                current_tokens = min(config.burst_size, tokens + refill)

                reset_at = last_refill + config.window_seconds

                return {
                    "limit": config.max_requests,
                    "remaining": int(current_tokens),
                    "reset_at": datetime.fromtimestamp(reset_at).isoformat(),
                }
            except Exception as e:
                logger.error(f"Error getting rate limit status from Redis: {e}")

        # Fallback to local
        with self._lock:
            if key in self._local_cache:
                last_refill, tokens = self._local_cache[key]
                reset_at = last_refill + config.window_seconds
                return {
                    "limit": config.max_requests,
                    "remaining": int(tokens),
                    "reset_at": datetime.fromtimestamp(reset_at).isoformat(),
                }
            else:
                return {
                    "limit": config.max_requests,
                    "remaining": config.max_requests,
                    "reset_at": datetime.fromtimestamp(now + config.window_seconds).isoformat(),
                }


# Predefined rate limit tiers
RATE_LIMIT_TIERS = {
    # Agent execution limits
    "agent_execution_user": RateLimitConfig(max_requests=100, window_seconds=3600),  # 100/hour per user
    "agent_execution_tenant": RateLimitConfig(max_requests=1000, window_seconds=3600),  # 1000/hour per tenant
    "agent_execution_global": RateLimitConfig(max_requests=10000, window_seconds=3600),  # 10k/hour global
    # API limits
    "api_user": RateLimitConfig(max_requests=1000, window_seconds=60),  # 1000/min per user
    "api_tenant": RateLimitConfig(max_requests=10000, window_seconds=60),  # 10k/min per tenant
    "api_global": RateLimitConfig(max_requests=100000, window_seconds=60),  # 100k/min global
    # Inference limits (expensive operations)
    "inference_user": RateLimitConfig(max_requests=50, window_seconds=60),  # 50/min per user
    "inference_tenant": RateLimitConfig(max_requests=500, window_seconds=60),  # 500/min per tenant
}


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(redis_client: Optional[redis.Redis] = None) -> RateLimiter:
    """
    Get or create the global RateLimiter instance.

    Args:
        redis_client: Redis client for distributed limiting

    Returns:
        RateLimiter singleton instance
    """
    global _rate_limiter

    if _rate_limiter is None:
        _rate_limiter = RateLimiter(redis_client=redis_client)

    return _rate_limiter
