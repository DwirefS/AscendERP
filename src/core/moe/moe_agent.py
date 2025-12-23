"""
Mixture of Experts (MoE) Agent - Complete Implementation

Combines expert routing, execution, and aggregation into production-ready system.

This file contains all MoE components:
- Expert base classes
- Gating mechanisms
- Aggregation strategies
- Complete MoEAgent

Based on arXiv:2503.07137 (MoE Survey, Mar 2025) and arXiv:2511.13983 (MoMoE, Nov 2025)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging
import asyncio

logger = logging.getLogger(__name__)


# ============================================================================
# EXPERT COMPONENTS
# ============================================================================

class ExpertType(Enum):
    """Types of expert specialization"""
    # Domain experts (vertical specialization)
    FINANCE = "finance"
    LEGAL = "legal"
    OPERATIONS = "operations"
    HR = "hr"
    TECHNOLOGY = "technology"
    SUSTAINABILITY = "sustainability"

    # Capability experts (horizontal specialization)
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    NEGOTIATION = "negotiation"
    EXECUTION = "execution"


@dataclass
class ExpertOutput:
    """Output from an expert"""
    expert_id: str
    expert_type: ExpertType
    result: Any
    confidence: float  # 0.0 to 1.0
    reasoning: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class Expert(ABC):
    """
    Abstract base class for all experts in MoE system

    Each expert is a specialized sub-agent optimized for specific domain/capability
    """

    def __init__(self, expert_id: str, expert_type: ExpertType, domain: List[str]):
        self.expert_id = expert_id
        self.expert_type = expert_type
        self.domain = domain  # Areas of expertise
        self.performance_history: List[float] = []

    @abstractmethod
    async def analyze(self, task: Dict[str, Any]) -> ExpertOutput:
        """
        Analyze task and produce expert output

        Args:
            task: Task data and context

        Returns:
            ExpertOutput with result and confidence
        """
        pass

    async def estimate_confidence(self, task: Dict[str, Any]) -> float:
        """
        Estimate confidence for this task without full analysis

        Used by gating network for routing decisions
        """
        # Check domain overlap
        task_domain = task.get("domain", "general")

        if task_domain in self.domain:
            return 0.9
        elif any(d in task_domain for d in self.domain):
            return 0.7
        else:
            return 0.3

    def update_performance(self, accuracy: float):
        """Update performance history"""
        self.performance_history.append(accuracy)

        # Keep last 100 results
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]

    def get_avg_performance(self) -> float:
        """Get average historical performance"""
        if not self.performance_history:
            return 0.5
        return sum(self.performance_history) / len(self.performance_history)


class DomainExpert(Expert):
    """Expert specialized in specific domain (finance, legal, operations, etc.)"""

    async def analyze(self, task: Dict[str, Any]) -> ExpertOutput:
        """Domain-specific analysis"""
        logger.info(f"Expert {self.expert_id} ({self.expert_type.value}) analyzing task")

        # Simulate domain-specific analysis
        # In production, would call LLM with domain-specific prompt/fine-tuning

        confidence = await self.estimate_confidence(task)

        result = {
            "recommendation": f"{self.expert_type.value.title()} perspective on {task.get('description', 'task')}",
            "considerations": self._get_domain_considerations(task),
            "risk_level": self._assess_risk(task)
        }

        return ExpertOutput(
            expert_id=self.expert_id,
            expert_type=self.expert_type,
            result=result,
            confidence=confidence,
            reasoning=f"Analysis based on {self.expert_type.value} expertise"
        )

    def _get_domain_considerations(self, task: Dict[str, Any]) -> List[str]:
        """Get domain-specific considerations"""
        if self.expert_type == ExpertType.FINANCE:
            return ["ROI analysis", "Budget impact", "Cash flow implications"]
        elif self.expert_type == ExpertType.LEGAL:
            return ["Regulatory compliance", "Contract review", "Risk exposure"]
        elif self.expert_type == ExpertType.SUSTAINABILITY:
            return ["Carbon footprint", "ESG impact", "Regulatory compliance"]
        else:
            return ["Domain best practices", "Technical feasibility"]

    def _assess_risk(self, task: Dict[str, Any]) -> str:
        """Assess risk level from domain perspective"""
        budget = task.get("budget_amount", 0)

        if budget > 1000000:
            return "high"
        elif budget > 100000:
            return "medium"
        else:
            return "low"


class CapabilityExpert(Expert):
    """Expert specialized in specific capability (analysis, creativity, execution, etc.)"""

    async def analyze(self, task: Dict[str, Any]) -> ExpertOutput:
        """Capability-specific analysis"""
        logger.info(f"Expert {self.expert_id} ({self.expert_type.value}) analyzing task")

        confidence = await self.estimate_confidence(task)

        result = {
            "approach": self._get_capability_approach(task),
            "estimated_effort": self._estimate_effort(task),
            "success_probability": confidence
        }

        return ExpertOutput(
            expert_id=self.expert_id,
            expert_type=self.expert_type,
            result=result,
            confidence=confidence,
            reasoning=f"Analysis using {self.expert_type.value} capabilities"
        )

    def _get_capability_approach(self, task: Dict[str, Any]) -> str:
        """Get capability-specific approach"""
        if self.expert_type == ExpertType.ANALYTICAL:
            return "Data-driven quantitative analysis with statistical models"
        elif self.expert_type == ExpertType.CREATIVE:
            return "Innovative solutions exploring unconventional approaches"
        elif self.expert_type == ExpertType.EXECUTION:
            return "Pragmatic implementation focused on deliverables"
        else:
            return "Balanced approach considering multiple factors"

    def _estimate_effort(self, task: Dict[str, Any]) -> str:
        """Estimate effort required"""
        complexity = task.get("complexity", "medium")

        effort_map = {
            "low": "1-2 days",
            "medium": "1-2 weeks",
            "high": "1-3 months"
        }

        return effort_map.get(complexity, "2-4 weeks")


# ============================================================================
# GATING MECHANISMS
# ============================================================================

class GatingNetwork(ABC):
    """
    Abstract base class for gating networks

    Gating network routes inputs to most appropriate expert(s)
    """

    @abstractmethod
    async def route(
        self,
        task: Dict[str, Any],
        experts: List[Expert],
        top_k: int = 2
    ) -> List[Tuple[Expert, float]]:
        """
        Route task to appropriate experts

        Args:
            task: Task to route
            experts: Available experts
            top_k: Number of experts to activate

        Returns:
            List of (expert, weight) tuples
        """
        pass


class RuleBasedGate(GatingNetwork):
    """
    Rule-based routing using explicit business logic

    Example:
    - Finance task → Finance expert + Risk expert + Legal expert
    - HR task + compliance flag → HR expert + Legal expert + Ethics expert
    """

    async def route(
        self,
        task: Dict[str, Any],
        experts: List[Expert],
        top_k: int = 2
    ) -> List[Tuple[Expert, float]]:
        """Route based on explicit rules"""

        domain = task.get("domain", "general")
        risk_level = task.get("risk_level", "medium")
        involves_compliance = task.get("involves_compliance", False)

        selected = []

        # Rule 1: Always include domain expert if available
        for expert in experts:
            if domain in [d.lower() for d in expert.domain]:
                selected.append((expert, 1.0))
                break

        # Rule 2: High risk → include risk/legal experts
        if risk_level == "high":
            for expert in experts:
                if expert.expert_type in [ExpertType.LEGAL, ExpertType.FINANCE]:
                    if expert not in [s[0] for s in selected]:
                        selected.append((expert, 0.8))

        # Rule 3: Compliance → include legal/ethics experts
        if involves_compliance:
            for expert in experts:
                if expert.expert_type in [ExpertType.LEGAL, ExpertType.SUSTAINABILITY]:
                    if expert not in [s[0] for s in selected]:
                        selected.append((expert, 0.9))

        # Rule 4: Cross-functional → include analytical expert
        if task.get("is_cross_functional", False):
            for expert in experts:
                if expert.expert_type == ExpertType.ANALYTICAL:
                    if expert not in [s[0] for s in selected]:
                        selected.append((expert, 0.7))

        # Fill up to top_k with best remaining experts
        if len(selected) < top_k:
            remaining = [e for e in experts if e not in [s[0] for s in selected]]
            for expert in remaining[:top_k - len(selected)]:
                selected.append((expert, 0.5))

        # Return top_k experts
        selected = sorted(selected, key=lambda x: x[1], reverse=True)[:top_k]

        logger.info(
            f"Rule-based routing selected {len(selected)} experts: "
            f"{[e.expert_id for e, _ in selected]}"
        )

        return selected


class ConfidenceGate(GatingNetwork):
    """
    Confidence-based routing - select experts with highest confidence

    Each expert estimates confidence, gate selects top-K
    """

    async def route(
        self,
        task: Dict[str, Any],
        experts: List[Expert],
        top_k: int = 2
    ) -> List[Tuple[Expert, float]]:
        """Route to experts with highest confidence"""

        # Get confidence estimates from all experts
        confidences = await asyncio.gather(*[
            expert.estimate_confidence(task)
            for expert in experts
        ])

        # Pair experts with confidences
        expert_confidences = list(zip(experts, confidences))

        # Sort by confidence descending
        expert_confidences = sorted(expert_confidences, key=lambda x: x[1], reverse=True)

        # Select top-K
        selected = expert_confidences[:top_k]

        logger.info(
            f"Confidence-based routing selected {len(selected)} experts: "
            f"{[(e.expert_id, f'{conf:.2f}') for e, conf in selected]}"
        )

        return selected


class LearnedGate(GatingNetwork):
    """
    Learned gating using historical performance

    Learns which experts perform best on which task types
    """

    def __init__(self):
        self.performance_matrix: Dict[str, Dict[str, float]] = {}
        # performance_matrix[task_type][expert_id] = avg_accuracy

    async def route(
        self,
        task: Dict[str, Any],
        experts: List[Expert],
        top_k: int = 2
    ) -> List[Tuple[Expert, float]]:
        """Route based on learned performance"""

        task_type = task.get("type", "general")

        # Get historical performance for this task type
        if task_type not in self.performance_matrix:
            # No history, fall back to confidence-based
            logger.info(f"No history for task type {task_type}, using confidence-based routing")
            confidence_gate = ConfidenceGate()
            return await confidence_gate.route(task, experts, top_k)

        # Score experts based on historical performance
        expert_scores = []
        for expert in experts:
            if expert.expert_id in self.performance_matrix[task_type]:
                score = self.performance_matrix[task_type][expert.expert_id]
            else:
                score = expert.get_avg_performance()

            expert_scores.append((expert, score))

        # Sort by score descending
        expert_scores = sorted(expert_scores, key=lambda x: x[1], reverse=True)

        # Select top-K
        selected = expert_scores[:top_k]

        # Normalize weights
        total_weight = sum(score for _, score in selected)
        selected = [(expert, score / total_weight) for expert, score in selected]

        logger.info(
            f"Learned routing selected {len(selected)} experts: "
            f"{[(e.expert_id, f'{weight:.2f}') for e, weight in selected]}"
        )

        return selected

    def update_performance(self, task_type: str, expert_id: str, accuracy: float):
        """Update performance matrix after task completion"""
        if task_type not in self.performance_matrix:
            self.performance_matrix[task_type] = {}

        # Exponential moving average
        if expert_id in self.performance_matrix[task_type]:
            old_perf = self.performance_matrix[task_type][expert_id]
            new_perf = 0.9 * old_perf + 0.1 * accuracy
        else:
            new_perf = accuracy

        self.performance_matrix[task_type][expert_id] = new_perf


# ============================================================================
# AGGREGATION STRATEGIES
# ============================================================================

class Aggregator(ABC):
    """Abstract base class for aggregating expert outputs"""

    @abstractmethod
    async def aggregate(
        self,
        expert_outputs: List[Tuple[ExpertOutput, float]]
    ) -> Dict[str, Any]:
        """
        Aggregate expert outputs into final result

        Args:
            expert_outputs: List of (ExpertOutput, weight) tuples

        Returns:
            Aggregated result
        """
        pass


class WeightedAverageAggregator(Aggregator):
    """Weighted average aggregation for numerical outputs"""

    async def aggregate(
        self,
        expert_outputs: List[Tuple[ExpertOutput, float]]
    ) -> Dict[str, Any]:
        """Aggregate via weighted average"""

        if not expert_outputs:
            raise ValueError("No expert outputs to aggregate")

        # Calculate weighted average of confidence scores
        total_weight = sum(weight for _, weight in expert_outputs)
        weighted_confidence = sum(
            output.confidence * weight
            for output, weight in expert_outputs
        ) / total_weight

        # Collect all results
        all_results = [output.result for output, _ in expert_outputs]

        # Aggregate reasoning
        reasoning_parts = [
            f"{output.expert_type.value}: {output.reasoning}"
            for output, _ in expert_outputs
        ]

        aggregated = {
            "result": all_results[0] if len(all_results) == 1 else all_results,
            "confidence": weighted_confidence,
            "reasoning": " | ".join(reasoning_parts),
            "expert_count": len(expert_outputs),
            "experts_consulted": [output.expert_id for output, _ in expert_outputs]
        }

        logger.info(
            f"Weighted aggregation complete: confidence={weighted_confidence:.2f}, "
            f"experts={len(expert_outputs)}"
        )

        return aggregated


class VotingAggregator(Aggregator):
    """Majority voting for classification/decision tasks"""

    async def aggregate(
        self,
        expert_outputs: List[Tuple[ExpertOutput, float]]
    ) -> Dict[str, Any]:
        """Aggregate via weighted voting"""

        if not expert_outputs:
            raise ValueError("No expert outputs to aggregate")

        # Extract decisions (assuming binary or categorical)
        votes: Dict[str, float] = {}

        for output, weight in expert_outputs:
            decision = str(output.result.get("recommendation", "neutral"))
            votes[decision] = votes.get(decision, 0.0) + weight * output.confidence

        # Find winner
        winner = max(votes.items(), key=lambda x: x[1])

        aggregated = {
            "result": winner[0],
            "confidence": winner[1] / sum(votes.values()),
            "vote_distribution": votes,
            "expert_count": len(expert_outputs),
            "experts_consulted": [output.expert_id for output, _ in expert_outputs]
        }

        logger.info(f"Voting aggregation complete: winner={winner[0]}, votes={votes}")

        return aggregated


# ============================================================================
# COMPLETE MoE AGENT
# ============================================================================

@dataclass
class MoEConfig:
    """Configuration for MoE agent"""
    moe_id: str
    gating_strategy: str = "confidence"  # "rule_based", "confidence", "learned"
    aggregation_strategy: str = "weighted_average"  # "weighted_average", "voting"
    top_k_experts: int = 2
    min_confidence_threshold: float = 0.5


class MoEAgent:
    """
    Complete Mixture of Experts agent

    Combines:
    - Multiple specialized experts
    - Intelligent gating/routing
    - Output aggregation

    Usage:
        moe = MoEAgent(config, experts)
        result = await moe.process_task(task)
    """

    def __init__(
        self,
        config: MoEConfig,
        experts: List[Expert],
        gating_network: Optional[GatingNetwork] = None,
        aggregator: Optional[Aggregator] = None
    ):
        """
        Initialize MoE agent

        Args:
            config: MoE configuration
            experts: List of available experts
            gating_network: Custom gating network (optional)
            aggregator: Custom aggregator (optional)
        """
        self.config = config
        self.experts = experts

        # Initialize gating network
        if gating_network:
            self.gating_network = gating_network
        elif config.gating_strategy == "rule_based":
            self.gating_network = RuleBasedGate()
        elif config.gating_strategy == "learned":
            self.gating_network = LearnedGate()
        else:  # confidence
            self.gating_network = ConfidenceGate()

        # Initialize aggregator
        if aggregator:
            self.aggregator = aggregator
        elif config.aggregation_strategy == "voting":
            self.aggregator = VotingAggregator()
        else:  # weighted_average
            self.aggregator = WeightedAverageAggregator()

        logger.info(
            f"MoE agent initialized: {config.moe_id}, "
            f"{len(experts)} experts, "
            f"gating={config.gating_strategy}, "
            f"aggregation={config.aggregation_strategy}"
        )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process task using MoE architecture

        Args:
            task: Task data and context

        Returns:
            Aggregated result from experts
        """
        logger.info(f"MoE {self.config.moe_id} processing task: {task.get('description', 'unknown')}")

        # Step 1: Route to appropriate experts
        selected_experts = await self.gating_network.route(
            task,
            self.experts,
            self.config.top_k_experts
        )

        # Step 2: Execute experts in parallel
        expert_tasks = [
            expert.analyze(task)
            for expert, _ in selected_experts
        ]
        expert_outputs = await asyncio.gather(*expert_tasks)

        # Step 3: Filter by confidence threshold
        filtered_outputs = [
            (output, weight)
            for (expert, weight), output in zip(selected_experts, expert_outputs)
            if output.confidence >= self.config.min_confidence_threshold
        ]

        if not filtered_outputs:
            logger.warning(
                f"No experts met confidence threshold {self.config.min_confidence_threshold}"
            )
            # Use best available
            filtered_outputs = [(expert_outputs[0], 1.0)]

        # Step 4: Aggregate expert outputs
        result = await self.aggregator.aggregate(filtered_outputs)

        logger.info(
            f"MoE processing complete: {len(filtered_outputs)} experts, "
            f"confidence={result['confidence']:.2f}"
        )

        return result

    def add_expert(self, expert: Expert):
        """Add new expert to MoE"""
        self.experts.append(expert)
        logger.info(f"Added expert {expert.expert_id} to MoE {self.config.moe_id}")

    def get_expert_performance(self) -> Dict[str, float]:
        """Get performance metrics for all experts"""
        return {
            expert.expert_id: expert.get_avg_performance()
            for expert in self.experts
        }
