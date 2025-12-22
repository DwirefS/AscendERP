"""
Example: Dynamic Model Routing for Agent Types.

Demonstrates how agents are routed to optimal AI models based on:
- Agent type (finance, code, medical, general)
- Task requirements (capabilities, cost, latency)
- Model availability and performance
- Cost optimization
"""
import asyncio
from src.core.inference import (
    create_model_router,
    ModelProvider,
    ModelCapability,
    RoutingRequest,
    ModelConfig
)


async def example_1_basic_routing():
    """Example 1: Basic routing by agent type."""
    print("=" * 60)
    print("Example 1: Basic Routing by Agent Type")
    print("=" * 60 + "\n")

    # Create router
    router = create_model_router()

    # Configure routing rules (agent_type -> preferred models)
    router.add_routing_rule("finance.reconciliation", ["gpt-4-turbo-2024-04-09"])
    router.add_routing_rule("code.generation", ["claude-opus-4", "claude-sonnet-4"])
    router.add_routing_rule("general.assistant", ["claude-sonnet-4", "gpt-35-turbo-0125"])

    print("1. Routing rules configured:\n")
    print("   finance.reconciliation → GPT-4 Turbo")
    print("   code.generation → Claude Opus/Sonnet")
    print("   general.assistant → Claude Sonnet/GPT-3.5\n")

    # Test routing
    test_cases = [
        ("finance.reconciliation", "Reconcile payment transactions"),
        ("code.generation", "Generate API integration code"),
        ("general.assistant", "Answer user questions")
    ]

    print("2. Routing decisions:\n")

    for agent_type, task_desc in test_cases:
        request = RoutingRequest(
            agent_id=f"{agent_type}_agent_001",
            agent_type=agent_type,
            task_type="default",
            task_description=task_desc,
            required_capabilities=[]
        )

        decision = await router.route(request)

        print(f"   Agent: {agent_type}")
        print(f"   Task: {task_desc}")
        print(f"   → Routed to: {decision.model.display_name}")
        print(f"   → Reason: {decision.reason}")
        print(f"   → Est. cost: ${decision.estimated_cost:.6f}")
        print(f"   → Est. latency: {decision.estimated_latency_ms:.0f}ms")
        print(f"   → Confidence: {decision.confidence:.1%}\n")

    print()


async def example_2_capability_based_routing():
    """Example 2: Routing based on required capabilities."""
    print("=" * 60)
    print("Example 2: Capability-Based Routing")
    print("=" * 60 + "\n")

    router = create_model_router()

    print("1. Capability requirements:\n")

    test_cases = [
        {
            "description": "Function calling for API integration",
            "capabilities": [ModelCapability.FUNCTION_CALLING, ModelCapability.CODE_GENERATION],
            "expected": "Models with function calling + code generation"
        },
        {
            "description": "Long context document analysis",
            "capabilities": [ModelCapability.LONG_CONTEXT, ModelCapability.REASONING],
            "expected": "Models with 100K+ context window"
        },
        {
            "description": "Fast response for user queries",
            "capabilities": [ModelCapability.FAST_RESPONSE],
            "expected": "Claude Haiku or GPT-3.5 Turbo"
        }
    ]

    for case in test_cases:
        print(f"   Task: {case['description']}")
        print(f"   Required capabilities: {[c.value for c in case['capabilities']]}")

        request = RoutingRequest(
            agent_id="test_agent",
            agent_type="test",
            task_type="capability_test",
            task_description=case['description'],
            required_capabilities=case['capabilities']
        )

        decision = await router.route(request)

        print(f"   → Selected: {decision.model.display_name}")
        print(f"   → Capabilities: {[c.value for c in decision.model.capabilities]}")
        print(f"   → Context window: {decision.model.context_window:,} tokens")
        print(f"   → Avg latency: {decision.model.average_latency_ms:.0f}ms\n")

    print()


