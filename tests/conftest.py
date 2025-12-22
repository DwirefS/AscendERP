"""
ANTS Test Configuration and Fixtures.
Provides common test setup for all test modules.
"""
import pytest
import asyncio
from typing import Dict, Any, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock
from dataclasses import dataclass

# Configure pytest-asyncio
pytest_plugins = ['pytest_asyncio']


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_agent_config() -> Dict[str, Any]:
    """Sample agent configuration."""
    return {
        "agent_id": "test-agent-001",
        "name": "Test Agent",
        "description": "Agent for testing",
        "tools": ["test_tool_1", "test_tool_2"],
        "max_iterations": 5,
        "timeout_seconds": 60,
        "memory_enabled": True,
        "policy_enabled": True,
        "model_name": "test-model"
    }


@pytest.fixture
def sample_context() -> Dict[str, Any]:
    """Sample agent context."""
    return {
        "trace_id": "trace-test-001",
        "tenant_id": "tenant-test",
        "user_id": "user-test",
        "session_id": "session-test",
        "metadata": {
            "environment": "test"
        }
    }


@pytest.fixture
def mock_memory_substrate():
    """Mock memory substrate for testing."""
    memory = AsyncMock()
    memory.store_episodic = AsyncMock(return_value="entry-001")
    memory.store_semantic = AsyncMock(return_value="entry-002")
    memory.store_procedural = AsyncMock(return_value="entry-003")
    memory.retrieve_episodic = AsyncMock(return_value=[])
    memory.retrieve_semantic = AsyncMock(return_value=[])
    memory.retrieve_procedural = AsyncMock(return_value=[])
    return memory


@pytest.fixture
def mock_policy_engine():
    """Mock policy engine for testing."""
    policy = AsyncMock()
    policy.evaluate = AsyncMock(return_value={
        "decision": "ALLOW",
        "allowed": True,
        "reason": None,
        "conditions": [],
        "audit_required": True
    })
    policy.check_tool_access = AsyncMock(return_value={
        "decision": "ALLOW",
        "allowed": True
    })
    policy.check_data_access = AsyncMock(return_value={
        "decision": "ALLOW",
        "allowed": True
    })
    return policy


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value={
        "content": "Test response",
        "tokens_used": 100,
        "confidence": 0.9
    })
    llm.embed = AsyncMock(return_value=[0.1] * 1024)
    return llm


@pytest.fixture
async def mock_database():
    """Mock database connection for testing."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.fetchone = AsyncMock(return_value=None)
    return db


@pytest.fixture
def sample_transaction() -> Dict[str, Any]:
    """Sample transaction data for testing."""
    return {
        "id": "txn-001",
        "date": "2024-01-15T10:30:00Z",
        "amount": 1500.00,
        "currency": "USD",
        "account_id": "acc-001",
        "description": "Test transaction",
        "status": "completed"
    }


@pytest.fixture
def sample_alert() -> Dict[str, Any]:
    """Sample security alert for testing."""
    return {
        "alert_id": "alert-001",
        "title": "Suspicious Login Attempt",
        "description": "Multiple failed login attempts detected",
        "severity": "high",
        "category": "InitialAccess",
        "detection_source": "defender",
        "affected_users": ["user@example.com"],
        "affected_devices": ["device-001"],
        "mitre_tactics": ["TA0001"],
        "mitre_techniques": ["T1078"],
        "indicators_of_compromise": [
            {"type": "ip", "value": "192.168.1.100"}
        ],
        "timestamp": "2024-01-15T10:30:00Z"
    }


@pytest.fixture
def sample_reconciliation_request() -> Dict[str, Any]:
    """Sample reconciliation request for testing."""
    return {
        "type": "standard",
        "period_start": "2024-01-01",
        "period_end": "2024-01-31",
        "accounts": ["acc-001", "acc-002"],
        "tolerance": 0.01,
        "sources": ["erp", "bank"],
        "urgency": "normal"
    }


class MockHTTPClient:
    """Mock HTTP client for external service tests."""

    def __init__(self):
        self.responses = {}

    def add_response(self, url: str, response: Dict[str, Any]):
        self.responses[url] = response

    async def get(self, url: str) -> Dict[str, Any]:
        return self.responses.get(url, {"error": "Not found"})

    async def post(self, url: str, json: Dict[str, Any]) -> Dict[str, Any]:
        return self.responses.get(url, {"error": "Not found"})


@pytest.fixture
def mock_http_client():
    """Mock HTTP client fixture."""
    return MockHTTPClient()


# Test markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "security: mark test as security test")
