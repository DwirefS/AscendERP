"""
Authentication and authorization middleware for ANTS API Gateway.
Supports JWT tokens and API keys.
"""
from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
import os
import secrets as _secrets
import structlog
import hashlib

logger = structlog.get_logger()

# Security schemes. auto_error=False so that missing credentials produce a
# 401 from our handlers (HTTPBearer's built-in error is a 403, which
# conflates "not authenticated" with "not authorized").
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Default configuration. ANTS_JWT_SECRET must be set in production; without
# it a random per-process secret is generated so tokens never validate across
# restarts or replicas (safe-by-default for local development).
DEFAULT_JWT_SECRET = os.getenv("ANTS_JWT_SECRET")
if not DEFAULT_JWT_SECRET:
    DEFAULT_JWT_SECRET = _secrets.token_urlsafe(48)
    logger.warning(
        "jwt_secret_generated",
        msg="ANTS_JWT_SECRET not set; using ephemeral secret (dev only)"
    )
DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_JWT_EXPIRATION_HOURS = 24

# Backwards-compatible module aliases
JWT_SECRET = DEFAULT_JWT_SECRET
JWT_ALGORITHM = DEFAULT_JWT_ALGORITHM
JWT_EXPIRATION_HOURS = DEFAULT_JWT_EXPIRATION_HOURS


class AuthContext:
    """Authentication context for requests."""
    def __init__(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        scopes: list[str] = None,
        auth_method: str = "jwt"
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.scopes = scopes or []
        self.auth_method = auth_method
        self.authenticated_at = datetime.utcnow()

    def has_scope(self, scope: str) -> bool:
        """Check if auth context has required scope."""
        if scope in self.scopes:
            return True
        # admin:* grants everything; "agents:*" grants "agents:read" etc.
        for held in self.scopes:
            if held == "admin:*":
                return True
            if held.endswith(":*") and scope.startswith(held[:-1]):
                return True
        return False


class AuthService:
    """
    Service for authentication operations.

    The gateway resolves credentials against ``AuthService.current`` — the
    most recently constructed instance. Constructing an AuthService with an
    explicit ``jwt_secret`` therefore reconfigures process-wide auth, which
    is how tests (and embedded deployments) inject their own secret.
    """

    current: "AuthService" = None  # set in __init__

    def __init__(
        self,
        jwt_secret: Optional[str] = None,
        jwt_algorithm: Optional[str] = None,
        token_expiry_hours: Optional[int] = None,
    ):
        self.jwt_secret = jwt_secret or DEFAULT_JWT_SECRET
        self.jwt_algorithm = jwt_algorithm or DEFAULT_JWT_ALGORITHM
        self.token_expiry_hours = token_expiry_hours or DEFAULT_JWT_EXPIRATION_HOURS

        # In production, this would be backed by database
        # Format: SHA256(api_key) -> metadata
        self.api_keys: Dict[str, Dict[str, Any]] = {}

        AuthService.current = self

    def create_jwt_token(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        scopes: list[str] = None
    ) -> str:
        """Create a JWT token for a tenant/user."""
        payload = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "scopes": scopes or ["agent:invoke", "memory:read"],
            "exp": datetime.utcnow() + timedelta(hours=self.token_expiry_hours),
            "iat": datetime.utcnow(),
            # Unique token id: enables revocation/audit and per-session
            # rate limiting at the gateway.
            "jti": _secrets.token_hex(8),
        }

        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        return token

    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    def create_api_key(
        self,
        tenant_id: str,
        name: str = "",
        scopes: list[str] = None
    ) -> str:
        """
        Create and register a new API key. Returns the raw key — it is
        stored only as a SHA256 hash and cannot be recovered later.
        """
        api_key = f"ants_{_secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        self.api_keys[key_hash] = {
            "tenant_id": tenant_id,
            "name": name,
            "scopes": scopes or ["agent:invoke", "memory:read"],
            "created_at": datetime.utcnow().isoformat()
        }

        logger.info(
            "api_key_created",
            tenant_id=tenant_id,
            name=name,
            key_hash=key_hash[:8]
        )
        return api_key

    def verify_api_key(self, api_key: str) -> Dict[str, Any]:
        """Verify an API key and return tenant metadata."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        metadata = self.api_keys.get(key_hash)
        if not metadata:
            raise HTTPException(status_code=401, detail="Invalid API key")

        return metadata

    def register_api_key(
        self,
        api_key: str,
        tenant_id: str,
        scopes: list[str] = None
    ):
        """Register an externally generated API key (admin operation)."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        self.api_keys[key_hash] = {
            "tenant_id": tenant_id,
            "scopes": scopes or ["agent:invoke", "memory:read"],
            "created_at": datetime.utcnow().isoformat()
        }

        logger.info(
            "api_key_registered",
            tenant_id=tenant_id,
            key_hash=key_hash[:8]
        )


# Global auth service instance (also becomes AuthService.current)
auth_service = AuthService()


async def get_auth_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header)
) -> AuthContext:
    """
    Dependency to extract and validate authentication.
    Supports both JWT tokens and API keys.
    """
    service = AuthService.current or auth_service

    # Try API key first
    if api_key:
        logger.debug("authenticating_with_api_key")
        metadata = service.verify_api_key(api_key)

        return AuthContext(
            tenant_id=metadata["tenant_id"],
            scopes=metadata.get("scopes", []),
            auth_method="api_key"
        )

    # Try JWT token
    if credentials:
        logger.debug("authenticating_with_jwt")
        token = credentials.credentials
        payload = service.verify_jwt_token(token)

        return AuthContext(
            tenant_id=payload["tenant_id"],
            user_id=payload.get("user_id"),
            scopes=payload.get("scopes", []),
            auth_method="jwt"
        )

    raise HTTPException(status_code=401, detail="No authentication credentials provided")


async def get_optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header)
) -> Optional[AuthContext]:
    """
    Optional authentication dependency.
    Returns None if no credentials provided.
    """
    try:
        return await get_auth_context(credentials, api_key)
    except HTTPException:
        return None


def require_scope(required_scope: str):
    """
    Dependency factory to require specific scope.
    Usage: auth = Depends(require_scope("agent:invoke"))
    """
    async def scope_checker(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not auth.has_scope(required_scope):
            raise HTTPException(
                status_code=403,
                detail=f"Missing required scope: {required_scope}"
            )
        return auth

    return scope_checker


def require_tenant(tenant_id: str):
    """
    Dependency factory to require specific tenant.
    Useful for path parameters validation.
    """
    async def tenant_checker(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if auth.tenant_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Tenant mismatch"
            )
        return auth

    return tenant_checker


async def log_auth_event(request: Request, auth: AuthContext):
    """Log authentication event for audit."""
    logger.info(
        "api_request_authenticated",
        method=request.method,
        path=request.url.path,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        auth_method=auth.auth_method,
        client_ip=request.client.host
    )
