"""
Semantic Kernel Integration for ANTS

Microsoft Semantic Kernel provides:
- Plugin system for standardized capabilities
- Automatic task decomposition (planners)
- Memory connectors
- Prompt template management
- Native function orchestration

This integration bridges Semantic Kernel with ANTS agents.

Reference: https://learn.microsoft.com/en-us/semantic-kernel/
"""

import os
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

try:
    import semantic_kernel as sk
    from semantic_kernel.connectors.ai.open_ai import (
        AzureChatCompletion,
        AzureTextEmbedding
    )
    from semantic_kernel.planning import SequentialPlanner
    from semantic_kernel.core_plugins import (
        TextMemoryPlugin,
        TimePlugin,
        MathPlugin
    )
    SK_AVAILABLE = True
except ImportError:
    SK_AVAILABLE = False
    logging.warning(
        "Semantic Kernel not available. Install with: pip install semantic-kernel"
    )

from src.core.observability import tracer
from src.core.llm_client import create_llm_client

logger = logging.getLogger(__name__)


@dataclass
class SemanticKernelConfig:
    """Configuration for Semantic Kernel integration."""

    # Azure OpenAI configuration
    deployment_name: str = "gpt-4"
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_version: str = "2024-02-01"

    # Embeddings configuration
    embedding_deployment: str = "text-embedding-ada-002"

    # Planner configuration
    enable_planner: bool = True
    max_tokens: int = 2048
    temperature: float = 0.7

    @classmethod
    def from_env(cls) -> 'SemanticKernelConfig':
        """Create configuration from environment variables."""
        return cls(
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            embedding_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
        )


