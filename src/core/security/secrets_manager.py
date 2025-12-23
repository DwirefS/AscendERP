"""
Secrets Manager

Azure Key Vault integration for secure secrets management.
Handles API keys, connection strings, certificates, and sensitive configuration.

Features:
- Lazy loading and caching
- Automatic rotation detection
- Fallback to environment variables (dev only)
- Secret versioning support
- Audit logging for secret access
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import ResourceNotFoundError
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Secure secrets management using Azure Key Vault.

    Design Principles:
    - Never log secret values
    - Cache secrets with TTL to reduce Key Vault calls
    - Fail secure: raise exception if secret not found
    - Support multiple authentication methods (MSI, Service Principal)
    - Track secret access for audit
    """

    def __init__(
        self,
        key_vault_url: Optional[str] = None,
        use_managed_identity: bool = True,
        cache_ttl_seconds: int = 3600,
        allow_env_fallback: bool = False,  # Only True in dev environments
    ):
        """
        Initialize Secrets Manager.

        Args:
            key_vault_url: Azure Key Vault URL (e.g., https://my-vault.vault.azure.net/)
            use_managed_identity: Use Azure Managed Identity for auth
            cache_ttl_seconds: How long to cache secrets (default 1 hour)
            allow_env_fallback: Allow fallback to environment variables (dev only)
        """
        self.key_vault_url = key_vault_url or os.getenv("KEY_VAULT_URL")
        self.use_managed_identity = use_managed_identity
        self.cache_ttl_seconds = cache_ttl_seconds
        self.allow_env_fallback = allow_env_fallback

        # Secret cache with expiration
        self._cache: Dict[str, tuple[Any, datetime]] = {}

        # Initialize Azure Key Vault client
        self._client: Optional[SecretClient] = None
        if self.key_vault_url:
            try:
                credential = (
                    ManagedIdentityCredential()
                    if self.use_managed_identity
                    else DefaultAzureCredential()
                )
                self._client = SecretClient(
                    vault_url=self.key_vault_url, credential=credential
                )
                logger.info(
                    f"Secrets Manager initialized with Key Vault: {self.key_vault_url}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Key Vault client: {e}")
                if not self.allow_env_fallback:
                    raise
        else:
            logger.warning("No Key Vault URL configured")
            if not self.allow_env_fallback:
                raise ValueError(
                    "KEY_VAULT_URL must be set, or allow_env_fallback=True"
                )

    def get_secret(self, secret_name: str, version: Optional[str] = None) -> str:
        """
        Retrieve a secret from Azure Key Vault.

        Args:
            secret_name: Name of the secret
            version: Specific version (optional, uses latest if not specified)

        Returns:
            Secret value as string

        Raises:
            ValueError: If secret not found and no fallback allowed
        """
        # Check cache first
        cache_key = f"{secret_name}:{version or 'latest'}"
        if cache_key in self._cache:
            value, expiry = self._cache[cache_key]
            if datetime.now() < expiry:
                logger.debug(f"Secret '{secret_name}' retrieved from cache")
                return value
            else:
                # Cache expired
                del self._cache[cache_key]

        # Try Key Vault
        if self._client:
            try:
                secret = self._client.get_secret(secret_name, version=version)
                logger.info(
                    f"Secret '{secret_name}' retrieved from Key Vault "
                    f"(version: {secret.properties.version})"
                )

                # Cache the secret
                expiry = datetime.now() + timedelta(seconds=self.cache_ttl_seconds)
                self._cache[cache_key] = (secret.value, expiry)

                return secret.value
            except ResourceNotFoundError:
                logger.warning(f"Secret '{secret_name}' not found in Key Vault")
            except Exception as e:
                logger.error(f"Error retrieving secret '{secret_name}': {e}")

        # Fallback to environment variable (dev only)
        if self.allow_env_fallback:
            env_value = os.getenv(secret_name)
            if env_value:
                logger.warning(
                    f"Secret '{secret_name}' retrieved from environment variable "
                    "(INSECURE - dev only)"
                )
                return env_value

        # Secret not found
        raise ValueError(
            f"Secret '{secret_name}' not found in Key Vault or environment"
        )

    async def get_secret_async(
        self, secret_name: str, version: Optional[str] = None
    ) -> str:
        """Async version of get_secret."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.get_secret, secret_name, version
        )

    def get_connection_string(self, service_name: str) -> str:
        """
        Get connection string for a service.

        Convention: Connection strings stored as "{service_name}-connection-string"

        Args:
            service_name: Name of service (e.g., "postgresql", "eventhub", "redis")

        Returns:
            Connection string
        """
        secret_name = f"{service_name}-connection-string"
        return self.get_secret(secret_name)

    def get_api_key(self, service_name: str) -> str:
        """
        Get API key for a service.

        Convention: API keys stored as "{service_name}-api-key"

        Args:
            service_name: Name of service (e.g., "openai", "azure-openai", "nim")

        Returns:
            API key
        """
        secret_name = f"{service_name}-api-key"
        return self.get_secret(secret_name)

    def invalidate_cache(self, secret_name: Optional[str] = None):
        """
        Invalidate secret cache.

        Args:
            secret_name: Specific secret to invalidate, or None to clear all
        """
        if secret_name:
            # Remove all versions of this secret
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(secret_name)]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"Cache invalidated for secret '{secret_name}'")
        else:
            # Clear entire cache
            self._cache.clear()
            logger.info("Entire secret cache cleared")

    def list_secrets(self) -> list[str]:
        """
        List all secret names in Key Vault.

        Returns:
            List of secret names (not values!)
        """
        if not self._client:
            return []

        try:
            return [secret.name for secret in self._client.list_properties_of_secrets()]
        except Exception as e:
            logger.error(f"Error listing secrets: {e}")
            return []


# Global singleton instance
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager(
    key_vault_url: Optional[str] = None,
    use_managed_identity: bool = True,
    allow_env_fallback: bool = False,
) -> SecretsManager:
    """
    Get or create the global SecretsManager instance.

    Args:
        key_vault_url: Azure Key Vault URL
        use_managed_identity: Use Azure Managed Identity
        allow_env_fallback: Allow environment variable fallback (dev only)

    Returns:
        SecretsManager singleton instance
    """
    global _secrets_manager

    if _secrets_manager is None:
        _secrets_manager = SecretsManager(
            key_vault_url=key_vault_url,
            use_managed_identity=use_managed_identity,
            allow_env_fallback=allow_env_fallback,
        )

    return _secrets_manager
