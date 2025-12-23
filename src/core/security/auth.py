"""
Authentication and Authorization Manager

Azure AD integration for:
- User authentication (OAuth 2.0, OpenID Connect)
- Service principal authentication
- Managed Identity authentication
- JWT token validation
- RBAC (Role-Based Access Control)
- Policy-based authorization (integrates with OPA)

Security:
- Token validation
- Signature verification
- Claims extraction
- Permission checking
"""

import logging
import jwt
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from msal import ConfidentialClientApplication
import requests

logger = logging.getLogger(__name__)


class AuthorizationError(Exception):
    """Raised when authorization fails."""
    pass


class User:
    """Authenticated user."""

    def __init__(
        self,
        user_id: str,
        email: str,
        name: str,
        tenant_id: Optional[str] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
    ):
        self.user_id = user_id
        self.email = email
        self.name = name
        self.tenant_id = tenant_id
        self.roles = roles or []
        self.permissions = permissions or []

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "tenant_id": self.tenant_id,
            "roles": self.roles,
            "permissions": self.permissions,
        }


class AuthManager:
    """
    Authentication and authorization manager.

    Integrates with:
    - Azure AD for user authentication
    - MSAL for OAuth 2.0 flows
    - OPA for policy-based authorization
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        use_managed_identity: bool = True,
        opa_url: Optional[str] = None,
    ):
        """
        Initialize Auth Manager.

        Args:
            tenant_id: Azure AD tenant ID
            client_id: Application client ID
            client_secret: Application client secret
            use_managed_identity: Use Azure Managed Identity
            opa_url: Open Policy Agent URL for authorization
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.use_managed_identity = use_managed_identity
        self.opa_url = opa_url

        # MSAL client for token acquisition
        self.msal_app: Optional[ConfidentialClientApplication] = None
        if client_id and client_secret and tenant_id:
            authority = f"https://login.microsoftonline.com/{tenant_id}"
            self.msal_app = ConfidentialClientApplication(
                client_id,
                authority=authority,
                client_credential=client_secret,
            )

        # Azure credential for service authentication
        self.azure_credential = (
            ManagedIdentityCredential()
            if use_managed_identity
            else DefaultAzureCredential()
        )

    def validate_jwt_token(self, token: str) -> User:
        """
        Validate JWT token and extract user info.

        Args:
            token: JWT token (Bearer token)

        Returns:
            User object

        Raises:
            AuthorizationError: If token is invalid
        """
        try:
            # Decode token without verification (to get header)
            header = jwt.get_unverified_header(token)

            # Get signing keys from Azure AD
            # (In production, cache these keys)
            jwks_url = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
            jwks_response = requests.get(jwks_url)
            jwks = jwks_response.json()

            # Find the key that matches the token's kid
            key = None
            for jwk in jwks["keys"]:
                if jwk["kid"] == header["kid"]:
                    key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
                    break

            if not key:
                raise AuthorizationError("No matching signing key found")

            # Verify and decode token
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=f"https://login.microsoftonline.com/{self.tenant_id}/v2.0",
            )

            # Extract user info from claims
            user = User(
                user_id=claims.get("oid") or claims.get("sub"),
                email=claims.get("email") or claims.get("preferred_username"),
                name=claims.get("name", "Unknown"),
                tenant_id=claims.get("tid"),
                roles=claims.get("roles", []),
            )

            logger.info(f"Token validated for user: {user.email}")
            return user

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise AuthorizationError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise AuthorizationError(f"Invalid token: {e}")
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise AuthorizationError(f"Token validation failed: {e}")

    def acquire_token_for_client(self, scopes: List[str]) -> str:
        """
        Acquire token for service-to-service authentication.

        Args:
            scopes: List of scopes to request

        Returns:
            Access token

        Raises:
            AuthorizationError: If token acquisition fails
        """
        if not self.msal_app:
            raise AuthorizationError("MSAL app not configured")

        try:
            # Try to get cached token
            result = self.msal_app.acquire_token_silent(scopes, account=None)

            if not result:
                # Acquire new token
                result = self.msal_app.acquire_token_for_client(scopes=scopes)

            if "access_token" in result:
                logger.info("Token acquired successfully")
                return result["access_token"]
            else:
                error = result.get("error")
                error_desc = result.get("error_description")
                logger.error(f"Token acquisition failed: {error} - {error_desc}")
                raise AuthorizationError(f"Failed to acquire token: {error}")

        except Exception as e:
            logger.error(f"Token acquisition error: {e}")
            raise AuthorizationError(f"Token acquisition failed: {e}")

    def check_permission(
        self, user: User, resource: str, action: str, context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if user has permission to perform action on resource.

        Integrates with OPA for policy-based authorization.

        Args:
            user: User requesting access
            resource: Resource being accessed (e.g., "agent:finance-001")
            action: Action being performed (e.g., "read", "execute", "delete")
            context: Additional context (e.g., tenant_id, ip_address)

        Returns:
            True if authorized, False otherwise

        Raises:
            AuthorizationError: If authorization check fails
        """
        # Build authorization request
        authz_request = {
            "input": {
                "user": user.to_dict(),
                "resource": resource,
                "action": action,
                "context": context or {},
            }
        }

        # Check with OPA if configured
        if self.opa_url:
            try:
                response = requests.post(
                    f"{self.opa_url}/v1/data/ants/authz/allow",
                    json=authz_request,
                    timeout=5,
                )

                if response.status_code == 200:
                    result = response.json()
                    allowed = result.get("result", False)

                    if allowed:
                        logger.info(
                            f"Authorization granted: {user.email} -> {action} on {resource}"
                        )
                    else:
                        logger.warning(
                            f"Authorization denied: {user.email} -> {action} on {resource}"
                        )

                    return allowed
                else:
                    logger.error(f"OPA authorization check failed: {response.status_code}")
                    raise AuthorizationError("Authorization service unavailable")

            except Exception as e:
                logger.error(f"OPA authorization error: {e}")
                raise AuthorizationError(f"Authorization check failed: {e}")

        # Fallback: Simple role-based check
        # (Use OPA in production for complex policies)
        logger.warning("OPA not configured, using simple role-based check")

        # Admin role has all permissions
        if user.has_role("admin"):
            return True

        # Resource-specific permissions
        # Format: "resource_type:action" (e.g., "agent:execute", "data:read")
        resource_type = resource.split(":")[0] if ":" in resource else resource
        required_permission = f"{resource_type}:{action}"

        return user.has_permission(required_permission)

    def require_permission(
        self, user: User, resource: str, action: str, context: Optional[Dict[str, Any]] = None
    ):
        """
        Require permission (raises exception if denied).

        Args:
            user: User requesting access
            resource: Resource being accessed
            action: Action being performed
            context: Additional context

        Raises:
            AuthorizationError: If user doesn't have permission
        """
        if not self.check_permission(user, resource, action, context):
            raise AuthorizationError(
                f"User {user.email} not authorized to {action} on {resource}"
            )


# Global auth manager instance
_auth_manager: Optional[AuthManager] = None


def get_auth_manager(
    tenant_id: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    use_managed_identity: bool = True,
    opa_url: Optional[str] = None,
) -> AuthManager:
    """
    Get or create the global AuthManager instance.

    Args:
        tenant_id: Azure AD tenant ID
        client_id: Application client ID
        client_secret: Application client secret
        use_managed_identity: Use Azure Managed Identity
        opa_url: OPA endpoint URL

    Returns:
        AuthManager singleton instance
    """
    global _auth_manager

    if _auth_manager is None:
        _auth_manager = AuthManager(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            use_managed_identity=use_managed_identity,
            opa_url=opa_url,
        )

    return _auth_manager
