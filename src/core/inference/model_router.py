"""
Model Router for Dynamic Model Selection.

Routes agents to optimal AI models based on:
- Agent type (finance, code, medical, legal, etc.)
- Task complexity and requirements
- Cost constraints and budgets
- Model availability and load
- Performance history

Supports:
- Azure OpenAI (GPT-4, GPT-4 Turbo, GPT-3.5)
- Anthropic Claude (Opus, Sonnet, Haiku)
- Google Gemini (Ultra, Pro, Flash)
- Domain-specific models (FinBERT, CodeLlama, Med-PaLM, etc.)
- Custom model endpoints
"""
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import structlog
from collections import defaultdict

logger = structlog.get_logger()


class ModelProvider(Enum):
    """AI model providers."""
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    NVIDIA = "nvidia"
    CUSTOM = "custom"


class ModelCapability(Enum):
    """Model capabilities for matching."""
    GENERAL_PURPOSE = "general_purpose"
    CODE_GENERATION = "code_generation"
    FINANCIAL_ANALYSIS = "financial_analysis"
    MEDICAL_REASONING = "medical_reasoning"
    LEGAL_ANALYSIS = "legal_analysis"
    FUNCTION_CALLING = "function_calling"
    LONG_CONTEXT = "long_context"
    MULTIMODAL = "multimodal"
    REASONING = "reasoning"
    FAST_RESPONSE = "fast_response"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    model_id: str
    provider: ModelProvider
    display_name: str
    capabilities: List[ModelCapability]

    # Performance characteristics
    context_window: int  # Max tokens
    max_output_tokens: int
    supports_streaming: bool
    average_latency_ms: float

    # Cost (per 1M tokens)
    input_cost: float
    output_cost: float

    # Availability
    endpoint: str
    deployment_name: Optional[str] = None
    api_version: Optional[str] = None

    # Load balancing
    max_requests_per_minute: int = 1000
    current_load: float = 0.0

    # Performance tracking
    success_rate: float = 1.0
    average_response_time_ms: float = 0.0
    total_requests: int = 0

    # Custom metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingRequest:
    """Request for model routing."""
    agent_id: str
    agent_type: str
    task_type: str
    task_description: str
    required_capabilities: List[ModelCapability]

    # Constraints
    max_cost_per_request: Optional[float] = None
    max_latency_ms: Optional[float] = None
    min_context_window: Optional[int] = None

    # Preferences
    prefer_provider: Optional[ModelProvider] = None
    prefer_fast_response: bool = False

    # Context
    estimated_input_tokens: int = 1000
    estimated_output_tokens: int = 500

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    model: ModelConfig
    reason: str
    estimated_cost: float
    estimated_latency_ms: float
    fallback_models: List[ModelConfig]
    confidence: float  # 0.0-1.0


