"""
Security Module

Comprehensive security hardening for ANTS:
- Secrets management (Azure Key Vault)
- Input validation and sanitization
- Rate limiting and throttling
- Security audit logging
- Encryption helpers
- Authentication and authorization

Philosophy:
- Defense in depth
- Zero trust architecture
- Fail secure by default
- Comprehensive audit trail
"""

from .input_validator import InputValidator, ValidationError
from .rate_limiter import RateLimiter, RateLimitExceeded
from .security_audit import SecurityAuditor
from .encryption import EncryptionHelper

# Azure/MSAL-backed modules are optional (pip install "ants[azure]").
try:
    from .secrets_manager import SecretsManager
    from .auth import AuthManager, AuthorizationError
except ImportError:  # pragma: no cover - azure extra not installed
    SecretsManager = None
    AuthManager = None

    class AuthorizationError(Exception):
        """Raised when authorization fails (azure extra not installed)."""

__all__ = [
    "SecretsManager",
    "InputValidator",
    "ValidationError",
    "RateLimiter",
    "RateLimitExceeded",
    "SecurityAuditor",
    "EncryptionHelper",
    "AuthManager",
    "AuthorizationError",
]