async def example_3_cost_optimization():
    """Example 3: Cost-constrained routing."""
    print("=" * 60)
    print("Example 3: Cost-Constrained Routing")
    print("=" * 60 + "\n")

    router = create_model_router()

    print("1. Cost-sensitive routing:\n")

    # Same task with different cost constraints
    task_desc = "Summarize this financial report"
    input_tokens = 2000
    output_tokens = 500

    constraints = [
        ("No constraint", None),
        ("Budget: $0.01", 0.01),
        ("Budget: $0.001", 0.001),
        ("Budget: $0.0001", 0.0001)
    ]

    for desc, max_cost in constraints:
        print(f"   {desc}")

        request = RoutingRequest(
            agent_id="finance_agent",
            agent_type="finance.analysis",
            task_type="summarization",
            task_description=task_desc,
            required_capabilities=[],
            max_cost_per_request=max_cost,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens
        )

        decision = await router.route(request)

        print(f"   → Model: {decision.model.display_name}")
        print(f"   → Est. cost: ${decision.estimated_cost:.6f}")
        print(f"   → Input: ${decision.model.input_cost}/1M tokens")
        print(f"   → Output: ${decision.model.output_cost}/1M tokens")

        if max_cost and decision.estimated_cost > max_cost:
            print(f"   ⚠️  Warning: Estimate exceeds budget!")

        print()

    print("2. Cost comparison:\n")

    # Show all models for same task
    request = RoutingRequest(
        agent_id="cost_comparison",
        agent_type="test",
        task_type="test",
        task_description="Test task",
        required_capabilities=[],
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens
    )

    models = router.list_models()
    model_costs = []

    for model in models:
        cost = (input_tokens / 1_000_000) * model.input_cost + (output_tokens / 1_000_000) * model.output_cost
        model_costs.append((model.display_name, cost))

    model_costs.sort(key=lambda x: x[1])

    print(f"   For {input_tokens} input + {output_tokens} output tokens:\n")
    for name, cost in model_costs:
        print(f"   {name:25s} ${cost:.6f}")

    print()


async def example_4_latency_optimization():
    """Example 4: Latency-constrained routing."""
    print("=" * 60)
    print("Example 4: Latency-Constrained Routing")
    print("=" * 60 + "\n")

    router = create_model_router()

    print("1. Real-time response requirements:\n")

    latency_constraints = [
        ("Interactive chat (< 1s)", 1000, True),
        ("Standard response (< 2s)", 2000, False),
        ("Background task (< 5s)", 5000, False),
        ("No constraint", None, False)
    ]

    for desc, max_latency, prefer_fast in latency_constraints:
        print(f"   {desc}")

        request = RoutingRequest(
            agent_id="chat_agent",
            agent_type="chat.assistant",
            task_type="response",
            task_description="Respond to user query",
            required_capabilities=[],
            max_latency_ms=max_latency,
            prefer_fast_response=prefer_fast
        )

        decision = await router.route(request)

        print(f"   → Model: {decision.model.display_name}")
        print(f"   → Est. latency: {decision.estimated_latency_ms:.0f}ms")
        print(f"   → Est. cost: ${decision.estimated_cost:.6f}")

        if max_latency and decision.estimated_latency_ms > max_latency:
            print(f"   ⚠️  Warning: Latency exceeds requirement!")

        print()

    print()


async def example_5_custom_routing():
    """Example 5: Custom routing logic."""
    print("=" * 60)
    print("Example 5: Custom Routing Logic")
    print("=" * 60 + "\n")

    router = create_model_router()

    print("1. Adding custom router:\n")

    # Custom router: Route medical tasks to GPT-4 Turbo
    def medical_router(request: RoutingRequest) -> str:
        if "medical" in request.agent_type or "medical" in request.task_description.lower():
            print(f"   → Custom router triggered for medical task")
            return "gpt-4-turbo-2024-04-09"
        return None

    router.add_custom_router(medical_router)

    print("   Custom router registered: medical tasks → GPT-4 Turbo\n")

    # Test medical task
    print("2. Testing custom routing:\n")

    medical_request = RoutingRequest(
        agent_id="medical_agent_001",
        agent_type="medical.diagnosis",
        task_type="analysis",
        task_description="Analyze patient symptoms for potential diagnosis",
        required_capabilities=[]
    )

    decision = await router.route(medical_request)

    print(f"   Task: {medical_request.task_description}")
    print(f"   → Routed to: {decision.model.display_name}")
    print(f"   → Reason: {decision.reason}")
    print(f"   → Confidence: {decision.confidence:.1%}\n")

    # Test non-medical task (should use normal routing)
    normal_request = RoutingRequest(
        agent_id="general_agent_001",
        agent_type="general.assistant",
        task_type="chat",
        task_description="Help user with general questions",
        required_capabilities=[]
    )

    decision = await router.route(normal_request)

    print(f"   Task: {normal_request.task_description}")
    print(f"   → Routed to: {decision.model.display_name}")
    print(f"   → Reason: {decision.reason}")
    print(f"   → Confidence: {decision.confidence:.1%}\n")

    print()


