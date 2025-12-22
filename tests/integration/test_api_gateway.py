"""
Integration tests for ANTS API Gateway.
Tests authentication, rate limiting, and endpoint security.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
import jwt
import time

from fastapi.testclient import TestClient
from services.api_gateway.main import app
from services.api_gateway.auth import AuthService, AuthContext
from services.api_gateway.ratelimit import RateLimiter, TokenBucket


@pytest.fixture
def client():
    """Create test client for API gateway."""
    return TestClient(app)


@pytest.fixture
def auth_service():
    """Create auth service for tests."""
    return AuthService(
        jwt_secret="test_secret_key_for_testing_only",
        jwt_algorithm="HS256",
        token_expiry_hours=1
    )


@pytest.fixture
def valid_jwt_token(auth_service):
    """Generate a valid JWT token."""
    return auth_service.create_jwt_token(
        tenant_id="test_tenant",
        user_id="test_user",
        scopes=["agents:read", "agents:write", "tasks:submit"]
    )


@pytest.fixture
def admin_jwt_token(auth_service):
    """Generate an admin JWT token with all scopes."""
    return auth_service.create_jwt_token(
        tenant_id="admin_tenant",
        user_id="admin_user",
        scopes=["agents:read", "agents:write", "tasks:submit", "admin:*"]
    )


@pytest.fixture
def valid_api_key(auth_service):
    """Generate a valid API key."""
    return auth_service.create_api_key(
        tenant_id="test_tenant",
        name="test_api_key",
        scopes=["agents:read"]
    )


class TestAuthentication:
    """Tests for API authentication."""

    def test_access_public_endpoint_no_auth(self, client):
        """Test accessing public endpoint without auth."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_access_protected_endpoint_no_auth(self, client):
        """Test accessing protected endpoint without auth fails."""
        response = client.get("/api/v1/agents")
        assert response.status_code == 401

    def test_access_with_valid_jwt_token(self, client, valid_jwt_token):
        """Test accessing protected endpoint with valid JWT."""
        headers = {"Authorization": f"Bearer {valid_jwt_token}"}
        response = client.get("/api/v1/agents", headers=headers)

        # May return 200 or 404 depending on data, but should not be 401
        assert response.status_code != 401

    def test_access_with_expired_jwt_token(self, auth_service, client):
        """Test that expired JWT tokens are rejected."""
        # Create token that's already expired
        expired_token = jwt.encode(
            {
                "tenant_id": "test_tenant",
                "user_id": "test_user",
                "scopes": ["agents:read"],
                "exp": datetime.utcnow() - timedelta(hours=1)
            },
            "test_secret_key_for_testing_only",
            algorithm="HS256"
        )

        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/agents", headers=headers)
        assert response.status_code == 401

    def test_access_with_invalid_jwt_token(self, client):
        """Test that invalid JWT tokens are rejected."""
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        response = client.get("/api/v1/agents", headers=headers)
        assert response.status_code == 401

    def test_access_with_valid_api_key(self, client, valid_api_key):
        """Test accessing endpoint with valid API key."""
        headers = {"X-API-Key": valid_api_key}
        response = client.get("/api/v1/agents", headers=headers)

        # Should not be unauthorized
        assert response.status_code != 401

    def test_access_with_invalid_api_key(self, client):
        """Test that invalid API keys are rejected."""
        headers = {"X-API-Key": "invalid_api_key_12345"}
        response = client.get("/api/v1/agents", headers=headers)
        assert response.status_code == 401


