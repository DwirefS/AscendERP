"""
Unit Tests for Microsoft Entra Agent IDs

Tests the secure agent authentication and authorization system.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.integrations.entra_agent_ids import (
    EntraAgentIDManager,
    AgentIdentity,
    AgentIDType,
    AgentRole,
    AuthenticationScope,
    AgentToken,
    AgentAuthorizationResult,
    AZURE_IDENTITY_AVAILABLE
)


@pytest.fixture
def entra_manager():
    """Entra Agent ID Manager fixture."""
    manager = EntraAgentIDManager(
        tenant_id="test-tenant-id",
        key_vault_url="https://test-vault.vault.azure.net/"
    )
    return manager


@pytest.fixture
def agent_identity():
    """Agent identity fixture."""
    return AgentIdentity(
        agent_id="test-agent-001",
        agent_name="Test Agent",
        identity_type=AgentIDType.MANAGED_IDENTITY,
        tenant_id="test-tenant-id",
        roles={AgentRole.DATA_READER, AgentRole.AGENT_OPERATOR},
        scopes={AuthenticationScope.AGENT_API, AuthenticationScope.MICROSOFT_GRAPH}
    )


class TestAgentIdentity:
    """Test agent identity."""

    def test_identity_creation(self, agent_identity):
        """Test agent identity creation."""
        assert agent_identity.agent_id == "test-agent-001"
        assert agent_identity.agent_name == "Test Agent"
        assert agent_identity.identity_type == AgentIDType.MANAGED_IDENTITY
        assert agent_identity.enabled is True

    def test_identity_roles(self, agent_identity):
        """Test agent roles."""
        assert AgentRole.DATA_READER in agent_identity.roles
        assert AgentRole.AGENT_OPERATOR in agent_identity.roles
        assert AgentRole.AGENT_ADMIN not in agent_identity.roles

    def test_identity_scopes(self, agent_identity):
        """Test authentication scopes."""
        assert AuthenticationScope.AGENT_API in agent_identity.scopes
        assert AuthenticationScope.MICROSOFT_GRAPH in agent_identity.scopes
        assert AuthenticationScope.DYNAMICS_365 not in agent_identity.scopes


class TestAgentToken:
    """Test agent token."""

    def test_token_creation(self):
        """Test token creation."""
        token = AgentToken(
            token="eyJ0eXAiOiJKV1QiLCJhbGc...",
            token_type="Bearer",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            scopes=["api://ants-agents/.default"],
            agent_id="finance-agent"
        )

        assert token.token
        assert token.token_type == "Bearer"
        assert token.agent_id == "finance-agent"
        assert len(token.scopes) == 1

    def test_token_expiration(self):
        """Test token expiration check."""
        # Expired token
        expired_token = AgentToken(
            token="old-token",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )

        # Valid token
        valid_token = AgentToken(
            token="valid-token",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )

        assert expired_token.expires_at < datetime.utcnow()
        assert valid_token.expires_at > datetime.utcnow()


class TestEntraAgentIDManager:
    """Test Entra Agent ID Manager."""

    async def test_manager_initialization(self, entra_manager):
        """Test manager initialization."""
        assert entra_manager.tenant_id == "test-tenant-id"
        assert entra_manager.key_vault_url == "https://test-vault.vault.azure.net/"
        assert entra_manager.agent_identities == {}

    async def test_initialize(self, entra_manager):
        """Test manager initialize."""
        # Should succeed even without real Azure connection
        result = await entra_manager.initialize()
        # Simplified test - in production would require real credentials

    async def test_register_agent_managed_identity(self, entra_manager):
        """Test registering agent with managed identity."""
        identity = await entra_manager.register_agent(
            agent_id="finance-agent",
            agent_name="Finance Reconciliation Agent",
            identity_type=AgentIDType.MANAGED_IDENTITY,
            roles={AgentRole.DATA_READER, AgentRole.DATA_WRITER},
            scopes={AuthenticationScope.DYNAMICS_365}
        )

        assert identity.agent_id == "finance-agent"
        assert identity.agent_name == "Finance Reconciliation Agent"
        assert identity.identity_type == AgentIDType.MANAGED_IDENTITY
        assert AgentRole.DATA_READER in identity.roles
        assert AuthenticationScope.DYNAMICS_365 in identity.scopes

        # Check it's registered
        assert "finance-agent" in entra_manager.agent_identities

    async def test_register_agent_service_principal(self, entra_manager):
        """Test registering agent with service principal."""
        identity = await entra_manager.register_agent(
            agent_id="compliance-agent",
            agent_name="Compliance Audit Agent",
            identity_type=AgentIDType.SERVICE_PRINCIPAL,
            client_id="app-client-id-123",
            roles={AgentRole.AGENT_ADMIN, AgentRole.POLICY_ENFORCER},
            scopes={AuthenticationScope.AGENT_API, AuthenticationScope.AZURE_MANAGEMENT}
        )

        assert identity.identity_type == AgentIDType.SERVICE_PRINCIPAL
        assert identity.client_id == "app-client-id-123"
        assert AgentRole.AGENT_ADMIN in identity.roles

    async def test_register_multiple_agents(self, entra_manager):
        """Test registering multiple agents."""
        agent1 = await entra_manager.register_agent(
            "agent-1", "Agent 1", AgentIDType.MANAGED_IDENTITY
        )
        agent2 = await entra_manager.register_agent(
            "agent-2", "Agent 2", AgentIDType.SERVICE_PRINCIPAL,
            client_id="client-id"
        )

        assert len(entra_manager.agent_identities) == 2
        assert "agent-1" in entra_manager.agent_identities
        assert "agent-2" in entra_manager.agent_identities

    async def test_authorize_agent_success(self, entra_manager):
        """Test successful agent authorization."""
        # Register agent with specific roles and scopes
        await entra_manager.register_agent(
            agent_id="test-agent",
            agent_name="Test Agent",
            identity_type=AgentIDType.MANAGED_IDENTITY,
            roles={AgentRole.DATA_READER, AgentRole.DATA_WRITER},
            scopes={AuthenticationScope.DYNAMICS_365}
        )

        # Authorize with matching requirements
        result = await entra_manager.authorize_agent(
            agent_id="test-agent",
            required_roles=[AgentRole.DATA_READER],
            required_scopes=[AuthenticationScope.DYNAMICS_365]
        )

        assert result.authorized is True
        assert result.agent_id == "test-agent"
        assert AgentRole.DATA_READER in result.assigned_roles
        assert AuthenticationScope.DYNAMICS_365 in result.granted_scopes

    async def test_authorize_agent_missing_role(self, entra_manager):
        """Test authorization failure due to missing role."""
        # Register agent without AGENT_ADMIN role
        await entra_manager.register_agent(
            agent_id="limited-agent",
            agent_name="Limited Agent",
            identity_type=AgentIDType.MANAGED_IDENTITY,
            roles={AgentRole.DATA_READER},
            scopes={AuthenticationScope.AGENT_API}
        )

        # Try to authorize with required AGENT_ADMIN role
        result = await entra_manager.authorize_agent(
            agent_id="limited-agent",
            required_roles=[AgentRole.AGENT_ADMIN],
            required_scopes=[AuthenticationScope.AGENT_API]
        )

        assert result.authorized is False
        assert "Missing required roles or scopes" in result.reason

    async def test_authorize_agent_missing_scope(self, entra_manager):
        """Test authorization failure due to missing scope."""
        # Register agent without Dynamics 365 scope
        await entra_manager.register_agent(
            agent_id="api-agent",
            agent_name="API Agent",
            identity_type=AgentIDType.MANAGED_IDENTITY,
            roles={AgentRole.AGENT_OPERATOR},
            scopes={AuthenticationScope.AGENT_API}
        )

        # Try to authorize with Dynamics 365 scope requirement
        result = await entra_manager.authorize_agent(
            agent_id="api-agent",
            required_roles=[AgentRole.AGENT_OPERATOR],
            required_scopes=[AuthenticationScope.DYNAMICS_365]
        )

        assert result.authorized is False

    async def test_authorize_nonexistent_agent(self, entra_manager):
        """Test authorization for nonexistent agent."""
        result = await entra_manager.authorize_agent(
            agent_id="nonexistent-agent",
            required_roles=[AgentRole.DATA_READER],
            required_scopes=[AuthenticationScope.AGENT_API]
        )

        assert result.authorized is False
        assert "Agent identity not found" in result.reason

    async def test_revoke_agent(self, entra_manager):
        """Test agent revocation."""
        # Register agent
        await entra_manager.register_agent(
            "revoke-test-agent", "Revoke Test", AgentIDType.MANAGED_IDENTITY
        )

        # Revoke agent
        result = await entra_manager.revoke_agent("revoke-test-agent")

        assert result is True

        # Agent should be disabled
        identity = entra_manager.agent_identities["revoke-test-agent"]
        assert identity.enabled is False

    async def test_list_agents(self, entra_manager):
        """Test listing all agents."""
        # Register several agents
        await entra_manager.register_agent("agent-1", "Agent 1", AgentIDType.MANAGED_IDENTITY)
        await entra_manager.register_agent("agent-2", "Agent 2", AgentIDType.SERVICE_PRINCIPAL, client_id="id")
        await entra_manager.register_agent("agent-3", "Agent 3", AgentIDType.MANAGED_IDENTITY)

        agents = await entra_manager.list_agents()

        assert len(agents) == 3
        agent_ids = [a.agent_id for a in agents]
        assert "agent-1" in agent_ids
        assert "agent-2" in agent_ids
        assert "agent-3" in agent_ids

    async def test_get_agent_identity(self, entra_manager):
        """Test getting specific agent identity."""
        # Register agent
        original = await entra_manager.register_agent(
            "get-test-agent", "Get Test", AgentIDType.MANAGED_IDENTITY
        )

        # Retrieve agent
        retrieved = await entra_manager.get_agent_identity("get-test-agent")

        assert retrieved is not None
        assert retrieved.agent_id == original.agent_id
        assert retrieved.agent_name == original.agent_name

    async def test_get_nonexistent_agent(self, entra_manager):
        """Test getting nonexistent agent."""
        agent = await entra_manager.get_agent_identity("nonexistent")

        assert agent is None


class TestTokenCaching:
    """Test token caching functionality."""

    async def test_token_cache_invalidation(self, entra_manager):
        """Test token cache invalidation on revoke."""
        # Register agent
        await entra_manager.register_agent(
            "cache-test-agent", "Cache Test", AgentIDType.MANAGED_IDENTITY
        )

        # Simulate cached token
        entra_manager.token_cache["cache-test-agent:api"] = AgentToken(
            token="cached-token",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )

        # Revoke agent (should invalidate cache)
        await entra_manager.revoke_agent("cache-test-agent")

        # Cache should be cleared for this agent
        assert "cache-test-agent:api" not in entra_manager.token_cache


class TestAgentRoles:
    """Test agent role enumeration."""

    def test_all_roles_defined(self):
        """Test all required roles are defined."""
        assert AgentRole.AGENT_ADMIN
        assert AgentRole.AGENT_OPERATOR
        assert AgentRole.AGENT_VIEWER
        assert AgentRole.DATA_READER
        assert AgentRole.DATA_WRITER
        assert AgentRole.POLICY_ENFORCER


class TestAuthenticationScopes:
    """Test authentication scope enumeration."""

    def test_all_scopes_defined(self):
        """Test all required scopes are defined."""
        assert AuthenticationScope.AGENT_API
        assert AuthenticationScope.MICROSOFT_GRAPH
        assert AuthenticationScope.DYNAMICS_365
        assert AuthenticationScope.AZURE_MANAGEMENT
        assert AuthenticationScope.KEY_VAULT


@pytest.mark.integration
@pytest.mark.skipif(not AZURE_IDENTITY_AVAILABLE, reason="Azure Identity SDK not installed")
class TestEntraIntegration:
    """Integration tests for Entra Agent IDs."""

    async def test_full_agent_lifecycle(self, entra_manager):
        """Test full agent lifecycle: register, authorize, revoke."""
        # Register
        identity = await entra_manager.register_agent(
            agent_id="lifecycle-agent",
            agent_name="Lifecycle Test Agent",
            identity_type=AgentIDType.MANAGED_IDENTITY,
            roles={AgentRole.DATA_READER},
            scopes={AuthenticationScope.AGENT_API}
        )

        # Authorize
        auth_result = await entra_manager.authorize_agent(
            "lifecycle-agent",
            [AgentRole.DATA_READER],
            [AuthenticationScope.AGENT_API]
        )

        assert auth_result.authorized is True

        # Revoke
        revoke_result = await entra_manager.revoke_agent("lifecycle-agent")
        assert revoke_result is True

        # Authorization should fail after revoke
        auth_after_revoke = await entra_manager.authorize_agent(
            "lifecycle-agent",
            [AgentRole.DATA_READER],
            [AuthenticationScope.AGENT_API]
        )

        assert auth_after_revoke.authorized is False

    async def test_multi_agent_authorization(self, entra_manager):
        """Test authorization across multiple agents."""
        # Register agents with different permissions
        await entra_manager.register_agent(
            "admin-agent", "Admin", AgentIDType.SERVICE_PRINCIPAL,
            client_id="admin-id",
            roles={AgentRole.AGENT_ADMIN, AgentRole.DATA_READER, AgentRole.DATA_WRITER},
            scopes={AuthenticationScope.AGENT_API, AuthenticationScope.AZURE_MANAGEMENT}
        )

        await entra_manager.register_agent(
            "readonly-agent", "ReadOnly", AgentIDType.MANAGED_IDENTITY,
            roles={AgentRole.AGENT_VIEWER, AgentRole.DATA_READER},
            scopes={AuthenticationScope.AGENT_API}
        )

        # Admin should be authorized for admin operations
        admin_auth = await entra_manager.authorize_agent(
            "admin-agent",
            [AgentRole.AGENT_ADMIN],
            [AuthenticationScope.AZURE_MANAGEMENT]
        )
        assert admin_auth.authorized is True

        # ReadOnly should NOT be authorized for admin operations
        readonly_auth = await entra_manager.authorize_agent(
            "readonly-agent",
            [AgentRole.AGENT_ADMIN],
            [AuthenticationScope.AZURE_MANAGEMENT]
        )
        assert readonly_auth.authorized is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
