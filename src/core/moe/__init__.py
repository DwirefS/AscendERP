"""
Mixture of Experts (MoE) Framework

Implements MoE architecture where specialized expert agents collaborate
on complex tasks via intelligent routing and aggregation.

Based on research:
- Comprehensive Survey of MoE (arXiv:2503.07137, Mar 2025)
- MoMoE: Mixture of Expert Agent Model (arXiv:2511.13983, Nov 2025)
- DeepSeek-V3 validates MoE as production-ready (Jan 2025)

Key Components:
- Expert: Specialized sub-agent optimized for specific domain/capability
- GatingNetwork: Routes inputs to most appropriate expert(s)
- Aggregator: Combines expert outputs into final result
- MoEAgent: Complete MoE agent with routing and aggregation
"""

from src.core.moe.expert import Expert, DomainExpert, CapabilityExpert
from src.core.moe.gating import (
    GatingNetwork,
    LearnedGate,
    RuleBasedGate,
    ConfidenceGate
)
from src.core.moe.aggregation import (
    Aggregator,
    WeightedAverageAggregator,
    VotingAggregator,
    StackedAggregator
)
from src.core.moe.moe_agent import MoEAgent, MoEConfig

__all__ = [
    "Expert",
    "DomainExpert",
    "CapabilityExpert",
    "GatingNetwork",
    "LearnedGate",
    "RuleBasedGate",
    "ConfidenceGate",
    "Aggregator",
    "WeightedAverageAggregator",
    "VotingAggregator",
    "StackedAggregator",
    "MoEAgent",
    "MoEConfig",
]
