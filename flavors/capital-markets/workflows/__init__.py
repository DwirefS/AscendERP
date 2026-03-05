"""
Capital Markets Workflows for ANTS/Ascend EOS.

LangGraph-based workflow orchestration for capital markets operations including:
- Trade lifecycle management with compliance checks and council deliberation
- Portfolio risk assessment with real-time monitoring and hedging
- Client onboarding with KYC/AML screening and risk evaluation
- Position monitoring with automated alerts and dashboard updates

Each workflow implements the PERCEIVE→RETRIEVE→REASON→EXECUTE→VERIFY→LEARN loop.

Workflows:
- trade_lifecycle: Complete trade flow from reception to post-execution learning
- risk_assessment: Portfolio risk analysis with committee escalation
- client_onboarding: Client acquisition with compliance vetting
- position_monitoring: Real-time position tracking with continuous monitoring
"""

from .trade_lifecycle import (
    create_trade_lifecycle_workflow,
    TradeLifecycleState,
)
from .risk_assessment import (
    create_risk_assessment_workflow,
    RiskAssessmentState,
)
from .client_onboarding import (
    create_client_onboarding_workflow,
    ClientOnboardingState,
)
from .position_monitoring import (
    create_position_monitoring_workflow,
    PositionMonitoringState,
)

__all__ = [
    # Trade Lifecycle
    "create_trade_lifecycle_workflow",
    "TradeLifecycleState",
    # Risk Assessment
    "create_risk_assessment_workflow",
    "RiskAssessmentState",
    # Client Onboarding
    "create_client_onboarding_workflow",
    "ClientOnboardingState",
    # Position Monitoring
    "create_position_monitoring_workflow",
    "PositionMonitoringState",
]
