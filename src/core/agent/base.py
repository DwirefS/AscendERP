"""
Base Agent implementation for ANTS.
All agents inherit from this class.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid
from datetime import datetime
import structlog

logger = structlog.get_logger()


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

        try:
            # 1. Perceive - understand the input
            perception = await self.perceive(input_data, context)

            # 2. Retrieve - get relevant context from memory
            retrieved_context = await self.retrieve(perception, context)

            # 3. Reason - decide on actions
            reasoning = await self.reason(perception, retrieved_context, context)

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
                        result = await self.execute(reasoning["action"], context)
                        actions_taken.append({
                            "action": reasoning["action"],
                            "result": result,
                            "policy_decision": policy_decision
                        })

                        # 5. Verify - check result
                        verification = await self.verify(result, context)

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
            await self.learn(input_data, actions_taken, context)

            # Calculate metrics
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

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
