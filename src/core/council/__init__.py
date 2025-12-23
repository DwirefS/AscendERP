"""
Council Framework - Collective Intelligence for Decision Making

This module implements the Decision-Making Council architecture where diverse
AI agents engage in structured debate to reach consensus on strategic decisions.

Based on:
- Condorcet Jury Theorem: Ensemble accuracy > individual accuracy
- Diversity Prediction Theorem: Collective error = avg error - diversity
- Multi-Agent Collaboration research (arXiv:2501.06322, 2025)

Key Components:
- BaseCouncil: Abstract council orchestrator
- DecisionMaker: Deliberation engine with debate protocols
- ConsensusBuilder: Weighted voting, Delphi, Nash equilibrium
- CouncilMember: Individual agent within council
"""

from src.core.council.base_council import BaseCouncil, CouncilConfig
from src.core.council.decision_maker import DecisionMaker, DeliberationPhase
from src.core.council.consensus import (
    ConsensusBuilder,
    WeightedVoting,
    DelphiMethod,
    NashNegotiation,
    ConsensusAlgorithm
)
from src.core.council.member import CouncilMember, MemberRole, Vote

__all__ = [
    "BaseCouncil",
    "CouncilConfig",
    "DecisionMaker",
    "DeliberationPhase",
    "ConsensusBuilder",
    "WeightedVoting",
    "DelphiMethod",
    "NashNegotiation",
    "ConsensusAlgorithm",
    "CouncilMember",
    "MemberRole",
    "Vote",
]
