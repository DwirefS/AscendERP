"""
Data Pipeline Orchestrator for ANTS Lakehouse.
Coordinates Bronze→Silver→Gold transformations.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio
import structlog

from pyspark.sql import SparkSession
from data.ingestion.connectors.erp_connector import ERPConnector, ConnectorConfig
from data.etl.pipelines.bronze_to_silver import BronzeToSilverPipeline, PipelineConfig
from data.etl.pipelines.silver_to_gold import SilverToGoldPipeline, GoldLayerConfig

logger = structlog.get_logger()


class PipelineStage(Enum):
    """Pipeline stages."""
    INGESTION = "ingestion"
    BRONZE_TO_SILVER = "bronze_to_silver"
    SILVER_TO_GOLD = "silver_to_gold"


@dataclass
class OrchestrationConfig:
    """Configuration for pipeline orchestration."""
    anf_base_path: str = "/mnt/anf/lakehouse"
    bronze_path_template: str = "{base}/bronze/{source}/{entity}"
    silver_path_template: str = "{base}/silver/{entity}"
    gold_path_template: str = "{base}/gold/{entity}/{aggregation}"
    checkpoint_path: str = "/mnt/anf/lakehouse/checkpoints"
    entity_types: List[str] = None
    aggregation_levels: List[str] = None

    def __post_init__(self):
        if self.entity_types is None:
            self.entity_types = ["transaction", "invoice", "account", "vendor"]
        if self.aggregation_levels is None:
            self.aggregation_levels = ["daily", "monthly"]


class DataPipelineOrchestrator:
    """
    Orchestrates end-to-end data pipeline:
    Source → Bronze → Silver → Gold
    """

    def __init__(
        self,
        config: OrchestrationConfig,
        spark: SparkSession
    ):
        self.config = config
        self.spark = spark
        self._execution_history = []

    async def run_full_pipeline(
        self,
        source_name: str,
        source_config: ConnectorConfig,
        entity_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run complete pipeline for all entity types.
        """
        logger.info(
            "starting_full_pipeline",
            source=source_name,
            entities=entity_types or self.config.entity_types
        )

        execution_start = datetime.utcnow()
        results = {
            "execution_id": f"pipeline-{execution_start.strftime('%Y%m%d%H%M%S')}",
            "source": source_name,
            "stages": {},
            "status": "running"
        }

        try:
            entities = entity_types or self.config.entity_types

            # Stage 1: Ingestion (Source → Bronze)
            ingestion_results = await self._run_ingestion(
                source_name,
                source_config,
                entities
            )
            results["stages"]["ingestion"] = ingestion_results

            # Stage 2: Bronze → Silver
            silver_results = self._run_bronze_to_silver(entities)
            results["stages"]["bronze_to_silver"] = silver_results

            # Stage 3: Silver → Gold
            gold_results = self._run_silver_to_gold(entities)
            results["stages"]["silver_to_gold"] = gold_results

            results["status"] = "completed"
            results["completed_at"] = datetime.utcnow().isoformat()
            results["duration_seconds"] = (datetime.utcnow() - execution_start).total_seconds()

            self._execution_history.append(results)

            logger.info(
                "pipeline_completed",
                execution_id=results["execution_id"],
                duration=results["duration_seconds"]
            )

        except Exception as e:
            logger.error("pipeline_failed", error=str(e))
            results["status"] = "failed"
            results["error"] = str(e)

        return results

    async def _run_ingestion(
        self,
        source_name: str,
        source_config: ConnectorConfig,
        entity_types: List[str]
    ) -> Dict[str, Any]:
        """Ingest data from source to bronze layer."""
        logger.info("starting_ingestion", source=source_name)

        connector = ERPConnector(source_config)
        await connector.connect()

        ingestion_results = {}

        try:
            for entity_type in entity_types:
                logger.info("ingesting_entity", entity=entity_type)

                bronze_path = self.config.bronze_path_template.format(
                    base=self.config.anf_base_path,
                    source=source_name,
                    entity=entity_type
                )

                records_ingested = 0

                # Extract and write to bronze
                async for record in connector.extract(entity_type=entity_type):
                    # In production, batch writes for efficiency
                    # Here we simulate writing to bronze
                    records_ingested += 1

                    if records_ingested % 1000 == 0:
                        logger.info(
                            "ingestion_progress",
                            entity=entity_type,
                            records=records_ingested
                        )

                ingestion_results[entity_type] = {
                    "success": True,
                    "records_ingested": records_ingested,
                    "bronze_path": bronze_path
                }

                logger.info(
                    "entity_ingestion_complete",
                    entity=entity_type,
                    records=records_ingested
                )

        finally:
            await connector.disconnect()

        return ingestion_results

    def _run_bronze_to_silver(
        self,
        entity_types: List[str]
    ) -> Dict[str, Any]:
        """Transform bronze data to silver layer."""
        logger.info("starting_bronze_to_silver")

        silver_results = {}

        for entity_type in entity_types:
            logger.info("transforming_to_silver", entity=entity_type)

            bronze_path = self.config.bronze_path_template.format(
                base=self.config.anf_base_path,
                source="erp",  # Default source
                entity=entity_type
            )

            silver_path = self.config.silver_path_template.format(
                base=self.config.anf_base_path,
                entity=entity_type
            )

            pipeline_config = PipelineConfig(
                source_path=bronze_path,
                target_path=silver_path,
                checkpoint_path=f"{self.config.checkpoint_path}/bronze_to_silver/{entity_type}",
                entity_type=entity_type,
                partition_columns=["fiscal_year", "fiscal_month"] if entity_type == "transaction" else []
            )

            pipeline = BronzeToSilverPipeline(
                spark=self.spark,
                config=pipeline_config
            )

            result = pipeline.run()
            silver_results[entity_type] = result

            logger.info(
                "silver_transformation_complete",
                entity=entity_type,
                success=result["success"]
            )

        return silver_results

    def _run_silver_to_gold(
        self,
        entity_types: List[str]
    ) -> Dict[str, Any]:
        """Aggregate silver data to gold layer."""
        logger.info("starting_silver_to_gold")

        gold_results = {}

        for entity_type in entity_types:
            for aggregation_level in self.config.aggregation_levels:
                key = f"{entity_type}_{aggregation_level}"
                logger.info(
                    "creating_gold_view",
                    entity=entity_type,
                    aggregation=aggregation_level
                )

                silver_path = self.config.silver_path_template.format(
                    base=self.config.anf_base_path,
                    entity=entity_type
                )

                gold_path = self.config.gold_path_template.format(
                    base=self.config.anf_base_path,
                    entity=entity_type,
                    aggregation=aggregation_level
                )

                gold_config = GoldLayerConfig(
                    source_path=silver_path,
                    target_path=gold_path,
                    entity_type=entity_type,
                    aggregation_level=aggregation_level,
                    metrics=self._get_metrics_for_entity(entity_type)
                )

                pipeline = SilverToGoldPipeline(
                    spark=self.spark,
                    config=gold_config
                )

                result = pipeline.run()
                gold_results[key] = result

                logger.info(
                    "gold_view_complete",
                    entity=entity_type,
                    aggregation=aggregation_level,
                    success=result["success"]
                )

        return gold_results

    def _get_metrics_for_entity(self, entity_type: str) -> List[str]:
        """Get relevant metrics for entity type."""
        metrics_map = {
            "transaction": ["count", "sum", "avg", "variance"],
            "invoice": ["count", "sum", "aging"],
            "sales": ["revenue", "quantity", "customers"],
            "inventory": ["turnover", "stock_level", "stockout_risk"]
        }
        return metrics_map.get(entity_type, ["count"])

    async def run_incremental_update(
        self,
        entity_type: str,
        since: datetime
    ) -> Dict[str, Any]:
        """
        Run incremental update for a specific entity.
        Only processes new/changed records since timestamp.
        """
        logger.info(
            "starting_incremental_update",
            entity=entity_type,
            since=since.isoformat()
        )

        # Implementation would filter by timestamp in each stage
        # This is a simplified version
        pass

    def get_pipeline_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a pipeline execution."""
        for execution in self._execution_history:
            if execution["execution_id"] == execution_id:
                return execution
        return None

    def get_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent pipeline executions."""
        return self._execution_history[-limit:]


class PipelineScheduler:
    """
    Schedules periodic pipeline runs.
    """

    def __init__(
        self,
        orchestrator: DataPipelineOrchestrator,
        schedule_config: Dict[str, Any]
    ):
        self.orchestrator = orchestrator
        self.schedule_config = schedule_config
        self._running = False

    async def start(self):
        """Start the scheduler."""
        self._running = True
        logger.info("pipeline_scheduler_started")

        while self._running:
            try:
                # Check schedule and run pipelines
                await self._check_and_run()

                # Sleep for check interval
                await asyncio.sleep(self.schedule_config.get("check_interval_seconds", 300))

            except Exception as e:
                logger.error("scheduler_error", error=str(e))

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        logger.info("pipeline_scheduler_stopped")

    async def _check_and_run(self):
        """Check schedule and trigger pipeline runs."""
        # Implementation would check time-based triggers
        # and run pipelines accordingly
        pass
