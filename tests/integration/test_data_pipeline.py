"""
Integration tests for ANTS Data Pipeline (Bronze→Silver→Gold).
Tests the full medallion architecture flow.
"""
import pytest
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
import tempfile
import shutil

from pyspark.sql import SparkSession
from data.ingestion.connectors.erp_connector import ERPConnector, ConnectorConfig, DataRecord
from data.ingestion.bronze_writer import BronzeLayerWriter, BronzeWriterConfig
from data.etl.pipelines.bronze_to_silver import BronzeToSilverPipeline, PipelineConfig
from data.etl.pipelines.silver_to_gold import SilverToGoldPipeline, GoldLayerConfig
from data.etl.pipelines.orchestrator import DataPipelineOrchestrator, OrchestrationConfig


@pytest.fixture(scope="module")
def spark_session():
    """Create Spark session for tests."""
    spark = SparkSession.builder \
        .appName("ANTS_Pipeline_Tests") \
        .master("local[2]") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()

    yield spark

    spark.stop()


@pytest.fixture
def temp_lakehouse():
    """Create temporary lakehouse directory structure."""
    temp_dir = tempfile.mkdtemp(prefix="ants_lakehouse_")
    lakehouse_path = Path(temp_dir)

    # Create layer directories
    (lakehouse_path / "bronze").mkdir(parents=True)
    (lakehouse_path / "silver").mkdir(parents=True)
    (lakehouse_path / "gold").mkdir(parents=True)
    (lakehouse_path / "checkpoints").mkdir(parents=True)

    yield str(lakehouse_path)

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_transactions() -> List[DataRecord]:
    """Generate sample transaction records."""
    records = []
    base_date = datetime(2024, 1, 1)

    for i in range(100):
        record = DataRecord(
            id=f"txn_{i:04d}",
            source="erp_test",
            entity_type="transaction",
            data={
                "transaction_id": f"TXN-{i:04d}",
                "account_id": f"ACC-{(i % 10):03d}",
                "vendor_id": f"VND-{(i % 20):03d}",
                "amount": 1000.0 + (i * 100),
                "currency": "USD",
                "description": f"Test transaction {i}",
                "date": (base_date + timedelta(days=i)).isoformat(),
                "status": "posted" if i % 3 == 0 else "pending"
            },
            metadata={
                "source_system": "test_erp",
                "extraction_timestamp": datetime.utcnow().isoformat()
            },
            extracted_at=datetime.utcnow()
        )
        records.append(record)

    return records


class TestBronzeLayer:
    """Tests for Bronze layer ingestion."""

    @pytest.mark.asyncio
    async def test_bronze_writer_basic(self, temp_lakehouse, sample_transactions):
        """Test writing records to bronze layer."""
        config = BronzeWriterConfig(
            base_path=f"{temp_lakehouse}/bronze",
            batch_size=10,
            file_format="json",
            partition_by=["source", "entity_type", "ingestion_date"]
        )

        writer = BronzeLayerWriter(config)

        # Create async iterator from sample data
        async def record_generator():
            for record in sample_transactions:
                yield record

        # Write records
        stats = await writer.write_records(
            records=record_generator(),
            source_name="erp_test"
        )

        # Assertions
        assert stats["records_written"] == 100
        assert stats["files_created"] > 0
        assert stats["bytes_written"] > 0
        assert len(stats["partitions"]) > 0
        assert "error" not in stats

    @pytest.mark.asyncio
    async def test_bronze_partitioning(self, temp_lakehouse, sample_transactions):
        """Test that bronze layer correctly partitions data."""
        config = BronzeWriterConfig(
            base_path=f"{temp_lakehouse}/bronze",
            batch_size=50
        )

        writer = BronzeLayerWriter(config)

        async def record_generator():
            for record in sample_transactions:
                yield record

        stats = await writer.write_records(
            records=record_generator(),
            source_name="erp_test"
        )

        # Check partition structure exists
        bronze_path = Path(temp_lakehouse) / "bronze"
        partitions = list(bronze_path.glob("source=*/entity_type=*/ingestion_date=*"))

        assert len(partitions) > 0

        # Verify partition naming
        partition_str = str(partitions[0])
        assert "source=erp_test" in partition_str
        assert "entity_type=transaction" in partition_str


