"""
Unit Tests for Semantic Kernel Integration

Tests the Microsoft Semantic Kernel integration with ANTS agents.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.integrations.semantic_kernel_integration import (
    ANTSSemanticKernel,
    ANTSPluginBuilder,
    SemanticKernelConfig,
    create_finance_plugin,
    SK_AVAILABLE
)


@pytest.fixture
def sk_config():
    """Semantic Kernel configuration fixture."""
    return SemanticKernelConfig(
        deployment_name="gpt-4",
        endpoint="https://test.openai.azure.com",
        api_key="test-key",
        embedding_deployment="text-embedding-ada-002",
        enable_planner=True
    )


@pytest.fixture
def mock_kernel():
    """Mock Semantic Kernel."""
    kernel = MagicMock()
    kernel.create_new_context.return_value = {}
    kernel.plugins = {}
    return kernel


class TestSemanticKernelConfig:
    """Test Semantic Kernel configuration."""

    def test_config_creation(self, sk_config):
        """Test configuration creation."""
        assert sk_config.deployment_name == "gpt-4"
        assert sk_config.enable_planner is True
        assert sk_config.max_tokens == 2048
        assert sk_config.temperature == 0.7

    def test_config_from_env(self, monkeypatch):
        """Test configuration from environment variables."""
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4-turbo")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://prod.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "prod-key")

        config = SemanticKernelConfig.from_env()

        assert config.deployment_name == "gpt-4-turbo"
        assert config.endpoint == "https://prod.openai.azure.com"
        assert config.api_key == "prod-key"


@pytest.mark.skipif(not SK_AVAILABLE, reason="Semantic Kernel not installed")
class TestANTSSemanticKernel:
    """Test ANTS Semantic Kernel integration."""

    @patch('src.integrations.semantic_kernel_integration.sk.Kernel')
    def test_initialization(self, mock_kernel_class, sk_config):
        """Test Semantic Kernel initialization."""
        mock_kernel_class.return_value = mock_kernel()

        sk_instance = ANTSSemanticKernel(sk_config)

        assert sk_instance.config == sk_config
        assert sk_instance.kernel is not None

    @patch('src.integrations.semantic_kernel_integration.sk.Kernel')
    async def test_register_ants_plugin(self, mock_kernel_class, sk_config):
        """Test registering ANTS plugin."""
        mock_kernel_instance = mock_kernel()
        mock_kernel_class.return_value = mock_kernel_instance

        sk_instance = ANTSSemanticKernel(sk_config)

        # Create test plugin
        async def test_function(input: str) -> str:
            """Test function"""
            return f"processed: {input}"

        plugin_functions = {
            "test_function": test_function
        }

        # Register plugin
        sk_instance.register_ants_plugin("test_plugin", plugin_functions)

        # Verify plugin registered (in real SK, would check kernel.plugins)
        # Here we just verify no exceptions raised

    @patch('src.integrations.semantic_kernel_integration.sk.Kernel')
    @patch('src.integrations.semantic_kernel_integration.SequentialPlanner')
    async def test_create_plan(self, mock_planner_class, mock_kernel_class, sk_config):
        """Test plan creation."""
        mock_kernel_instance = mock_kernel()
        mock_kernel_class.return_value = mock_kernel_instance

        mock_planner = AsyncMock()
        mock_plan = MagicMock()
        mock_plan._steps = []
        mock_planner.create_plan.return_value = mock_plan
        mock_planner_class.return_value = mock_planner

        sk_instance = ANTSSemanticKernel(sk_config)
        sk_instance.planner = mock_planner

        # Create plan
        plan = await sk_instance.create_plan("Test goal")

        assert plan["goal"] == "Test goal"
        assert "steps" in plan
        assert "plan" in plan
        mock_planner.create_plan.assert_called_once()

    @patch('src.integrations.semantic_kernel_integration.sk.Kernel')
    async def test_render_prompt(self, mock_kernel_class, sk_config):
        """Test prompt template rendering."""
        mock_kernel_instance = mock_kernel()
        mock_kernel_class.return_value = mock_kernel_instance

        sk_instance = ANTSSemanticKernel(sk_config)

        # Mock prompt template
        with patch('src.integrations.semantic_kernel_integration.sk.PromptTemplate') as mock_template:
            mock_template_instance = AsyncMock()
            mock_template_instance.render.return_value = "Rendered prompt: test value"
            mock_template.return_value = mock_template_instance

            result = await sk_instance.render_prompt(
                "Test {{variable}}",
                {"variable": "test value"}
            )

            assert result == "Rendered prompt: test value"


class TestANTSPluginBuilder:
    """Test ANTS Plugin Builder."""

    def test_plugin_builder_creation(self):
        """Test plugin builder creation."""
        builder = ANTSPluginBuilder("test_plugin")

        assert builder.plugin_name == "test_plugin"
        assert builder.functions == {}

    def test_add_function(self):
        """Test adding function to plugin."""
        builder = ANTSPluginBuilder("test_plugin")

        def test_func():
            """Test function"""
            return "test"

        builder.add_function("test", test_func, "Test description")

        assert "test" in builder.functions
        assert builder.functions["test"] == test_func
        assert builder.functions["test"].__doc__ == "Test description"

    def test_build_plugin(self):
        """Test building plugin."""
        builder = ANTSPluginBuilder("test_plugin")

        def func1():
            return "1"

        def func2():
            return "2"

        builder.add_function("func1", func1)
        builder.add_function("func2", func2)

        plugin = builder.build()

        assert len(plugin) == 2
        assert "func1" in plugin
        assert "func2" in plugin


class TestFinancePlugin:
    """Test finance plugin creation."""

    async def test_create_finance_plugin(self):
        """Test finance plugin creation."""
        plugin = create_finance_plugin()

        assert "reconcile_invoice" in plugin
        assert "calculate_variance" in plugin
        assert "approve_payment" in plugin

    async def test_reconcile_invoice(self):
        """Test invoice reconciliation function."""
        plugin = create_finance_plugin()
        reconcile = plugin["reconcile_invoice"]

        result = await reconcile("INV-001", "ACME Corp")

        assert "INV-001" in result
        assert "ACME Corp" in result

    async def test_calculate_variance(self):
        """Test variance calculation function."""
        plugin = create_finance_plugin()
        calculate = plugin["calculate_variance"]

        result = await calculate(50000.0, 45000.0)

        # Variance should be (50000 - 45000) / 45000 * 100 = 11.11%
        assert abs(result - 11.11) < 0.1

    async def test_approve_payment(self):
        """Test payment approval function."""
        plugin = create_finance_plugin()
        approve = plugin["approve_payment"]

        result = await approve(25000.0, "Tech Solutions")

        assert "25000" in result
        assert "Tech Solutions" in result
        assert "approval" in result.lower()


@pytest.mark.integration
class TestSemanticKernelIntegration:
    """Integration tests for Semantic Kernel."""

    @pytest.mark.skipif(not SK_AVAILABLE, reason="Semantic Kernel not installed")
    @patch('src.integrations.semantic_kernel_integration.sk.Kernel')
    async def test_end_to_end_plugin_execution(self, mock_kernel_class, sk_config):
        """Test end-to-end plugin execution."""
        mock_kernel_instance = mock_kernel()
        mock_kernel_class.return_value = mock_kernel_instance

        sk_instance = ANTSSemanticKernel(sk_config)

        # Register finance plugin
        finance_plugin = create_finance_plugin()
        sk_instance.register_ants_plugin("finance", finance_plugin)

        # Invoke function (simplified test)
        result = await finance_plugin["calculate_variance"](60000.0, 50000.0)

        assert result == 20.0  # (60000 - 50000) / 50000 * 100

    @pytest.mark.skipif(not SK_AVAILABLE, reason="Semantic Kernel not installed")
    @patch('src.integrations.semantic_kernel_integration.sk.Kernel')
    async def test_multiple_plugin_registration(self, mock_kernel_class, sk_config):
        """Test registering multiple plugins."""
        mock_kernel_instance = mock_kernel()
        mock_kernel_class.return_value = mock_kernel_instance

        sk_instance = ANTSSemanticKernel(sk_config)

        # Register multiple plugins
        finance_plugin = create_finance_plugin()
        sk_instance.register_ants_plugin("finance", finance_plugin)

        custom_plugin = ANTSPluginBuilder("custom").add_function(
            "test", lambda: "test", "Test function"
        ).build()
        sk_instance.register_ants_plugin("custom", custom_plugin)

        # Both should be registered (verified by no exceptions)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
