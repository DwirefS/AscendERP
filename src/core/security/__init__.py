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

from .secrets_manager import SecretsManager
from .input_validator import InputValidator, ValidationError
from .rate_limiter import RateLimiter, RateLimitExceeded
from .security_audit import SecurityAuditor
from .encryption import EncryptionHelper
from .auth import AuthManager, AuthorizationError

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
