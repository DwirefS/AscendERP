"""
Base Agent implementation for ANTS.
All agents inherit from this class.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid
import os
from datetime import datetime
import structlog
import time

logger = structlog.get_logger()

# Optional DevUI integration
_devui_enabled = os.getenv("ANTS_DEVUI_ENABLED", "false").lower() == "true"
_agent_debugger = None

if _devui_enabled:
    try:
        from src.devtools.devui_server import debugger as agent_debugger
        _agent_debugger = agent_debugger
        logger.info("devui_enabled", status="AgentDebugger loaded for visual debugging")
    except ImportError:
        logger.warning("devui_import_failed", msg="DevUI enabled but could not import debugger")

# OpenTelemetry integration (following Microsoft Agent Framework patterns)
_otel_enabled = os.getenv("ENABLE_INSTRUMENTATION", "false").lower() == "true"
_tracer = None

if _otel_enabled:
    try:
        from src.core.observability import (
            tracer,
            trace_agent_execution,
            trace_llm_call,
            agent_execution_counter,
            agent_latency_histogram
        )
        _tracer = tracer
        logger.info("opentelemetry_enabled", status="Distributed tracing enabled")
    except ImportError:
        logger.warning("opentelemetry_import_failed", msg="OTEL enabled but could not import observability module")


class AgentState(Enum):
    """Agent lifecycle states."""
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    WAITING = "waiting"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    tenant_id: str = ""

    # Capabilities
    tools: List[str] = field(default_factory=list)
    max_iterations: int = 10
    timeout_seconds: int = 300

    # Memory configuration
    memory_enabled: bool = True
    episodic_memory_limit: int = 1000

    # Policy configuration
    policy_enabled: bool = True
    require_approval_threshold: float = 0.8

    # Model configuration
    model_name: str = "llama-3.1-nemotron-nano-8b"
    temperature: float = 0.7
    max_tokens: int = 2048


@dataclass
class AgentContext:
    """Context passed to agent during execution."""
    trace_id: str
    tenant_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentResult:
    """Result from agent execution."""
    success: bool
    output: Any
    trace_id: str
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    latency_ms: float = 0.0
    confidence: float = 0.0
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    Base class for all ANTS agents.
    Implements the Perceive → Retrieve → Reason → Execute → Verify → Learn loop.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.state = AgentState.INITIALIZING
        self.memory = None  # Injected
        self.policy_engine = None  # Injected
        self.llm = None  # Injected

        logger.info(
            "agent_initialized",
            agent_id=config.agent_id,
            name=config.name
        )

    async def initialize(
        self,
        memory: 'MemorySubstrate',
        policy_engine: 'PolicyEngine',
        llm: 'LLMClient'
    ):
        """Initialize agent with dependencies."""
        self.memory = memory
        self.policy_engine = policy_engine
        self.llm = llm
        self.state = AgentState.READY

        logger.info("agent_ready", agent_id=self.config.agent_id)

    async def run(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> AgentResult:
        """
        Main execution loop for the agent.
        """
        start_time = datetime.utcnow()
        self.state = AgentState.PROCESSING
        actions_taken = []

        # Start OpenTelemetry span for agent execution
        span = None
        if _tracer:
            span = _tracer.start_span(
                f"{self.__class__.__name__}.run",
                attributes={
                    "agent.id": self.config.agent_id,
                    "agent.name": self.config.name,
                    "agent.type": self.__class__.__name__,
                    "trace.id": context.trace_id,
                    "tenant.id": context.tenant_id
                }
            )
            span.__enter__()

        try:
            # 1. Perceive - understand the input
            phase_start = time.time()
            perception = await self.perceive(input_data, context)

            # Capture phase in DevUI
            if _agent_debugger:
                await _agent_debugger.capture_reasoning_step(
                    agent_id=self.config.agent_id,
                    step_type="perceive",
                    phase_number=1,
                    input_data=input_data,
                    output_data=perception,
                    metadata={
                        "latency_ms": (time.time() - phase_start) * 1000
                    }
                )

            # 2. Retrieve - get relevant context from memory
            phase_start = time.time()
            retrieved_context = await self.retrieve(perception, context)

            # Capture phase in DevUI
            if _agent_debugger:
                memory_snapshot = None
                if self.memory:
                    try:
                        memory_snapshot = {
                            "retrieved_count": len(retrieved_context.get("memories", [])),
                            "relevant_facts": retrieved_context.get("facts", [])[:5]
                        }
                    except:
                        memory_snapshot = {"status": "memory_snapshot_failed"}

                await _agent_debugger.capture_reasoning_step(
                    agent_id=self.config.agent_id,
                    step_type="retrieve",
                    phase_number=2,
                    input_data={"perception": perception},
                    output_data=retrieved_context,
                    metadata={
                        "memory_snapshot": memory_snapshot,
                        "latency_ms": (time.time() - phase_start) * 1000
                    }
                )

            # 3. Reason - decide on actions
            phase_start = time.time()
            reasoning = await self.reason(perception, retrieved_context, context)

            # Capture phase in DevUI
            if _agent_debugger:
                await _agent_debugger.capture_reasoning_step(
                    agent_id=self.config.agent_id,
                    step_type="reason",
                    phase_number=3,
                    input_data={"perception": perception, "context": retrieved_context},
                    output_data=reasoning,
                    metadata={
                        "latency_ms": (time.time() - phase_start) * 1000
                    }
                )

            iterations = 0
            while iterations < self.config.max_iterations:
                iterations += 1

                # 4. Execute - perform actions
                if reasoning.get("action"):
                    # Check policy before execution
                    policy_decision = await self._check_policy(
                        reasoning["action"],
                        context
                    )

                    if policy_decision["allowed"]:
                        phase_start = time.time()
                        result = await self.execute(reasoning["action"], context)

                        # Capture phase in DevUI
                        if _agent_debugger:
                            await _agent_debugger.capture_reasoning_step(
                                agent_id=self.config.agent_id,
                                step_type="execute",
                                phase_number=4,
                                input_data={"action": reasoning["action"]},
                                output_data={"result": result},
                                metadata={
                                    "policy_result": policy_decision,
                                    "latency_ms": (time.time() - phase_start) * 1000
                                }
                            )

                        actions_taken.append({
                            "action": reasoning["action"],
                            "result": result,
                            "policy_decision": policy_decision
                        })

                        # 5. Verify - check result
                        phase_start = time.time()
                        verification = await self.verify(result, context)

                        # Capture phase in DevUI
                        if _agent_debugger:
                            await _agent_debugger.capture_reasoning_step(
                                agent_id=self.config.agent_id,
                                step_type="verify",
                                phase_number=5,
                                input_data={"result": result},
                                output_data=verification,
                                metadata={
                                    "latency_ms": (time.time() - phase_start) * 1000
                                }
                            )

                        if verification["complete"]:
                            break

                        # Continue reasoning with new context
                        reasoning = await self.reason(
                            perception,
                            {**retrieved_context, "last_result": result},
                            context
                        )
                    else:
                        # Policy denied - handle gracefully
                        logger.warning(
                            "action_denied_by_policy",
                            action=reasoning["action"],
                            reason=policy_decision.get("reason")
                        )
                        break
                else:
                    break

            # 6. Learn - store in memory
            phase_start = time.time()
            await self.learn(input_data, actions_taken, context)

            # Capture phase in DevUI
            if _agent_debugger:
                await _agent_debugger.capture_reasoning_step(
                    agent_id=self.config.agent_id,
                    step_type="learn",
                    phase_number=6,
                    input_data={"input_data": input_data, "actions_count": len(actions_taken)},
                    output_data={"status": "learning_complete"},
                    metadata={
                        "latency_ms": (time.time() - phase_start) * 1000
                    }
                )

            # Calculate metrics
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Record OpenTelemetry metrics
            if _otel_enabled:
                from src.core.observability import agent_execution_counter, agent_latency_histogram
                agent_execution_counter.add(
                    1,
                    {"agent_type": self.__class__.__name__, "status": "success"}
                )
                agent_latency_histogram.record(
                    latency_ms,
                    {"agent_type": self.__class__.__name__}
                )

            # Close OpenTelemetry span
            if span:
                span.set_attribute("success", True)
                span.set_attribute("latency_ms", latency_ms)
                span.set_attribute("actions_count", len(actions_taken))
                span.__exit__(None, None, None)

            self.state = AgentState.READY

            return AgentResult(
                success=True,
                output=reasoning.get("output", actions_taken[-1]["result"] if actions_taken else None),
                trace_id=context.trace_id,
                actions_taken=actions_taken,
                latency_ms=latency_ms,
                confidence=reasoning.get("confidence", 0.0)
            )

        except Exception as e:
            self.state = AgentState.ERROR

            # Record error metrics
            if _otel_enabled:
                from src.core.observability import agent_execution_counter
                agent_execution_counter.add(
                    1,
                    {"agent_type": self.__class__.__name__, "status": "error"}
                )

            # Record error in OpenTelemetry span
            if span:
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                span.record_exception(e)
                span.__exit__(type(e), e, e.__traceback__)

            logger.error(
                "agent_execution_error",
                agent_id=self.config.agent_id,
                error=str(e)
            )

            return AgentResult(
                success=False,
                output=None,
                trace_id=context.trace_id,
                error=str(e)
            )

    @abstractmethod
    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Perceive and understand the input."""
        pass

    @abstractmethod
    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Retrieve relevant context from memory."""
        pass

    @abstractmethod
    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Reason about what action to take."""
        pass

    @abstractmethod
    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """Execute the decided action."""
        pass

    @abstractmethod
    async def verify(
        self,
        result: Any,
        context: AgentContext
    ) -> Dict[str, Any]:
        """Verify the execution result."""
        pass

    @abstractmethod
    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext
    ):
        """Learn from the execution for future improvement."""
        pass

    async def _check_policy(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Check policy before executing action."""
        if not self.config.policy_enabled or not self.policy_engine:
            return {"allowed": True}

        decision = await self.policy_engine.evaluate({
            "agent_id": self.config.agent_id,
            "action": action,
            "context": context.metadata
        })

        return decision