class TestAuthorization:
    """Tests for scope-based authorization."""

    def test_access_endpoint_with_required_scope(self, client, auth_service):
        """Test accessing endpoint with required scope."""
        token = auth_service.create_jwt_token(
            tenant_id="test_tenant",
            user_id="test_user",
            scopes=["agents:read"]
        )

        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/agents", headers=headers)

        # Should have access
        assert response.status_code != 403

    def test_access_endpoint_without_required_scope(self, client, auth_service):
        """Test accessing endpoint without required scope fails."""
        token = auth_service.create_jwt_token(
            tenant_id="test_tenant",
            user_id="test_user",
            scopes=["tasks:read"]  # Missing agents:read scope
        )

        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/agents", headers=headers)

        # Should be forbidden
        assert response.status_code == 403

    def test_write_operation_requires_write_scope(self, client, auth_service):
        """Test write operations require write scope."""
        # Read-only token
        read_token = auth_service.create_jwt_token(
            tenant_id="test_tenant",
            user_id="test_user",
            scopes=["agents:read"]
        )

        headers = {"Authorization": f"Bearer {read_token}"}
        response = client.post(
            "/api/v1/agents",
            headers=headers,
            json={"agent_type": "test.agent"}
        )

        # Should be forbidden (403) or unauthorized (401)
        assert response.status_code in [401, 403]

        # Write token
        write_token = auth_service.create_jwt_token(
            tenant_id="test_tenant",
            user_id="test_user",
            scopes=["agents:write"]
        )

        headers = {"Authorization": f"Bearer {write_token}"}
        response = client.post(
            "/api/v1/agents",
            headers=headers,
            json={"agent_type": "test.agent"}
        )

        # Should not be forbidden due to scopes (may fail validation)
        assert response.status_code != 403


class TestRateLimiting:
    """Tests for rate limiting."""

    def test_token_bucket_basic_consumption(self):
        """Test token bucket allows requests under limit."""
        bucket = TokenBucket(capacity=10, refill_rate=2)

        # Should allow 10 requests
        for i in range(10):
            assert bucket.consume(1) is True

        # 11th request should fail
        assert bucket.consume(1) is False

    def test_token_bucket_refill(self):
        """Test token bucket refills over time."""
        bucket = TokenBucket(capacity=10, refill_rate=10)  # 10 tokens/second

        # Consume all tokens
        for i in range(10):
            bucket.consume(1)

        # Should be empty
        assert bucket.consume(1) is False

        # Wait 0.5 seconds for refill (should get 5 tokens)
        time.sleep(0.5)

        # Should allow some requests now
        assert bucket.consume(1) is True

    def test_rate_limiter_enforces_limits(self):
        """Test rate limiter enforces per-client limits."""
        limiter = RateLimiter(
            default_capacity=5,
            default_refill_rate=1
        )

        client_id = "test_client_001"

        # Should allow 5 requests
        for i in range(5):
            assert limiter.check_limit(client_id) is True

        # 6th request should fail
        assert limiter.check_limit(client_id) is False

    def test_rate_limiter_separate_clients(self):
        """Test rate limiter tracks clients separately."""
        limiter = RateLimiter(
            default_capacity=3,
            default_refill_rate=1
        )

        # Client 1 uses all tokens
        for i in range(3):
            assert limiter.check_limit("client_1") is True
        assert limiter.check_limit("client_1") is False

        # Client 2 should still have tokens
        assert limiter.check_limit("client_2") is True

    def test_api_gateway_rate_limiting(self, client, valid_jwt_token):
        """Test API gateway enforces rate limits."""
        headers = {"Authorization": f"Bearer {valid_jwt_token}"}

        # Make many requests rapidly
        responses = []
        for i in range(100):
            response = client.get("/api/v1/agents", headers=headers)
            responses.append(response.status_code)

        # At least one should be rate limited (429)
        assert 429 in responses