class ModelRouter:
    """
    Dynamic model router for AI agents.

    Features:
    - Capability-based routing
    - Cost optimization
    - Load balancing
    - Performance tracking
    - Automatic fallbacks
    - Custom routing rules
    """

    def __init__(self):
        # Model registry
        self._models: Dict[str, ModelConfig] = {}

        # Routing rules (agent_type -> preferred models)
        self._routing_rules: Dict[str, List[str]] = {}

        # Custom routing functions
        self._custom_routers: List[Callable[[RoutingRequest], Optional[str]]] = []

        # Performance tracking
        self._request_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Cost tracking
        self._total_cost: float = 0.0
        self._cost_by_model: Dict[str, float] = defaultdict(float)

        # Initialize default models
        self._register_default_models()

    def _register_default_models(self):
        """Register default model configurations."""

        # Azure OpenAI - GPT-4 Turbo (latest, best for complex reasoning)
        self.register_model(ModelConfig(
            model_id="gpt-4-turbo-2024-04-09",
            provider=ModelProvider.AZURE_OPENAI,
            display_name="GPT-4 Turbo",
            capabilities=[
                ModelCapability.GENERAL_PURPOSE,
                ModelCapability.CODE_GENERATION,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.REASONING,
                ModelCapability.LONG_CONTEXT
            ],
            context_window=128000,
            max_output_tokens=4096,
            supports_streaming=True,
            average_latency_ms=3000,
            input_cost=10.0,   # $10 per 1M input tokens
            output_cost=30.0,  # $30 per 1M output tokens
            endpoint="https://your-resource.openai.azure.com",
            api_version="2024-02-15-preview"
        ))

        # Azure OpenAI - GPT-3.5 Turbo (fast, cheap, good for simple tasks)
        self.register_model(ModelConfig(
            model_id="gpt-35-turbo-0125",
            provider=ModelProvider.AZURE_OPENAI,
            display_name="GPT-3.5 Turbo",
            capabilities=[
                ModelCapability.GENERAL_PURPOSE,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.FAST_RESPONSE
            ],
            context_window=16385,
            max_output_tokens=4096,
            supports_streaming=True,
            average_latency_ms=1000,
            input_cost=0.5,    # $0.50 per 1M input tokens
            output_cost=1.5,   # $1.50 per 1M output tokens
            endpoint="https://your-resource.openai.azure.com",
            api_version="2024-02-15-preview"
        ))

        # Anthropic Claude Opus (best reasoning, coding)
        self.register_model(ModelConfig(
            model_id="claude-opus-4",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude Opus 4",
            capabilities=[
                ModelCapability.GENERAL_PURPOSE,
                ModelCapability.CODE_GENERATION,
                ModelCapability.REASONING,
                ModelCapability.LONG_CONTEXT,
                ModelCapability.FUNCTION_CALLING
            ],
            context_window=200000,
            max_output_tokens=4096,
            supports_streaming=True,
            average_latency_ms=2500,
            input_cost=15.0,   # $15 per 1M input tokens
            output_cost=75.0,  # $75 per 1M output tokens
            endpoint="https://api.anthropic.com/v1/messages"
        ))

        # Anthropic Claude Sonnet (balanced performance/cost)
        self.register_model(ModelConfig(
            model_id="claude-sonnet-4",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude Sonnet 4",
            capabilities=[
                ModelCapability.GENERAL_PURPOSE,
                ModelCapability.CODE_GENERATION,
                ModelCapability.REASONING,
                ModelCapability.FUNCTION_CALLING
            ],
            context_window=200000,
            max_output_tokens=4096,
            supports_streaming=True,
            average_latency_ms=2000,
            input_cost=3.0,    # $3 per 1M input tokens
            output_cost=15.0,  # $15 per 1M output tokens
            endpoint="https://api.anthropic.com/v1/messages"
        ))

        # Anthropic Claude Haiku (fast, cheap)
        self.register_model(ModelConfig(
            model_id="claude-haiku-4",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude Haiku 4",
            capabilities=[
                ModelCapability.GENERAL_PURPOSE,
                ModelCapability.FAST_RESPONSE,
                ModelCapability.FUNCTION_CALLING
            ],
            context_window=200000,
            max_output_tokens=4096,
            supports_streaming=True,
            average_latency_ms=800,
            input_cost=0.25,   # $0.25 per 1M input tokens
            output_cost=1.25,  # $1.25 per 1M output tokens
            endpoint="https://api.anthropic.com/v1/messages"
        ))

        # Google Gemini Pro (good general purpose, multimodal)
        self.register_model(ModelConfig(
            model_id="gemini-1.5-pro",
            provider=ModelProvider.GOOGLE,
            display_name="Gemini 1.5 Pro",
            capabilities=[
                ModelCapability.GENERAL_PURPOSE,
                ModelCapability.REASONING,
                ModelCapability.MULTIMODAL,
                ModelCapability.LONG_CONTEXT
            ],
            context_window=2000000,  # 2M tokens!
            max_output_tokens=8192,
            supports_streaming=True,
            average_latency_ms=2500,
            input_cost=3.5,    # $3.50 per 1M input tokens
            output_cost=10.5,  # $10.50 per 1M output tokens
            endpoint="https://generativelanguage.googleapis.com/v1beta"
        ))

        # Google FunctionGemma (specialized for tool calling)
        self.register_model(ModelConfig(
            model_id="functiongemma-7b",
            provider=ModelProvider.GOOGLE,
            display_name="FunctionGemma 7B",
            capabilities=[
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.FAST_RESPONSE
            ],
            context_window=8192,
            max_output_tokens=2048,
            supports_streaming=True,
            average_latency_ms=500,
            input_cost=0.1,    # Very cheap
            output_cost=0.3,
            endpoint="https://your-endpoint/functiongemma"
        ))

        logger.info("default_models_registered", count=len(self._models))

    def register_model(self, model: ModelConfig):
        """Register a new model."""
        self._models[model.model_id] = model
        logger.info("model_registered", model_id=model.model_id, provider=model.provider.value)

    def add_routing_rule(self, agent_type: str, preferred_models: List[str]):
        """Add routing rule for agent type."""
        self._routing_rules[agent_type] = preferred_models
        logger.info("routing_rule_added", agent_type=agent_type, models=preferred_models)

    def add_custom_router(self, router_func: Callable[[RoutingRequest], Optional[str]]):
        """Add custom routing function."""
        self._custom_routers.append(router_func)
        logger.info("custom_router_added")

    async def route(self, request: RoutingRequest) -> RoutingDecision:
        """
        Route request to optimal model.

        Routing strategy:
        1. Check custom routers first
        2. Apply agent-type routing rules
        3. Filter by capabilities
        4. Filter by constraints (cost, latency, context)
        5. Score remaining models
        6. Select best model
        7. Identify fallback options
        """

        # 1. Custom routers
        for custom_router in self._custom_routers:
            model_id = custom_router(request)
            if model_id and model_id in self._models:
                model = self._models[model_id]
                decision = self._create_decision(model, request, "custom_router", 1.0)
                logger.info("routed_via_custom", model_id=model_id, agent_type=request.agent_type)
                return decision

        # 2. Agent-type routing rules
        if request.agent_type in self._routing_rules:
            preferred_models = self._routing_rules[request.agent_type]
            for model_id in preferred_models:
                if model_id in self._models:
                    model = self._models[model_id]
                    if self._meets_requirements(model, request):
                        decision = self._create_decision(model, request, "routing_rule", 0.9)
                        logger.info("routed_via_rule", model_id=model_id, agent_type=request.agent_type)
                        return decision

        # 3. Filter by capabilities
        candidates = []
        for model in self._models.values():
            if not request.required_capabilities:
                candidates.append(model)
                continue

            # Check if model has all required capabilities
            model_caps = set(model.capabilities)
            required_caps = set(request.required_capabilities)

            if required_caps.issubset(model_caps):
                candidates.append(model)

        if not candidates:
            # No models match capabilities, relax requirements
            logger.warning("no_models_match_capabilities", required=request.required_capabilities)
            candidates = list(self._models.values())

        # 4. Filter by constraints
        filtered = []
        for model in candidates:
            if not self._meets_requirements(model, request):
                continue
            filtered.append(model)

        if not filtered:
            # No models meet constraints, use candidates anyway
            logger.warning("no_models_meet_constraints")
            filtered = candidates

        # 5. Score models
        scored_models = []
        for model in filtered:
            score = self._score_model(model, request)
            scored_models.append((score, model))

        # Sort by score (highest first)
        scored_models.sort(reverse=True, key=lambda x: x[0])

        # 6. Select best model
        best_score, best_model = scored_models[0]
        confidence = best_score / 100.0 if best_score <= 100 else 1.0

        # 7. Identify fallbacks
        fallbacks = [model for _, model in scored_models[1:4]]

        decision = self._create_decision(
            best_model,
            request,
            f"scored (score={best_score:.1f})",
            confidence
        )
        decision.fallback_models = fallbacks

        logger.info(
            "model_routed",
            model_id=best_model.model_id,
            agent_type=request.agent_type,
            score=best_score,
            confidence=confidence
        )

        return decision

    def _meets_requirements(self, model: ModelConfig, request: RoutingRequest) -> bool:
        """Check if model meets request requirements."""

        # Cost constraint
        if request.max_cost_per_request is not None:
            estimated_cost = self._estimate_cost(
                model,
                request.estimated_input_tokens,
                request.estimated_output_tokens
            )
            if estimated_cost > request.max_cost_per_request:
                return False

        # Latency constraint
        if request.max_latency_ms is not None:
            if model.average_latency_ms > request.max_latency_ms:
                return False

        # Context window
        if request.min_context_window is not None:
            if model.context_window < request.min_context_window:
                return False

        # Provider preference
        if request.prefer_provider is not None:
            if model.provider != request.prefer_provider:
                return False

        return True

    def _score_model(self, model: ModelConfig, request: RoutingRequest) -> float:
        """Score model for request (higher is better)."""
        score = 0.0

        # Capability match (40 points)
        if request.required_capabilities:
            model_caps = set(model.capabilities)
            required_caps = set(request.required_capabilities)
            match_ratio = len(required_caps & model_caps) / len(required_caps)
            score += match_ratio * 40
        else:
            score += 40  # No requirements, full points

        # Cost efficiency (30 points)
        estimated_cost = self._estimate_cost(
            model,
            request.estimated_input_tokens,
            request.estimated_output_tokens
        )
        # Inverse cost score (cheaper is better)
        # Normalize: $0.001 = 30 points, $0.10 = 0 points
        max_cost = 0.10
        cost_score = max(0, 30 * (1 - min(estimated_cost, max_cost) / max_cost))
        score += cost_score

        # Latency (20 points)
        if request.prefer_fast_response:
            # Fast response preferred
            max_latency = 5000  # 5 seconds
            latency_score = max(0, 20 * (1 - min(model.average_latency_ms, max_latency) / max_latency))
            score += latency_score
        else:
            # Balance speed with quality
            optimal_latency = 2000  # 2 seconds
            deviation = abs(model.average_latency_ms - optimal_latency)
            latency_score = max(0, 20 * (1 - deviation / 5000))
            score += latency_score

        # Success rate (10 points)
        score += model.success_rate * 10

        # Load balancing (bonus/penalty)
        # Prefer models with lower current load
        if model.current_load > 0.8:  # >80% loaded
            score -= 10
        elif model.current_load < 0.3:  # <30% loaded
            score += 5

        return score

    def _estimate_cost(self, model: ModelConfig, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for request."""
        input_cost = (input_tokens / 1_000_000) * model.input_cost
        output_cost = (output_tokens / 1_000_000) * model.output_cost
        return input_cost + output_cost

    def _create_decision(
        self,
        model: ModelConfig,
        request: RoutingRequest,
        reason: str,
        confidence: float
    ) -> RoutingDecision:
        """Create routing decision."""
        estimated_cost = self._estimate_cost(
            model,
            request.estimated_input_tokens,
            request.estimated_output_tokens
        )

        return RoutingDecision(
            model=model,
            reason=reason,
            estimated_cost=estimated_cost,
            estimated_latency_ms=model.average_latency_ms,
            fallback_models=[],
            confidence=confidence
        )

    async def record_result(
        self,
        model_id: str,
        success: bool,
        actual_cost: float,
        actual_latency_ms: float
    ):
        """Record request result for performance tracking."""
        if model_id not in self._models:
            return

        model = self._models[model_id]

        # Update model statistics
        model.total_requests += 1

        # Update success rate (exponential moving average)
        alpha = 0.1
        model.success_rate = (alpha * (1.0 if success else 0.0)) + ((1 - alpha) * model.success_rate)

        # Update average response time
        model.average_response_time_ms = (
            (model.average_response_time_ms * (model.total_requests - 1) + actual_latency_ms)
            / model.total_requests
        )

        # Track cost
        self._total_cost += actual_cost
        self._cost_by_model[model_id] += actual_cost

        # Store in history
        self._request_history[model_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "cost": actual_cost,
            "latency_ms": actual_latency_ms
        })

        # Keep only last 1000 requests per model
        if len(self._request_history[model_id]) > 1000:
            self._request_history[model_id] = self._request_history[model_id][-1000:]

        logger.debug(
            "result_recorded",
            model_id=model_id,
            success=success,
            cost=actual_cost,
            latency_ms=actual_latency_ms
        )

    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get model by ID."""
        return self._models.get(model_id)

    def list_models(
        self,
        provider: Optional[ModelProvider] = None,
        capability: Optional[ModelCapability] = None
    ) -> List[ModelConfig]:
        """List registered models with optional filtering."""
        models = list(self._models.values())

        if provider:
            models = [m for m in models if m.provider == provider]

        if capability:
            models = [m for m in models if capability in m.capabilities]

        return models

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        return {
            "total_models": len(self._models),
            "total_cost": round(self._total_cost, 4),
            "cost_by_model": {k: round(v, 4) for k, v in self._cost_by_model.items()},
            "models_by_provider": {
                provider.value: len([m for m in self._models.values() if m.provider == provider])
                for provider in ModelProvider
            },
            "total_requests": sum(m.total_requests for m in self._models.values()),
            "average_success_rate": sum(m.success_rate for m in self._models.values()) / len(self._models) if self._models else 0
        }


# Factory function
def create_model_router() -> ModelRouter:
    """Create a ModelRouter instance with default models."""
    return ModelRouter()