class TestSilverLayer:
    """Tests for Bronze→Silver transformation."""

    def test_bronze_to_silver_pipeline(self, spark_session, temp_lakehouse, sample_transactions):
        """Test full bronze to silver transformation."""
        # First, write bronze data
        bronze_path = f"{temp_lakehouse}/bronze/erp_test/transaction"
        Path(bronze_path).mkdir(parents=True)

        # Write sample data as JSONL
        data_file = Path(bronze_path) / "data_test.json"
        with open(data_file, 'w') as f:
            for record in sample_transactions:
                json_obj = {
                    "id": record.id,
                    "source": record.source,
                    "entity_type": record.entity_type,
                    "data": record.data,
                    "metadata": record.metadata,
                    "extracted_at": record.extracted_at.isoformat()
                }
                f.write(json.dumps(json_obj) + "\n")

        # Configure pipeline
        silver_path = f"{temp_lakehouse}/silver/transaction"
        checkpoint_path = f"{temp_lakehouse}/checkpoints/bronze_to_silver/transaction"

        config = PipelineConfig(
            source_path=bronze_path,
            target_path=silver_path,
            checkpoint_path=checkpoint_path,
            entity_type="transaction",
            partition_columns=["fiscal_year"]
        )

        # Run pipeline
        pipeline = BronzeToSilverPipeline(spark_session, config)
        result = pipeline.run()

        # Assertions
        assert result["success"] is True
        assert result["records_processed"] == 100
        assert result["quality_checks"]["duplicates_removed"] >= 0
        assert result["quality_checks"]["nulls_handled"] >= 0

        # Verify silver data exists
        silver_df = spark_session.read.format("delta").load(silver_path)
        assert silver_df.count() > 0

        # Verify required columns exist
        expected_columns = ["id", "account_id", "vendor_id", "amount", "fiscal_year"]
        for col in expected_columns:
            assert col in silver_df.columns

    def test_data_quality_checks(self, spark_session, temp_lakehouse):
        """Test data quality validation in silver layer."""
        # Create bronze data with quality issues
        bronze_path = f"{temp_lakehouse}/bronze/erp_test/transaction_quality"
        Path(bronze_path).mkdir(parents=True)

        # Data with duplicates and nulls
        bad_data = [
            {"id": "1", "data": {"amount": 100, "account_id": "A1"}},
            {"id": "1", "data": {"amount": 100, "account_id": "A1"}},  # Duplicate
            {"id": "2", "data": {"amount": None, "account_id": "A2"}},  # Null amount
            {"id": "3", "data": {"amount": 300, "account_id": None}},   # Null account
        ]

        data_file = Path(bronze_path) / "data_quality.json"
        with open(data_file, 'w') as f:
            for record in bad_data:
                f.write(json.dumps(record) + "\n")

        silver_path = f"{temp_lakehouse}/silver/transaction_quality"

        config = PipelineConfig(
            source_path=bronze_path,
            target_path=silver_path,
            checkpoint_path=f"{temp_lakehouse}/checkpoints/quality",
            entity_type="transaction"
        )

        pipeline = BronzeToSilverPipeline(spark_session, config)
        result = pipeline.run()

        # Verify quality metrics
        assert result["quality_checks"]["duplicates_removed"] >= 1


