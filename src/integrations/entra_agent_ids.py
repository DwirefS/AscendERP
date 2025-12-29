"""
Microsoft Entra Agent IDs - Secure Agent Authentication

Implements Microsoft Entra (Azure AD) Agent IDs for secure agent authentication
and authorization following Microsoft Agent Framework patterns.

Key Features:
- Agent Identity Management
- On-Behalf-Of (OBO) Authentication - agents acting on behalf of users
- Agent-to-Agent (A2A) Protocol - secure inter-agent communication
- Managed Identity Integration
- Role-Based Access Control (RBAC)
- Token Management and Rotation
- Azure Key Vault Integration

Reference: https://learn.microsoft.com/en-us/azure/active-directory/
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import hashlib
import secrets

try:
    from azure.identity import (
        DefaultAzureCredential,
        ManagedIdentityCredential,
        ClientSecretCredential,
        OnBehalfOfCredential
    )
    from azure.keyvault.secrets import SecretClient
    from azure.core.credentials import AccessToken
    AZURE_IDENTITY_AVAILABLE = True
except ImportError:
    AZURE_IDENTITY_AVAILABLE = False
    logging.warning(
        "Azure Identity SDK not available. Install with: pip install azure-identity azure-keyvault-secrets"
    )

from src.core.observability import tracer

logger = logging.getLogger(__name__)


class AgentIDType(Enum):
    """Types of agent identities."""
    MANAGED_IDENTITY = "managed_identity"  # System-assigned or user-assigned
    SERVICE_PRINCIPAL = "service_principal"  # Application registration
    ON_BEHALF_OF = "on_behalf_of"  # Acting on behalf of user
    AGENT_TO_AGENT = "agent_to_agent"  # Inter-agent authentication


class AgentRole(Enum):
    """Agent roles for RBAC."""
    AGENT_ADMIN = "agent_admin"  # Full agent management
    AGENT_OPERATOR = "agent_operator"  # Execute agent tasks
    AGENT_VIEWER = "agent_viewer"  # Read-only access
    DATA_READER = "data_reader"  # Read data sources
    DATA_WRITER = "data_writer"  # Write to data sources
    POLICY_ENFORCER = "policy_enforcer"  # Enforce policies


class AuthenticationScope(Enum):
    """Authentication scopes."""
    AGENT_API = "api://ants-agents/.default"
    MICROSOFT_GRAPH = "https://graph.microsoft.com/.default"
    DYNAMICS_365 = "https://dynamics.microsoft.com/.default"
    AZURE_MANAGEMENT = "https://management.azure.com/.default"
    KEY_VAULT = "https://vault.azure.net/.default"


@dataclass
class AgentIdentity:
    """Agent identity configuration."""
    agent_id: str
    agent_name: str
    identity_type: AgentIDType
    tenant_id: str
    client_id: Optional[str] = None  # For service principal
    object_id: Optional[str] = None  # Entra object ID
    roles: Set[AgentRole] = field(default_factory=set)
    scopes: Set[AuthenticationScope] = field(default_factory=set)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCredential:
    """Agent credential information."""
    credential_id: str
    agent_id: str
    credential_type: str  # "managed_identity", "client_secret", "certificate"
    key_vault_secret_name: Optional[str] = None
    expires_at: Optional[datetime] = None
    rotation_policy: str = "30_days"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentToken:
    """Agent access token."""
    token: str
    token_type: str = "Bearer"
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))
    scopes: List[str] = field(default_factory=list)
    agent_id: Optional[str] = None
    user_id: Optional[str] = None  # For OBO tokens
    claims: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentAuthorizationResult:
    """Authorization check result."""
    authorized: bool
    agent_id: str
    required_roles: List[AgentRole]
    assigned_roles: List[AgentRole]
    required_scopes: List[AuthenticationScope]
    granted_scopes: List[AuthenticationScope]
    reason: str = ""


class EntraAgentIDManager:
    """
    Microsoft Entra Agent ID Manager.

    Manages agent identities, authentication, and authorization using
    Microsoft Entra ID (Azure Active Directory).

    Example:
        ```python
        # Initialize manager
        manager = EntraAgentIDManager(
            tenant_id="your-tenant-id",
            key_vault_url="https://your-vault.vault.azure.net/"
        )
        await manager.initialize()

        # Register agent identity
        identity = await manager.register_agent(
            agent_id="finance-reconciliation-agent",
            agent_name="Finance Reconciliation Agent",
            identity_type=AgentIDType.MANAGED_IDENTITY,
            roles={AgentRole.DATA_READER, AgentRole.DATA_WRITER},
            scopes={AuthenticationScope.DYNAMICS_365}
        )

        # Get token for agent
        token = await manager.get_agent_token(
            agent_id="finance-reconciliation-agent",
            scopes=[AuthenticationScope.DYNAMICS_365]
        )

        # OBO authentication - agent acting on behalf of user
        obo_token = await manager.get_obo_token(
            agent_id="finance-reconciliation-agent",
            user_token="user-access-token",
            scopes=[AuthenticationScope.MICROSOFT_GRAPH]
        )

        # Agent-to-Agent authentication
        a2a_token = await manager.get_agent_to_agent_token(
            source_agent_id="finance-agent",
            target_agent_id="compliance-agent"
        )
        ```
    """

    def __init__(
        self,
        tenant_id: str,
        key_vault_url: Optional[str] = None,
        credential: Optional[Any] = None
    ):
        """
        Initialize Entra Agent ID Manager.

        Args:
            tenant_id: Azure AD tenant ID
            key_vault_url: Azure Key Vault URL for secrets
            credential: Azure credential (defaults to DefaultAzureCredential)
        """
        if not AZURE_IDENTITY_AVAILABLE:
            raise ImportError(
                "Azure Identity SDK required. Install: pip install azure-identity azure-keyvault-secrets"
            )

        self.tenant_id = tenant_id
        self.key_vault_url = key_vault_url
        self.credential = credential or DefaultAzureCredential()

        self.agent_identities: Dict[str, AgentIdentity] = {}
        self.agent_credentials: Dict[str, AgentCredential] = {}
        self.token_cache: Dict[str, AgentToken] = {}

        self._key_vault_client: Optional[SecretClient] = None

        logger.info("EntraAgentIDManager initialized", tenant_id=tenant_id)

    async def initialize(self) -> bool:
        """
        Initialize Entra Agent ID Manager.

        Returns:
            True if successful
        """
        with tracer.start_as_current_span("entra.initialize"):
            try:
                # Initialize Key Vault client if URL provided
                if self.key_vault_url:
                    self._key_vault_client = SecretClient(
                        vault_url=self.key_vault_url,
                        credential=self.credential
                    )
                    logger.info("Key Vault client initialized", vault_url=self.key_vault_url)

                logger.info("Entra Agent ID Manager initialized successfully")
                return True

            except Exception as e:
                logger.error(f"Failed to initialize Entra Agent ID Manager: {e}")
                return False

    async def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        identity_type: AgentIDType,
        roles: Optional[Set[AgentRole]] = None,
        scopes: Optional[Set[AuthenticationScope]] = None,
        client_id: Optional[str] = None,
        **kwargs
    ) -> AgentIdentity:
        """
        Register a new agent identity.

        Args:
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            identity_type: Type of agent identity
            roles: Agent roles for RBAC
            scopes: Authentication scopes
            client_id: Client ID (for service principal)
            **kwargs: Additional identity metadata

        Returns:
            Registered agent identity
        """
        with tracer.start_as_current_span("entra.register_agent") as span:
            span.set_attribute("agent.id", agent_id)
            span.set_attribute("identity.type", identity_type.value)

            identity = AgentIdentity(
                agent_id=agent_id,
                agent_name=agent_name,
                identity_type=identity_type,
                tenant_id=self.tenant_id,
                client_id=client_id,
                roles=roles or set(),
                scopes=scopes or set(),
                metadata=kwargs
            )

            self.agent_identities[agent_id] = identity

            logger.info(
                f"Registered agent identity: {agent_name}",
                agent_id=agent_id,
                type=identity_type.value,
                roles=[r.value for r in identity.roles]
            )

            return identity

    async def get_agent_token(
        self,
        agent_id: str,
        scopes: List[AuthenticationScope],
        force_refresh: bool = False
    ) -> AgentToken:
        """
        Get access token for agent.

        Args:
            agent_id: Agent identifier
            scopes: Required authentication scopes
            force_refresh: Force token refresh

        Returns:
            Agent access token
        """
        with tracer.start_as_current_span("entra.get_agent_token") as span:
            span.set_attribute("agent.id", agent_id)
            span.set_attribute("scopes", [s.value for s in scopes])

            # Check cache
            cache_key = f"{agent_id}:{':'.join(s.value for s in scopes)}"
            if not force_refresh and cache_key in self.token_cache:
                cached_token = self.token_cache[cache_key]
                if cached_token.expires_at > datetime.utcnow() + timedelta(minutes=5):
                    logger.debug(f"Using cached token for {agent_id}")
                    return cached_token

            # Get identity
            if agent_id not in self.agent_identities:
                raise ValueError(f"Agent identity not found: {agent_id}")

            identity = self.agent_identities[agent_id]

            # Get credential based on identity type
            if identity.identity_type == AgentIDType.MANAGED_IDENTITY:
                credential = ManagedIdentityCredential(client_id=identity.client_id)
            elif identity.identity_type == AgentIDType.SERVICE_PRINCIPAL:
                # Retrieve secret from Key Vault
                if not self._key_vault_client:
                    raise ValueError("Key Vault required for service principal auth")
                secret_name = f"agent-{agent_id}-secret"
                secret = self._key_vault_client.get_secret(secret_name)
                credential = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=identity.client_id,
                    client_secret=secret.value
                )
            else:
                raise ValueError(f"Unsupported identity type for token: {identity.identity_type}")

            # Get token
            scope_strings = [s.value for s in scopes]
            access_token = credential.get_token(*scope_strings)

            # Create agent token
            agent_token = AgentToken(
                token=access_token.token,
                expires_at=datetime.fromtimestamp(access_token.expires_on),
                scopes=scope_strings,
                agent_id=agent_id
            )

            # Cache token
            self.token_cache[cache_key] = agent_token

            logger.info(
                f"Generated token for agent: {agent_id}",
                scopes=scope_strings,
                expires_in_minutes=(agent_token.expires_at - datetime.utcnow()).total_seconds() / 60
            )

            return agent_token

    async def get_obo_token(
        self,
        agent_id: str,
        user_token: str,
        scopes: List[AuthenticationScope]
    ) -> AgentToken:
        """
        Get On-Behalf-Of (OBO) token for agent acting on behalf of user.

        Args:
            agent_id: Agent identifier
            user_token: User's access token
            scopes: Required scopes

        Returns:
            OBO access token
        """
        with tracer.start_as_current_span("entra.get_obo_token") as span:
            span.set_attribute("agent.id", agent_id)
            span.set_attribute("scopes", [s.value for s in scopes])

            # Get identity
            if agent_id not in self.agent_identities:
                raise ValueError(f"Agent identity not found: {agent_id}")

            identity = self.agent_identities[agent_id]

            if not identity.client_id:
                raise ValueError("Client ID required for OBO authentication")

            # Retrieve client secret from Key Vault
            if not self._key_vault_client:
                raise ValueError("Key Vault required for OBO authentication")

            secret_name = f"agent-{agent_id}-secret"
            secret = self._key_vault_client.get_secret(secret_name)

            # Create OBO credential
            obo_credential = OnBehalfOfCredential(
                tenant_id=self.tenant_id,
                client_id=identity.client_id,
                client_secret=secret.value,
                user_assertion=user_token
            )

            # Get OBO token
            scope_strings = [s.value for s in scopes]
            access_token = obo_credential.get_token(*scope_strings)

            # Create agent token
            agent_token = AgentToken(
                token=access_token.token,
                expires_at=datetime.fromtimestamp(access_token.expires_on),
                scopes=scope_strings,
                agent_id=agent_id,
                claims={"auth_type": "obo"}
            )

            logger.info(
                f"Generated OBO token for agent: {agent_id}",
                scopes=scope_strings
            )

            return agent_token

    async def get_agent_to_agent_token(
        self,
        source_agent_id: str,
        target_agent_id: str,
        scopes: Optional[List[AuthenticationScope]] = None
    ) -> AgentToken:
        """
        Get Agent-to-Agent (A2A) authentication token.

        Enables secure communication between agents.

        Args:
            source_agent_id: Source agent identifier
            target_agent_id: Target agent identifier
            scopes: Optional scopes (defaults to agent API scope)

        Returns:
            A2A access token
        """
        with tracer.start_as_current_span("entra.get_a2a_token") as span:
            span.set_attribute("source_agent.id", source_agent_id)
            span.set_attribute("target_agent.id", target_agent_id)

            # Verify both agents exist
            if source_agent_id not in self.agent_identities:
                raise ValueError(f"Source agent not found: {source_agent_id}")
            if target_agent_id not in self.agent_identities:
                raise ValueError(f"Target agent not found: {target_agent_id}")

            # Default to agent API scope
            scopes = scopes or [AuthenticationScope.AGENT_API]

            # Get source agent token
            source_token = await self.get_agent_token(source_agent_id, scopes)

            # Add A2A claims
            source_token.claims.update({
                "auth_type": "agent_to_agent",
                "source_agent": source_agent_id,
                "target_agent": target_agent_id
            })

            logger.info(
                f"Generated A2A token: {source_agent_id} -> {target_agent_id}",
                scopes=[s.value for s in scopes]
            )

            return source_token

    async def authorize_agent(
        self,
        agent_id: str,
        required_roles: List[AgentRole],
        required_scopes: List[AuthenticationScope]
    ) -> AgentAuthorizationResult:
        """
        Authorize agent for operation.

        Checks if agent has required roles and scopes.

        Args:
            agent_id: Agent identifier
            required_roles: Required roles
            required_scopes: Required scopes

        Returns:
            Authorization result
        """
        with tracer.start_as_current_span("entra.authorize_agent") as span:
            span.set_attribute("agent.id", agent_id)

            if agent_id not in self.agent_identities:
                return AgentAuthorizationResult(
                    authorized=False,
                    agent_id=agent_id,
                    required_roles=required_roles,
                    assigned_roles=[],
                    required_scopes=required_scopes,
                    granted_scopes=[],
                    reason="Agent identity not found"
                )

            identity = self.agent_identities[agent_id]

            # Check if agent is enabled
            if not identity.enabled:
                return AgentAuthorizationResult(
                    authorized=False,
                    agent_id=agent_id,
                    required_roles=required_roles,
                    assigned_roles=list(identity.roles),
                    required_scopes=required_scopes,
                    granted_scopes=list(identity.scopes),
                    reason="Agent identity is disabled"
                )

            # Check roles
            has_required_roles = all(role in identity.roles for role in required_roles)

            # Check scopes
            has_required_scopes = all(scope in identity.scopes for scope in required_scopes)

            # Determine authorization
            authorized = has_required_roles and has_required_scopes

            result = AgentAuthorizationResult(
                authorized=authorized,
                agent_id=agent_id,
                required_roles=required_roles,
                assigned_roles=list(identity.roles),
                required_scopes=required_scopes,
                granted_scopes=list(identity.scopes),
                reason="Authorized" if authorized else "Missing required roles or scopes"
            )

            span.set_attribute("authorized", authorized)

            logger.info(
                f"Authorization check for {agent_id}: {authorized}",
                reason=result.reason
            )

            return result

    async def rotate_agent_credential(
        self,
        agent_id: str
    ) -> AgentCredential:
        """
        Rotate agent credential.

        Generates new credential and stores in Key Vault.

        Args:
            agent_id: Agent identifier

        Returns:
            New agent credential
        """
        with tracer.start_as_current_span("entra.rotate_credential"):
            if agent_id not in self.agent_identities:
                raise ValueError(f"Agent identity not found: {agent_id}")

            if not self._key_vault_client:
                raise ValueError("Key Vault required for credential rotation")

            # Generate new secret
            new_secret = secrets.token_urlsafe(32)
            secret_name = f"agent-{agent_id}-secret"

            # Store in Key Vault
            self._key_vault_client.set_secret(secret_name, new_secret)

            # Create credential record
            credential = AgentCredential(
                credential_id=f"cred-{secrets.token_hex(8)}",
                agent_id=agent_id,
                credential_type="client_secret",
                key_vault_secret_name=secret_name,
                expires_at=datetime.utcnow() + timedelta(days=30)
            )

            self.agent_credentials[credential.credential_id] = credential

            # Invalidate cached tokens
            self._invalidate_agent_tokens(agent_id)

            logger.info(
                f"Rotated credential for agent: {agent_id}",
                credential_id=credential.credential_id
            )

            return credential

    async def revoke_agent(self, agent_id: str) -> bool:
        """
        Revoke agent identity.

        Args:
            agent_id: Agent identifier

        Returns:
            True if successful
        """
        with tracer.start_as_current_span("entra.revoke_agent"):
            if agent_id not in self.agent_identities:
                return False

            # Disable identity
            self.agent_identities[agent_id].enabled = False

            # Invalidate tokens
            self._invalidate_agent_tokens(agent_id)

            logger.warning(f"Revoked agent identity: {agent_id}")

            return True

    def _invalidate_agent_tokens(self, agent_id: str):
        """Invalidate all cached tokens for an agent."""
        keys_to_remove = [
            key for key in self.token_cache.keys()
            if key.startswith(f"{agent_id}:")
        ]
        for key in keys_to_remove:
            del self.token_cache[key]

        logger.debug(f"Invalidated {len(keys_to_remove)} tokens for agent: {agent_id}")

    async def list_agents(self) -> List[AgentIdentity]:
        """List all registered agent identities."""
        return list(self.agent_identities.values())

    async def get_agent_identity(self, agent_id: str) -> Optional[AgentIdentity]:
        """Get agent identity by ID."""
        return self.agent_identities.get(agent_id)


async def demo_entra_agent_ids():
    """Demonstrate Entra Agent IDs."""
    print("=" * 80)
    print("Microsoft Entra Agent IDs Demo")
    print("=" * 80)
    print()

    # Initialize manager
    print("1. Initializing Entra Agent ID Manager...")
    manager = EntraAgentIDManager(
        tenant_id="your-tenant-id",
        key_vault_url="https://your-vault.vault.azure.net/"
    )
    # Note: initialize() requires real Azure credentials
    # await manager.initialize()
    print("   ✓ Manager initialized")
    print()

    # Register agent with managed identity
    print("2. Registering Finance Agent with Managed Identity...")
    finance_agent = await manager.register_agent(
        agent_id="finance-reconciliation-agent",
        agent_name="Finance Reconciliation Agent",
        identity_type=AgentIDType.MANAGED_IDENTITY,
        roles={AgentRole.DATA_READER, AgentRole.DATA_WRITER},
        scopes={AuthenticationScope.DYNAMICS_365, AuthenticationScope.MICROSOFT_GRAPH}
    )
    print(f"   ✓ Registered: {finance_agent.agent_name}")
    print(f"   Roles: {[r.value for r in finance_agent.roles]}")
    print(f"   Scopes: {[s.value for s in finance_agent.scopes]}")
    print()

    # Register agent with service principal
    print("3. Registering Compliance Agent with Service Principal...")
    compliance_agent = await manager.register_agent(
        agent_id="compliance-audit-agent",
        agent_name="Compliance Audit Agent",
        identity_type=AgentIDType.SERVICE_PRINCIPAL,
        client_id="app-client-id-here",
        roles={AgentRole.AGENT_ADMIN, AgentRole.POLICY_ENFORCER},
        scopes={AuthenticationScope.AGENT_API, AuthenticationScope.AZURE_MANAGEMENT}
    )
    print(f"   ✓ Registered: {compliance_agent.agent_name}")
    print()

    # Authorization check
    print("4. Authorizing Finance Agent for Dynamics 365 access...")
    auth_result = await manager.authorize_agent(
        agent_id="finance-reconciliation-agent",
        required_roles=[AgentRole.DATA_READER],
        required_scopes=[AuthenticationScope.DYNAMICS_365]
    )
    print(f"   ✓ Authorized: {auth_result.authorized}")
    print(f"   Reason: {auth_result.reason}")
    print()

    # List all agents
    print("5. Listing all agent identities...")
    agents = await manager.list_agents()
    print(f"   ✓ Total agents: {len(agents)}")
    for agent in agents:
        print(f"   - {agent.agent_name} ({agent.identity_type.value})")
    print()

    print("=" * 80)
    print("✓ Entra Agent IDs Demo Complete")
    print("=" * 80)
    print()
    print("Note: Full functionality requires:")
    print("  - Valid Azure tenant ID")
    print("  - Azure Key Vault")
    print("  - Managed identities or service principals")
    print("  - Proper RBAC assignments")


if __name__ == "__main__":
    asyncio.run(demo_entra_agent_ids())
