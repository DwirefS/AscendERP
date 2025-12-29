"""
Unit Tests for SelfOps Agents

Tests the autonomous platform management agents:
- DataOps Agent
- AgentOps Agent
- SecOps Agent
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.core.agent.base import AgentContext, AgentConfig
from src.agents.selfops.dataops.dataops_agent import (
    DataOpsAgent,
    DataQualityMetrics,
    PipelineHealth,
    PipelineStatus,
    DataQualityIssueType
)
from src.agents.selfops.agentops.agentops_agent import (
    AgentOpsAgent,
    AgentPerformanceMetrics,
    AgentStatus,
    OptimizationType
)
from src.agents.selfops.secops.secops_agent import (
    SecOpsAgent,
    SecurityThreat,
    ComplianceViolation,
    ThreatLevel,
    ComplianceStandard
)


@pytest.fixture
def agent_context():
    """Agent context fixture."""
    return AgentContext(
        trace_id="test-trace-001",
        tenant_id="test-tenant",
        user_id="test-user"
    )


@pytest.fixture
def mock_memory():
    """Mock memory substrate."""
    memory = AsyncMock()
    memory.store_experience = AsyncMock()
    return memory


@pytest.fixture
def mock_policy():
    """Mock policy engine."""
    policy = AsyncMock()
    return policy


class TestDataOpsAgent:
    """Test DataOps Agent."""

    @pytest.fixture
    def dataops_agent(self):
        """DataOps agent fixture."""
        return DataOpsAgent()

    async def test_agent_initialization(self, dataops_agent):
        """Test agent initialization."""
        assert dataops_agent.config.name == "DataOps Agent"
        assert dataops_agent.quality_thresholds["completeness"] == 0.95
        assert dataops_agent.pipeline_thresholds["success_rate"] == 0.95

    async def test_perceive(self, dataops_agent, agent_context):
        """Test perception phase."""
        perception = await dataops_agent.perceive({}, agent_context)

        assert "datasets" in perception
        assert "pipelines" in perception
        assert "cost_trends" in perception
        assert "schema_changes" in perception

        assert len(perception["datasets"]) > 0
        assert len(perception["pipelines"]) > 0

    async def test_dataset_quality_metrics(self, dataops_agent):
        """Test dataset quality metrics generation."""
        datasets = await dataops_agent._get_dataset_metrics()

        assert len(datasets) > 0

        for dataset in datasets:
            assert isinstance(dataset, DataQualityMetrics)
            assert dataset.record_count >= 0
            assert 0 <= dataset.completeness_score <= 1
            assert 0 <= dataset.validity_score <= 1
            assert 0 <= dataset.consistency_score <= 1
            assert dataset.layer in ["bronze", "silver", "gold"]

    async def test_pipeline_health_metrics(self, dataops_agent):
        """Test pipeline health metrics."""
        pipelines = await dataops_agent._get_pipeline_health()

        assert len(pipelines) > 0

        for pipeline in pipelines:
            assert isinstance(pipeline, PipelineHealth)
            assert isinstance(pipeline.status, PipelineStatus)
            assert 0 <= pipeline.success_rate <= 1
            assert pipeline.avg_latency_minutes >= 0

    async def test_identify_issues(self, dataops_agent, agent_context):
        """Test issue identification."""
        perception = await dataops_agent.perceive({}, agent_context)
        issues = dataops_agent._identify_issues(perception)

        # Should identify issues based on thresholds
        assert isinstance(issues, list)

        # Check issue structure
        for issue in issues:
            assert "type" in issue
            assert "severity" in issue
            assert issue["type"] in ["data_quality", "pipeline_health"]

    async def test_prioritize_issues(self, dataops_agent):
        """Test issue prioritization."""
        issues = [
            {"severity": "medium", "type": "data_quality"},
            {"severity": "critical", "type": "pipeline_health"},
            {"severity": "high", "type": "data_quality"}
        ]

        prioritized = dataops_agent._prioritize_issues(issues)

        # Should be sorted by severity (critical > high > medium)
        assert prioritized[0]["severity"] == "critical"
        assert prioritized[-1]["severity"] == "medium"

    async def test_remediation_plan(self, dataops_agent):
        """Test remediation plan generation."""
        issues = [
            {"type": "data_quality", "dataset": "invoices", "severity": "high"},
            {"type": "pipeline_health", "pipeline": "customer_etl", "severity": "critical"}
        ]

        plan = dataops_agent._generate_remediation_plan(issues, {})

        assert "actions" in plan
        assert len(plan["actions"]) > 0
        assert "estimated_time" in plan
        assert "priority" in plan

    async def test_cost_optimization(self, dataops_agent, agent_context):
        """Test cost optimization identification."""
        perception = await dataops_agent.perceive({}, agent_context)
        optimizations = dataops_agent._identify_cost_optimizations(perception)

        assert isinstance(optimizations, list)

        for opt in optimizations:
            assert "type" in opt
            assert "savings_daily" in opt


class TestAgentOpsAgent:
    """Test AgentOps Agent."""

    @pytest.fixture
    def agentops_agent(self):
        """AgentOps agent fixture."""
        return AgentOpsAgent()

    async def test_agent_initialization(self, agentops_agent):
        """Test agent initialization."""
        assert agentops_agent.config.name == "AgentOps Agent"
        assert agentops_agent.performance_thresholds["latency_ms"] == 5000
        assert agentops_agent.performance_thresholds["success_rate"] == 0.95

    async def test_perceive(self, agentops_agent, agent_context):
        """Test perception phase."""
        perception = await agentops_agent.perceive({}, agent_context)

        assert "agent_metrics" in perception
        assert "llm_metrics" in perception
        assert "cost_trends" in perception

        assert len(perception["agent_metrics"]) > 0

    async def test_agent_performance_metrics(self, agentops_agent):
        """Test agent performance metrics."""
        metrics = await agentops_agent._get_agent_metrics()

        assert len(metrics) > 0

        for metric in metrics:
            assert isinstance(metric, AgentPerformanceMetrics)
            assert isinstance(metric.status, AgentStatus)
            assert 0 <= metric.success_rate <= 1
            assert metric.avg_latency_ms >= 0
            assert metric.total_executions >= 0

    async def test_identify_underperforming_agents(self, agentops_agent, agent_context):
        """Test identification of underperforming agents."""
        perception = await agentops_agent.perceive({}, agent_context)
        underperforming = agentops_agent._identify_underperforming(perception)

        assert isinstance(underperforming, list)

        for agent_issue in underperforming:
            assert "agent_id" in agent_issue
            assert "issue" in agent_issue
            assert "current_value" in agent_issue

    async def test_optimization_recommendations(self, agentops_agent):
        """Test optimization recommendation generation."""
        underperforming = [
            {
                "agent_id": "finance-agent",
                "issue": "high_latency",
                "current_value": 8000,
                "threshold": 5000
            }
        ]

        recommendations = agentops_agent._generate_recommendations(
            underperforming, {}, {}
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        for rec in recommendations:
            assert "optimization_type" in rec
            assert "expected_improvement" in rec
            assert "confidence" in rec

    async def test_ab_testing_setup(self, agentops_agent):
        """Test A/B testing setup."""
        test_config = {
            "agent_id": "finance-agent",
            "variant_a": {"prompt": "Original prompt"},
            "variant_b": {"prompt": "Optimized prompt"},
            "traffic_split": 0.5
        }

        result = await agentops_agent._setup_ab_test(test_config)

        assert "ab_test_id" in result
        assert "status" in result
        assert result["status"] == "running"


class TestSecOpsAgent:
    """Test SecOps Agent."""

    @pytest.fixture
    def secops_agent(self):
        """SecOps agent fixture."""
        return SecOpsAgent()

    async def test_agent_initialization(self, secops_agent):
        """Test agent initialization."""
        assert secops_agent.config.name == "SecOps Agent"
        assert secops_agent.threat_thresholds["failed_login_attempts"] == 5
        assert secops_agent.auto_remediate is True

    async def test_perceive(self, secops_agent, agent_context):
        """Test perception phase."""
        perception = await secops_agent.perceive({}, agent_context)

        assert "threats" in perception
        assert "vulnerabilities" in perception
        assert "compliance" in perception
        assert "anomalies" in perception
        assert "incidents" in perception
        assert "audit_summary" in perception

    async def test_threat_detection(self, secops_agent):
        """Test threat detection."""
        threats = await secops_agent._detect_threats()

        assert len(threats) > 0

        for threat in threats:
            assert isinstance(threat, SecurityThreat)
            assert isinstance(threat.severity, ThreatLevel)
            assert threat.threat_id
            assert threat.threat_type
            assert threat.source
            assert threat.target

    async def test_vulnerability_scanning(self, secops_agent):
        """Test vulnerability scanning."""
        scan_result = await secops_agent._scan_vulnerabilities()

        assert scan_result.scan_id
        assert scan_result.critical_count >= 0
        assert scan_result.high_count >= 0
        assert scan_result.medium_count >= 0
        assert scan_result.low_count >= 0
        assert len(scan_result.vulnerabilities) > 0

    async def test_compliance_checking(self, secops_agent):
        """Test compliance checking."""
        violations = await secops_agent._check_compliance()

        assert isinstance(violations, list)

        for violation in violations:
            assert isinstance(violation, ComplianceViolation)
            assert isinstance(violation.standard, ComplianceStandard)
            assert isinstance(violation.severity, ThreatLevel)
            assert violation.remediation_required in [True, False]

    async def test_anomaly_detection(self, secops_agent):
        """Test anomaly detection."""
        anomalies = await secops_agent._detect_anomalies()

        assert isinstance(anomalies, list)

        for anomaly in anomalies:
            assert "type" in anomaly
            assert "anomaly_score" in anomaly
            assert 0 <= anomaly["anomaly_score"] <= 1

    async def test_response_plan_generation(self, secops_agent):
        """Test security response plan generation."""
        threats = [
            SecurityThreat(
                threat_id="THR-001",
                threat_type="data_exfiltration",
                severity=ThreatLevel.CRITICAL,
                source="user@company.com",
                target="database",
                description="Large data export",
                indicators=["size:500MB"],
                detected_at=datetime.utcnow(),
                auto_remediation=True
            )
        ]

        violations = []

        plan = secops_agent._generate_response_plan(threats, violations, {})

        assert "actions" in plan
        assert len(plan["actions"]) > 0
        assert "estimated_time" in plan
        assert "auto_executable" in plan

        # Should have isolation action for critical threat
        isolation_actions = [a for a in plan["actions"] if a["action"] == "isolate_resource"]
        assert len(isolation_actions) > 0

    async def test_incident_escalation(self, secops_agent):
        """Test incident escalation."""
        critical_threat = SecurityThreat(
            threat_id="THR-CRITICAL",
            threat_type="ransomware",
            severity=ThreatLevel.CRITICAL,
            source="external",
            target="file_server",
            description="Ransomware detected",
            indicators=["encryption_pattern"],
            detected_at=datetime.utcnow()
        )

        result = await secops_agent._escalate_incident([critical_threat], [])

        assert "status" in result
        assert result["status"] == "escalated"
        assert "incident_id" in result
        assert "notification_sent" in result


@pytest.mark.integration
class TestSelfOpsIntegration:
    """Integration tests for SelfOps agents."""

    async def test_dataops_full_execution(self, mock_memory, mock_policy, agent_context):
        """Test full DataOps agent execution."""
        agent = DataOpsAgent()
        await agent.initialize(mock_memory, mock_policy, None)

        result = await agent.run(
            input_data={"command": "monitor_and_remediate"},
            context=agent_context
        )

        assert result.success
        assert result.latency_ms > 0
        assert len(result.actions_taken) >= 0

    async def test_agentops_full_execution(self, mock_memory, mock_policy, agent_context):
        """Test full AgentOps agent execution."""
        agent = AgentOpsAgent()
        await agent.initialize(mock_memory, mock_policy, None)

        result = await agent.run(
            input_data={"command": "optimize_agents"},
            context=agent_context
        )

        assert result.success
        assert result.latency_ms > 0

    async def test_secops_full_execution(self, mock_memory, mock_policy, agent_context):
        """Test full SecOps agent execution."""
        agent = SecOpsAgent()
        await agent.initialize(mock_memory, mock_policy, None)

        result = await agent.run(
            input_data={"command": "monitor_and_secure"},
            context=agent_context
        )

        assert result.success
        assert result.latency_ms > 0

    async def test_selfops_coordination(self, mock_memory, mock_policy, agent_context):
        """Test coordination between SelfOps agents."""
        # Initialize all three agents
        dataops = DataOpsAgent()
        agentops = AgentOpsAgent()
        secops = SecOpsAgent()

        await dataops.initialize(mock_memory, mock_policy, None)
        await agentops.initialize(mock_memory, mock_policy, None)
        await secops.initialize(mock_memory, mock_policy, None)

        # Run all agents
        dataops_result = await dataops.run(
            {"command": "check_quality"}, agent_context
        )
        agentops_result = await agentops.run(
            {"command": "check_performance"}, agent_context
        )
        secops_result = await secops.run(
            {"command": "check_security"}, agent_context
        )

        # All should complete successfully
        assert dataops_result.success
        assert agentops_result.success
        assert secops_result.success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