class TestGoldLayer:
    """Tests for Silver→Gold aggregation."""

    def test_silver_to_gold_transaction_kpis(self, spark_session, temp_lakehouse):
        """Test transaction KPI aggregation in gold layer."""
        # Create silver data
        silver_path = f"{temp_lakehouse}/silver/transaction_gold"

        # Sample silver data
        data = []
        base_date = datetime(2024, 1, 1)
        for i in range(50):
            data.append({
                "id": f"txn_{i}",
                "account_id": f"ACC_{i % 5}",
                "vendor_id": f"VND_{i % 10}",
                "amount": 1000.0 + (i * 100),
                "currency": "USD",
                "date": (base_date + timedelta(days=i)).isoformat(),
                "fiscal_year": 2024,
                "fiscal_quarter": "Q1",
                "fiscal_month": 1
            })

        # Write to delta
        df = spark_session.createDataFrame(data)
        df.write.format("delta").mode("overwrite").save(silver_path)

        # Configure gold pipeline
        gold_path = f"{temp_lakehouse}/gold/transaction/daily"

        config = GoldLayerConfig(
            source_path=silver_path,
            target_path=gold_path,
            entity_type="transaction",
            aggregation_level="daily",
            metrics=["count", "sum", "avg"]
        )

        # Run pipeline
        pipeline = SilverToGoldPipeline(spark_session, config)
        result = pipeline.run()

        # Assertions
        assert result["success"] is True
        assert result["records_processed"] == 50
        assert result["records_output"] > 0

        # Verify gold data
        gold_df = spark_session.read.format("delta").load(gold_path)
        assert gold_df.count() > 0

        # Verify KPI columns exist
        expected_kpi_cols = ["transaction_count", "total_amount", "avg_amount"]
        for col in expected_kpi_cols:
            assert col in gold_df.columns


class TestPipelineOrchestration:
    """Tests for end-to-end pipeline orchestration."""

    @pytest.mark.asyncio
    async def test_full_pipeline_orchestration(self, spark_session, temp_lakehouse):
        """Test complete pipeline orchestration."""
        config = OrchestrationConfig(
            anf_base_path=temp_lakehouse,
            entity_types=["transaction"],
            aggregation_levels=["daily"]
        )

        orchestrator = DataPipelineOrchestrator(
            config=config,
            spark=spark_session
        )

        # Mock connector config
        connector_config = ConnectorConfig(
            host="test_host",
            database="test_db",
            username="test_user",
            password="test_pass",
            port=1433
        )

        # Note: This would need a mock connector in real tests
        # For now, we test the orchestrator structure
        assert orchestrator.config.entity_types == ["transaction"]
        assert orchestrator.spark is not None

    def test_pipeline_error_handling(self, spark_session, temp_lakehouse):
        """Test pipeline handles errors gracefully."""
        # Try to run silver pipeline on non-existent bronze data
        config = PipelineConfig(
            source_path=f"{temp_lakehouse}/bronze/nonexistent",
            target_path=f"{temp_lakehouse}/silver/test",
            checkpoint_path=f"{temp_lakehouse}/checkpoints/test",
            entity_type="transaction"
        )

        pipeline = BronzeToSilverPipeline(spark_session, config)
        result = pipeline.run()

        # Should return error in result
        assert result["success"] is False
        assert "error" in result


class TestPipelinePerformance:
    """Performance tests for pipeline."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_large_volume_ingestion(self, temp_lakehouse):
        """Test bronze writer with large volume (10k records)."""
        config = BronzeWriterConfig(
            base_path=f"{temp_lakehouse}/bronze",
            batch_size=1000
        )

        writer = BronzeLayerWriter(config)

        # Generate 10k records
        async def large_record_generator():
            for i in range(10000):
                yield DataRecord(
                    id=f"large_{i}",
                    source="perf_test",
                    entity_type="transaction",
                    data={"amount": i * 100, "account": f"A{i % 100}"},
                    metadata={},
                    extracted_at=datetime.utcnow()
                )

        stats = await writer.write_records(
            records=large_record_generator(),
            source_name="perf_test"
        )

        # Verify all records written
        assert stats["records_written"] == 10000
        assert stats["duration_seconds"] < 60  # Should complete in <1 minute


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