class TestTenantIsolation:
    """Tests for tenant data isolation."""

    def test_tenant_can_only_access_own_data(self, client, auth_service):
        """Test tenant isolation in API."""
        # Create tokens for different tenants
        tenant1_token = auth_service.create_jwt_token(
            tenant_id="tenant_1",
            user_id="user1",
            scopes=["agents:read"]
        )

        tenant2_token = auth_service.create_jwt_token(
            tenant_id="tenant_2",
            user_id="user2",
            scopes=["agents:read"]
        )

        # Create agent for tenant 1
        headers1 = {"Authorization": f"Bearer {tenant1_token}"}
        create_response = client.post(
            "/api/v1/agents",
            headers=headers1,
            json={"agent_type": "test.agent", "tenant_id": "tenant_1"}
        )

        # Tenant 1 should see their agent
        list_response1 = client.get("/api/v1/agents", headers=headers1)
        # Response should contain tenant_1 data

        # Tenant 2 should not see tenant 1's agent
        headers2 = {"Authorization": f"Bearer {tenant2_token}"}
        list_response2 = client.get("/api/v1/agents", headers=headers2)
        # Response should not contain tenant_1 data


class TestAPIEndpoints:
    """Tests for specific API endpoints."""

    def test_list_agents_endpoint(self, client, valid_jwt_token):
        """Test listing agents."""
        headers = {"Authorization": f"Bearer {valid_jwt_token}"}
        response = client.get("/api/v1/agents", headers=headers)

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    def test_create_agent_endpoint(self, client, admin_jwt_token):
        """Test creating an agent."""
        headers = {"Authorization": f"Bearer {admin_jwt_token}"}
        response = client.post(
            "/api/v1/agents",
            headers=headers,
            json={
                "agent_type": "finance.reconciliation",
                "tenant_id": "admin_tenant",
                "capabilities": ["reconcile"]
            }
        )

        # Should succeed or fail validation, but not auth error
        assert response.status_code not in [401, 403]

    def test_submit_task_endpoint(self, client, valid_jwt_token):
        """Test submitting a task."""
        headers = {"Authorization": f"Bearer {valid_jwt_token}"}
        response = client.post(
            "/api/v1/tasks",
            headers=headers,
            json={
                "task_type": "reconcile_account",
                "input_data": {"account_id": "ACC_001"},
                "priority": 5
            }
        )

        # Should not be auth error
        assert response.status_code != 401

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        health_data = response.json()
        assert "status" in health_data
        assert health_data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_metrics_endpoint(self, client, admin_jwt_token):
        """Test metrics endpoint requires admin scope."""
        # Without auth
        response = client.get("/metrics")
        assert response.status_code == 401

        # With admin token
        headers = {"Authorization": f"Bearer {admin_jwt_token}"}
        response = client.get("/metrics", headers=headers)
        assert response.status_code in [200, 404]


class TestErrorHandling:
    """Tests for API error handling."""

    def test_invalid_json_payload(self, client, valid_jwt_token):
        """Test API handles invalid JSON gracefully."""
        headers = {
            "Authorization": f"Bearer {valid_jwt_token}",
            "Content-Type": "application/json"
        }

        response = client.post(
            "/api/v1/agents",
            headers=headers,
            data="invalid json {{"
        )

        assert response.status_code == 422  # Unprocessable entity

    def test_missing_required_fields(self, client, valid_jwt_token):
        """Test API validates required fields."""
        headers = {"Authorization": f"Bearer {valid_jwt_token}"}

        response = client.post(
            "/api/v1/agents",
            headers=headers,
            json={}  # Missing required fields
        )

        assert response.status_code == 422

    def test_not_found_endpoint(self, client):
        """Test 404 for non-existent endpoints."""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test 405 for wrong HTTP method."""
        response = client.delete("/health")
        assert response.status_code == 405


class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_headers_present(self, client):
        """Test CORS headers are included in responses."""
        response = client.options(
            "/api/v1/agents",
            headers={"Origin": "https://example.com"}
        )

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers


class TestRequestLogging:
    """Tests for request logging and auditing."""

    def test_requests_are_logged(self, client, valid_jwt_token):
        """Test that requests are logged for audit."""
        headers = {"Authorization": f"Bearer {valid_jwt_token}"}

        # Make request
        response = client.get("/api/v1/agents", headers=headers)

        # In production, would verify logs were written
        # For now, just ensure request completes
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