class ANTSSemanticKernel:
    """
    Semantic Kernel integration for ANTS agents.

    Provides:
    - Plugin-based capability system
    - Automatic task planning and decomposition
    - Memory integration
    - Prompt template management
    """

    def __init__(self, config: Optional[SemanticKernelConfig] = None):
        """
        Initialize Semantic Kernel for ANTS.

        Args:
            config: Configuration (defaults to environment variables)
        """
        if not SK_AVAILABLE:
            raise ImportError(
                "Semantic Kernel not available. Install with: pip install semantic-kernel"
            )

        self.config = config or SemanticKernelConfig.from_env()
        self.kernel = sk.Kernel()

        # Initialize AI service
        self._initialize_ai_service()

        # Register core plugins
        self._register_core_plugins()

        # Initialize planner
        if self.config.enable_planner:
            self.planner = SequentialPlanner(self.kernel)

        logger.info("Semantic Kernel initialized for ANTS")

    def _initialize_ai_service(self):
        """Initialize Azure OpenAI service for Semantic Kernel."""
        with tracer.start_as_current_span("sk.initialize_ai_service"):
            # Chat completion service
            chat_service = AzureChatCompletion(
                deployment_name=self.config.deployment_name,
                endpoint=self.config.endpoint,
                api_key=self.config.api_key,
                api_version=self.config.api_version
            )
            self.kernel.add_service(chat_service)

            # Embedding service
            embedding_service = AzureTextEmbedding(
                deployment_name=self.config.embedding_deployment,
                endpoint=self.config.endpoint,
                api_key=self.config.api_key,
                api_version=self.config.api_version
            )
            self.kernel.add_service(embedding_service)

            logger.info(
                "AI services initialized",
                chat_deployment=self.config.deployment_name,
                embedding_deployment=self.config.embedding_deployment
            )

    def _register_core_plugins(self):
        """Register core Semantic Kernel plugins."""
        # Time plugin (date/time operations)
        self.kernel.import_plugin_from_object(TimePlugin(), "time")

        # Math plugin (calculations)
        self.kernel.import_plugin_from_object(MathPlugin(), "math")

        logger.info("Core plugins registered: time, math")

    def register_ants_plugin(
        self,
        plugin_name: str,
        functions: Dict[str, Callable]
    ):
        """
        Register ANTS-specific plugin.

        Args:
            plugin_name: Name of the plugin
            functions: Dictionary of function_name -> callable

        Example:
            kernel.register_ants_plugin("finance", {
                "reconcile_invoice": reconcile_invoice_func,
                "calculate_variance": calculate_variance_func
            })
        """
        with tracer.start_as_current_span("sk.register_plugin") as span:
            span.set_attribute("plugin.name", plugin_name)
            span.set_attribute("function.count", len(functions))

            # Create plugin from functions
            plugin = {}
            for func_name, func in functions.items():
                # Wrap function with SK decorator
                sk_func = sk.kernel_function(
                    name=func_name,
                    description=func.__doc__ or f"ANTS function: {func_name}"
                )(func)
                plugin[func_name] = sk_func

            # Import plugin
            self.kernel.import_plugin_from_dict(plugin_name, plugin)

            logger.info(
                f"ANTS plugin registered: {plugin_name}",
                functions=list(functions.keys())
            )

    async def create_plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create execution plan for a goal using Sequential Planner.

        Args:
            goal: High-level goal to achieve
            context: Optional context variables

        Returns:
            Execution plan with steps

        Example:
            plan = await kernel.create_plan(
                "Reconcile all invoices for December 2024"
            )
        """
        if not self.config.enable_planner:
            raise ValueError("Planner not enabled in configuration")

        with tracer.start_as_current_span("sk.create_plan") as span:
            span.set_attribute("goal", goal)

            # Create context
            sk_context = self.kernel.create_new_context()
            if context:
                for key, value in context.items():
                    sk_context[key] = value

            # Generate plan
            plan = await self.planner.create_plan(goal, sk_context)

            # Extract plan steps
            steps = []
            for step in plan._steps:
                steps.append({
                    "plugin": step.plugin_name,
                    "function": step.name,
                    "description": step.description
                })

            span.set_attribute("plan.steps", len(steps))

            logger.info(
                "Plan created",
                goal=goal,
                steps=len(steps)
            )

            return {
                "goal": goal,
                "steps": steps,
                "plan": plan
            }

    async def execute_plan(
        self,
        plan: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a plan created by the planner.

        Args:
            plan: Plan created by create_plan()
            context: Optional context variables

        Returns:
            Execution result
        """
        with tracer.start_as_current_span("sk.execute_plan") as span:
            span.set_attribute("plan.steps", len(plan["steps"]))

            # Create context
            sk_context = self.kernel.create_new_context()
            if context:
                for key, value in context.items():
                    sk_context[key] = value

            # Execute plan
            result = await plan["plan"].invoke(sk_context)

            logger.info(
                "Plan executed",
                goal=plan["goal"],
                success=True
            )

            return {
                "success": True,
                "result": str(result),
                "goal": plan["goal"]
            }

    async def invoke_function(
        self,
        plugin_name: str,
        function_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        Invoke a specific plugin function.

        Args:
            plugin_name: Name of the plugin
            function_name: Name of the function
            arguments: Function arguments

        Returns:
            Function result
        """
        with tracer.start_as_current_span("sk.invoke_function") as span:
            span.set_attribute("plugin", plugin_name)
            span.set_attribute("function", function_name)

            # Get function
            func = self.kernel.plugins[plugin_name][function_name]

            # Create context with arguments
            context = self.kernel.create_new_context()
            for key, value in arguments.items():
                context[key] = value

            # Invoke
            result = await func.invoke(context)

            logger.info(
                "Function invoked",
                plugin=plugin_name,
                function=function_name
            )

            return result

    async def render_prompt(
        self,
        template: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        Render prompt template with variables.

        Args:
            template: Prompt template with {{variables}}
            variables: Variable values

        Returns:
            Rendered prompt

        Example:
            prompt = await kernel.render_prompt(
                "Analyze invoice {{invoice_id}} for vendor {{vendor}}",
                {"invoice_id": "INV-001", "vendor": "ACME Corp"}
            )
        """
        with tracer.start_as_current_span("sk.render_prompt"):
            # Create prompt template
            prompt_template = sk.PromptTemplate(
                template=template,
                template_engine=self.kernel.prompt_template_engine
            )

            # Render with variables
            rendered = await prompt_template.render(self.kernel, variables)

            return rendered

    def create_semantic_function(
        self,
        prompt: str,
        function_name: str,
        description: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ):
        """
        Create a semantic function from a prompt.

        Args:
            prompt: Prompt template
            function_name: Function name
            description: Function description
            max_tokens: Optional max tokens override
            temperature: Optional temperature override

        Returns:
            Semantic function

        Example:
            summarize = kernel.create_semantic_function(
                prompt="Summarize the following text:\\n{{$input}}",
                function_name="summarize",
                description="Summarizes text"
            )
        """
        # Create execution settings
        execution_settings = sk.PromptExecutionSettings(
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature or self.config.temperature
        )

        # Create semantic function
        semantic_function = self.kernel.create_semantic_function(
            prompt_template=prompt,
            function_name=function_name,
            description=description,
            prompt_execution_settings=execution_settings
        )

        logger.info(f"Semantic function created: {function_name}")

        return semantic_function


class ANTSPluginBuilder:
    """
    Helper class to build ANTS plugins for Semantic Kernel.

    Simplifies creating plugins from ANTS agent capabilities.
    """

    def __init__(self, plugin_name: str):
        """
        Initialize plugin builder.

        Args:
            plugin_name: Name of the plugin
        """
        self.plugin_name = plugin_name
        self.functions = {}

    def add_function(
        self,
        name: str,
        func: Callable,
        description: Optional[str] = None
    ):
        """
        Add function to plugin.

        Args:
            name: Function name
            func: Callable function
            description: Optional description
        """
        if description:
            func.__doc__ = description

        self.functions[name] = func
        return self

    def build(self) -> Dict[str, Callable]:
        """Build plugin dictionary."""
        return self.functions


# Example: ANTS Finance Plugin
def create_finance_plugin() -> Dict[str, Callable]:
    """
    Create finance plugin for Semantic Kernel.

    Returns:
        Plugin dictionary
    """
    builder = ANTSPluginBuilder("finance")

    async def reconcile_invoice(invoice_id: str, vendor: str) -> str:
        """Reconcile an invoice against purchase order"""
        # Implementation would call actual finance agent
        return f"Reconciled invoice {invoice_id} for {vendor}"

    async def calculate_variance(actual: float, budget: float) -> float:
        """Calculate budget variance percentage"""
        return ((actual - budget) / budget) * 100

    async def approve_payment(amount: float, vendor: str) -> str:
        """Submit payment for approval"""
        return f"Payment of ${amount} to {vendor} submitted for approval"

    builder.add_function("reconcile_invoice", reconcile_invoice)
    builder.add_function("calculate_variance", calculate_variance)
    builder.add_function("approve_payment", approve_payment)

    return builder.build()


# Global Semantic Kernel instance
_sk_instance: Optional[ANTSSemanticKernel] = None


def get_semantic_kernel(config: Optional[SemanticKernelConfig] = None) -> ANTSSemanticKernel:
    """
    Get or create Semantic Kernel instance.

    Args:
        config: Optional configuration

    Returns:
        ANTSSemanticKernel instance
    """
    global _sk_instance

    if _sk_instance is None:
        _sk_instance = ANTSSemanticKernel(config)

    return _sk_instance


async def demo_semantic_kernel():
    """Demonstrate Semantic Kernel integration."""
    print("=" * 80)
    print("ANTS Semantic Kernel Integration Demo")
    print("=" * 80)
    print()

    try:
        # Initialize Semantic Kernel
        print("1. Initializing Semantic Kernel...")
        sk_kernel = get_semantic_kernel()
        print("   ✓ Semantic Kernel ready")
        print()

        # Register ANTS finance plugin
        print("2. Registering Finance Plugin...")
        finance_plugin = create_finance_plugin()
        sk_kernel.register_ants_plugin("finance", finance_plugin)
        print("   ✓ Finance plugin registered")
        print("   Functions: reconcile_invoice, calculate_variance, approve_payment")
        print()

        # Create a plan
        print("3. Creating Plan...")
        plan = await sk_kernel.create_plan(
            goal="Process invoice INV-001 from ACME Corp for $50,000",
            context={"invoice_id": "INV-001", "vendor": "ACME Corp", "amount": 50000}
        )
        print(f"   ✓ Plan created with {len(plan['steps'])} steps:")
        for i, step in enumerate(plan["steps"], 1):
            print(f"     {i}. {step['plugin']}.{step['function']}")
        print()

        # Execute plan
        print("4. Executing Plan...")
        result = await sk_kernel.execute_plan(plan)
        print(f"   ✓ Plan executed successfully")
        print(f"   Result: {result['result']}")
        print()

        # Invoke specific function
        print("5. Invoking Specific Function...")
        variance = await sk_kernel.invoke_function(
            "finance",
            "calculate_variance",
            {"actual": 50000, "budget": 45000}
        )
        print(f"   ✓ Budget variance: {variance}%")
        print()

        # Render prompt template
        print("6. Rendering Prompt Template...")
        prompt = await sk_kernel.render_prompt(
            "Analyze invoice {{invoice_id}} for vendor {{vendor}} with amount ${{amount}}",
            {"invoice_id": "INV-001", "vendor": "ACME Corp", "amount": "50,000"}
        )
        print(f"   ✓ Rendered: {prompt}")
        print()

        print("=" * 80)
        print("✓ Semantic Kernel Integration Demo Complete")
        print("=" * 80)

    except Exception as e:
        print(f"✗ Demo failed: {e}")
        print("Make sure AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are set")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_semantic_kernel())
