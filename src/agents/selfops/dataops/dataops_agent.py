"""
DataOps Agent - Autonomous Data Quality and Pipeline Management

The DataOps agent monitors and optimizes data pipelines across the medallion architecture:
- Bronze Layer: Raw data ingestion monitoring
- Silver Layer: Cleaned data quality validation
- Gold Layer: Business logic verification

Capabilities:
- Data quality monitoring (completeness, validity, consistency)
- Pipeline health tracking
- Anomaly detection in data flows
- Automated data remediation
- Cost optimization for data storage
- Schema drift detection

Part of SelfOps: Platform managing itself.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext, AgentResult
from src.core.observability import tracer, trace_agent_execution

logger = logging.getLogger(__name__)


class DataQualityIssueType(Enum):
    """Types of data quality issues."""
    MISSING_VALUES = "missing_values"
    INVALID_FORMAT = "invalid_format"
    DUPLICATE_RECORDS = "duplicate_records"
    SCHEMA_DRIFT = "schema_drift"
    ANOMALOUS_VALUES = "anomalous_values"
    LATE_ARRIVAL = "late_arrival"
    REFERENTIAL_INTEGRITY = "referential_integrity"


class PipelineStatus(Enum):
    """Pipeline health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    STOPPED = "stopped"


@dataclass
class DataQualityMetrics:
    """Data quality metrics for a dataset."""
    dataset_name: str
    layer: str  # bronze, silver, gold
    record_count: int
    completeness_score: float  # 0-1
    validity_score: float  # 0-1
    consistency_score: float  # 0-1
    overall_score: float  # 0-1
    issues: List[Dict[str, Any]]
    timestamp: datetime


@dataclass
class PipelineHealth:
    """Pipeline health metrics."""
    pipeline_name: str
    status: PipelineStatus
    success_rate: float  # 0-1
    avg_latency_minutes: float
    last_run: datetime
    failures_last_24h: int
    cost_last_24h: float