async def example_6_performance_tracking():
    """Example 6: Performance tracking and adaptation."""
    print("=" * 60)
    print("Example 6: Performance Tracking")
    print("=" * 60 + "\n")

    router = create_model_router()

    print("1. Simulating model usage and tracking:\n")

    # Simulate requests
    request = RoutingRequest(
        agent_id="test_agent",
        agent_type="test",
        task_type="test",
        task_description="Test task",
        required_capabilities=[]
    )

    decision = await router.route(request)
    model_id = decision.model.model_id

    print(f"   Using model: {decision.model.display_name}\n")

    # Simulate successful requests
    print("   Simulating 5 successful requests...")
    for i in range(5):
        await router.record_result(
            model_id=model_id,
            success=True,
            actual_cost=decision.estimated_cost * (1.0 + (i * 0.1)),  # Slight variation
            actual_latency_ms=decision.estimated_latency_ms + (i * 100)
        )

    # Simulate failed request
    print("   Simulating 1 failed request...")
    await router.record_result(
        model_id=model_id,
        success=False,
        actual_cost=decision.estimated_cost,
        actual_latency_ms=decision.estimated_latency_ms
    )

    print()

    # Get updated model stats
    model = router.get_model(model_id)

    print("2. Updated model statistics:\n")
    print(f"   Model: {model.display_name}")
    print(f"   Total requests: {model.total_requests}")
    print(f"   Success rate: {model.success_rate:.1%}")
    print(f"   Avg response time: {model.average_response_time_ms:.0f}ms\n")

    # Get overall router stats
    print("3. Router statistics:\n")
    stats = router.get_stats()

    print(f"   Total models: {stats['total_models']}")
    print(f"   Total requests: {stats['total_requests']}")
    print(f"   Total cost: ${stats['total_cost']:.6f}")
    print(f"   Avg success rate: {stats['average_success_rate']:.1%}")
    print(f"\n   Cost by model:")
    for model_id, cost in stats['cost_by_model'].items():
        model = router.get_model(model_id)
        if model:
            print(f"      {model.display_name:25s} ${cost:.6f}")

    print()


async def example_7_fallback_models():
    """Example 7: Automatic fallback models."""
    print("=" * 60)
    print("Example 7: Fallback Models")
    print("=" * 60 + "\n")

    router = create_model_router()

    print("1. Routing with fallback options:\n")

    request = RoutingRequest(
        agent_id="production_agent",
        agent_type="production.critical",
        task_type="processing",
        task_description="Process critical transaction",
        required_capabilities=[ModelCapability.REASONING, ModelCapability.FUNCTION_CALLING]
    )

    decision = await router.route(request)

    print(f"   Primary model: {decision.model.display_name}")
    print(f"   → Cost: ${decision.estimated_cost:.6f}")
    print(f"   → Latency: {decision.estimated_latency_ms:.0f}ms\n")

    print(f"   Fallback models (in order):")
    for i, fallback in enumerate(decision.fallback_models, 1):
        input_tokens = request.estimated_input_tokens
        output_tokens = request.estimated_output_tokens
        cost = (input_tokens / 1_000_000) * fallback.input_cost + (output_tokens / 1_000_000) * fallback.output_cost

        print(f"   {i}. {fallback.display_name}")
        print(f"      Cost: ${cost:.6f}, Latency: {fallback.average_latency_ms:.0f}ms")

    print("\n   → If primary model fails, automatically try fallbacks\n")

    print()


async def main():
    """Run all model router examples."""
    print("\n")
    print("█" * 60)
    print("ANTS Model Router Examples")
    print("█" * 60)
    print("\n")

    await example_1_basic_routing()
    await example_2_capability_based_routing()
    await example_3_cost_optimization()
    await example_4_latency_optimization()
    await example_5_custom_routing()
    await example_6_performance_tracking()
    await example_7_fallback_models()

    print("=" * 60)
    print("All Examples Complete")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("✓ Agents routed to optimal models based on type and task")
    print("✓ Capability matching ensures model can handle requirements")
    print("✓ Cost optimization: Claude Haiku 5x cheaper than GPT-4 Turbo")
    print("✓ Latency constraints for real-time responses (<1s)")
    print("✓ Custom routing logic for specialized domains (medical, legal)")
    print("✓ Performance tracking adapts routing over time")
    print("✓ Automatic fallbacks ensure reliability")
    print("✓ Finance → GPT-4, Code → Claude, Fast → Haiku/3.5 Turbo")
    print()


if __name__ == "__main__":
    asyncio.run(main())
