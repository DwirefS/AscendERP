"""
Authentication and authorization middleware for ANTS API Gateway.
Supports JWT tokens and API keys.
"""
from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
import structlog
import hashlib

logger = structlog.get_logger()

# Security schemes
bearer_scheme = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Configuration (should come from environment)
JWT_SECRET = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


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
        return scope in self.scopes


class AuthService:
    """Service for authentication operations."""

    def __init__(self):
        # In production, this would be backed by database
        self.api_keys: Dict[str, Dict[str, Any]] = {
            # Example: API key -> tenant metadata
            # Format: SHA256(api_key) -> metadata
        }

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
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.utcnow()
        }

        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return token

    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    def verify_api_key(self, api_key: str) -> Dict[str, Any]:
        """Verify an API key and return tenant metadata."""
        # Hash the API key
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
        """Register a new API key (admin operation)."""
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


# Global auth service instance
auth_service = AuthService()


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header)
) -> AuthContext:
    """
    Dependency to extract and validate authentication.
    Supports both JWT tokens and API keys.
    """
    # Try API key first
    if api_key:
        logger.debug("authenticating_with_api_key")
        metadata = auth_service.verify_api_key(api_key)

        return AuthContext(
            tenant_id=metadata["tenant_id"],
            scopes=metadata.get("scopes", []),
            auth_method="api_key"
        )

    # Try JWT token
    if credentials:
        logger.debug("authenticating_with_jwt")
        token = credentials.credentials
        payload = auth_service.verify_jwt_token(token)

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