class DataOpsAgent(BaseAgent):
    """
    DataOps Agent for autonomous data quality and pipeline management.

    Monitors and optimizes:
    - Data quality across medallion architecture
    - Pipeline health and performance
    - Cost optimization
    - Schema evolution
    - Data lineage
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize DataOps agent.

        Args:
            config: Agent configuration
        """
        if config is None:
            config = AgentConfig(
                name="DataOps Agent",
                description="Autonomous data quality and pipeline management",
                tools=["data_profiler", "schema_validator", "anomaly_detector"]
            )

        super().__init__(config)

        # Data quality thresholds
        self.quality_thresholds = {
            "completeness": 0.95,
            "validity": 0.98,
            "consistency": 0.99,
            "overall": 0.95
        }

        # Pipeline health thresholds
        self.pipeline_thresholds = {
            "success_rate": 0.95,
            "max_latency_minutes": 60,
            "max_failures_24h": 3
        }

        logger.info("DataOps agent initialized")

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Perceive current data ecosystem state.

        Monitors:
        - Data quality metrics
        - Pipeline health
        - Cost trends
        - Schema changes
        """
        with tracer.start_as_current_span("dataops.perceive"):
            # Simulate fetching metrics (in production, query from monitoring)
            perception = {
                "datasets": await self._get_dataset_metrics(),
                "pipelines": await self._get_pipeline_health(),
                "cost_trends": await self._get_cost_trends(),
                "schema_changes": await self._detect_schema_drift()
            }

            logger.info(
                "DataOps perception complete",
                datasets=len(perception["datasets"]),
                pipelines=len(perception["pipelines"])
            )

            return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Retrieve historical context and patterns.

        Retrieves:
        - Similar quality issues resolved in past
        - Successful remediation strategies
        - Known anomaly patterns
        """
        with tracer.start_as_current_span("dataops.retrieve"):
            # Simulate memory retrieval
            retrieved = {
                "historical_issues": await self._retrieve_similar_issues(perception),
                "remediation_patterns": await self._retrieve_remediation_strategies(),
                "anomaly_signatures": await self._retrieve_anomaly_patterns()
            }

            return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Reason about data quality issues and remediation strategies.

        Analyzes:
        - Severity of quality issues
        - Impact on downstream systems
        - Remediation options
        - Cost optimization opportunities
        """
        with tracer.start_as_current_span("dataops.reason"):
            # Identify issues
            issues = self._identify_issues(perception)

            # Prioritize issues by impact
            prioritized = self._prioritize_issues(issues)

            # Generate remediation plan
            remediation_plan = self._generate_remediation_plan(
                prioritized,
                retrieved_context
            )

            # Identify optimizations
            optimizations = self._identify_cost_optimizations(perception)

            reasoning = {
                "issues_identified": len(issues),
                "critical_issues": [i for i in prioritized if i["severity"] == "critical"],
                "remediation_plan": remediation_plan,
                "optimizations": optimizations,
                "action": "remediate" if issues else "monitor"
            }

            logger.info(
                "DataOps reasoning complete",
                issues=len(issues),
                critical=len(reasoning["critical_issues"])
            )

            return reasoning

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """
        Execute data quality remediation or optimization actions.

        Actions:
        - Fix data quality issues
        - Restart failed pipelines
        - Optimize storage costs
        - Update schema validations
        """
        with tracer.start_as_current_span("dataops.execute") as span:
            action_type = action.get("action")
            span.set_attribute("action.type", action_type)

            if action_type == "remediate":
                return await self._execute_remediation(action.get("remediation_plan", {}))
            elif action_type == "optimize":
                return await self._execute_optimizations(action.get("optimizations", []))
            elif action_type == "alert":
                return await self._send_alert(action.get("critical_issues", []))
            else:
                return {"status": "monitoring", "action": "continue"}

    async def verify(
        self,
        result: Any,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Verify remediation effectiveness.

        Checks:
        - Quality metrics improved
        - Pipelines recovered
        - No new issues introduced
        """
        with tracer.start_as_current_span("dataops.verify"):
            # Simulate verification
            verification = {
                "complete": True,
                "metrics_improved": True,
                "new_issues": [],
                "confidence": 0.95
            }

            return verification

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext
    ):
        """
        Learn from remediation outcomes.

        Stores:
        - Successful remediation patterns
        - Failed approaches
        - Quality trends
        - Cost optimization results
        """
        with tracer.start_as_current_span("dataops.learn"):
            # Store learning in memory
            if self.memory:
                await self.memory.store_experience({
                    "type": "dataops_remediation",
                    "actions": actions_taken,
                    "context": input_data,
                    "timestamp": datetime.utcnow()
                })

            logger.info("DataOps learning complete", actions=len(actions_taken))

    # Helper methods

    async def _get_dataset_metrics(self) -> List[DataQualityMetrics]:
        """Get data quality metrics for all datasets."""
        # Simulate dataset metrics
        datasets = [
            DataQualityMetrics(
                dataset_name="invoices",
                layer="bronze",
                record_count=10000,
                completeness_score=0.98,
                validity_score=0.96,
                consistency_score=0.99,
                overall_score=0.97,
                issues=[{"type": "missing_values", "column": "tax_id", "count": 200}],
                timestamp=datetime.utcnow()
            ),
            DataQualityMetrics(
                dataset_name="customers",
                layer="silver",
                record_count=5000,
                completeness_score=0.99,
                validity_score=0.98,
                consistency_score=0.99,
                overall_score=0.98,
                issues=[],
                timestamp=datetime.utcnow()
            ),
            DataQualityMetrics(
                dataset_name="sales",
                layer="gold",
                record_count=50000,
                completeness_score=1.0,
                validity_score=0.99,
                consistency_score=1.0,
                overall_score=0.99,
                issues=[],
                timestamp=datetime.utcnow()
            )
        ]
        return datasets

    async def _get_pipeline_health(self) -> List[PipelineHealth]:
        """Get health status of data pipelines."""
        # Simulate pipeline health
        pipelines = [
            PipelineHealth(
                pipeline_name="invoice_ingestion",
                status=PipelineStatus.HEALTHY,
                success_rate=0.98,
                avg_latency_minutes=15.5,
                last_run=datetime.utcnow() - timedelta(minutes=10),
                failures_last_24h=1,
                cost_last_24h=12.50
            ),
            PipelineHealth(
                pipeline_name="customer_etl",
                status=PipelineStatus.DEGRADED,
                success_rate=0.92,
                avg_latency_minutes=45.2,
                last_run=datetime.utcnow() - timedelta(hours=2),
                failures_last_24h=3,
                cost_last_24h=25.75
            )
        ]
        return pipelines

    async def _get_cost_trends(self) -> Dict[str, Any]:
        """Analyze cost trends for data processing."""
        return {
            "daily_cost": 125.50,
            "trend": "increasing",
            "storage_cost": 45.20,
            "compute_cost": 80.30,
            "optimization_potential": 35.0  # dollars/day
        }

    async def _detect_schema_drift(self) -> List[Dict[str, Any]]:
        """Detect schema changes in datasets."""
        return [
            {
                "dataset": "invoices",
                "change": "new_column",
                "column": "discount_code",
                "detected_at": datetime.utcnow().isoformat()
            }
        ]

    async def _retrieve_similar_issues(self, perception: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve similar quality issues from memory."""
        # Would query memory substrate
        return [
            {
                "issue": "missing_tax_id",
                "remediation": "lookup_from_vendor_master",
                "success_rate": 0.92
            }
        ]

    async def _retrieve_remediation_strategies(self) -> List[Dict[str, Any]]:
        """Retrieve successful remediation strategies."""
        return [
            {
                "strategy": "backfill_from_source",
                "success_rate": 0.95,
                "avg_time_minutes": 30
            }
        ]

    async def _retrieve_anomaly_patterns(self) -> List[Dict[str, Any]]:
        """Retrieve known anomaly patterns."""
        return []

    def _identify_issues(self, perception: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify data quality and pipeline issues."""
        issues = []

        # Check dataset quality
        for dataset in perception["datasets"]:
            if dataset.overall_score < self.quality_thresholds["overall"]:
                issues.append({
                    "type": "data_quality",
                    "dataset": dataset.dataset_name,
                    "layer": dataset.layer,
                    "score": dataset.overall_score,
                    "threshold": self.quality_thresholds["overall"],
                    "severity": "high" if dataset.overall_score < 0.90 else "medium"
                })

        # Check pipeline health
        for pipeline in perception["pipelines"]:
            if pipeline.status != PipelineStatus.HEALTHY:
                issues.append({
                    "type": "pipeline_health",
                    "pipeline": pipeline.pipeline_name,
                    "status": pipeline.status.value,
                    "success_rate": pipeline.success_rate,
                    "severity": "critical" if pipeline.status == PipelineStatus.FAILING else "high"
                })

        return issues

    def _prioritize_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize issues by severity and impact."""
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(issues, key=lambda x: severity_order[x["severity"]])

    def _generate_remediation_plan(
        self,
        issues: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate remediation plan for identified issues."""
        if not issues:
            return {"actions": [], "estimated_time": 0}

        actions = []
        for issue in issues:
            if issue["type"] == "data_quality":
                actions.append({
                    "action": "run_data_quality_fix",
                    "dataset": issue["dataset"],
                    "fix_type": "automated_remediation"
                })
            elif issue["type"] == "pipeline_health":
                actions.append({
                    "action": "restart_pipeline",
                    "pipeline": issue["pipeline"],
                    "with_retry": True
                })

        return {
            "actions": actions,
            "estimated_time": len(actions) * 15,  # minutes
            "priority": "high" if any(i["severity"] == "critical" for i in issues) else "medium"
        }

    def _identify_cost_optimizations(self, perception: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify cost optimization opportunities."""
        optimizations = []

        cost_trends = perception["cost_trends"]
        if cost_trends["optimization_potential"] > 20:
            optimizations.append({
                "type": "move_to_cool_tier",
                "savings_daily": 15.0,
                "datasets": ["old_invoices", "archived_customers"]
            })
            optimizations.append({
                "type": "compress_bronze_layer",
                "savings_daily": 10.0,
                "datasets": ["raw_events"]
            })

        return optimizations

    async def _execute_remediation(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute remediation actions."""
        results = []
        for action in plan.get("actions", []):
            # Simulate remediation
            await asyncio.sleep(0.1)
            results.append({
                "action": action["action"],
                "status": "success",
                "timestamp": datetime.utcnow().isoformat()
            })

        return {
            "status": "completed",
            "actions_executed": len(results),
            "results": results
        }

    async def _execute_optimizations(self, optimizations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute cost optimization actions."""
        savings = sum(opt.get("savings_daily", 0) for opt in optimizations)
        return {
            "status": "optimizations_applied",
            "total_savings_daily": savings,
            "optimizations": len(optimizations)
        }

    async def _send_alert(self, critical_issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send alert for critical issues."""
        logger.warning(
            "Critical data quality issues detected",
            issues=len(critical_issues),
            details=critical_issues
        )
        return {
            "status": "alert_sent",
            "issues": len(critical_issues)
        }


async def demo_dataops_agent():
    """Demonstrate DataOps agent capabilities."""
    print("=" * 80)
    print("DataOps Agent Demo - Autonomous Data Quality Management")
    print("=" * 80)
    print()

    # Initialize agent
    agent = DataOpsAgent()

    # Initialize dependencies (would be real implementations in production)
    from src.core.memory.substrate import MemorySubstrate
    from src.core.policy.engine import PolicyEngine

    memory = MemorySubstrate()
    policy = PolicyEngine()
    llm = None  # Not needed for this agent

    await agent.initialize(memory, policy, llm)

    # Create context
    context = AgentContext(
        trace_id="dataops-demo-001",
        tenant_id="tenant-123",
        user_id="system"
    )

    # Run agent
    print("Running DataOps agent...")
    result = await agent.run(
        input_data={"command": "monitor_and_remediate"},
        context=context
    )

    print(f"\n✓ Agent execution complete")
    print(f"Success: {result.success}")
    print(f"Actions taken: {len(result.actions_taken)}")
    print(f"Latency: {result.latency_ms:.2f}ms")
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo_dataops_agent())
