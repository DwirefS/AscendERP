"""
Bronze to Silver ETL Pipeline.
Cleans and validates raw data for the Medallion architecture.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructType
import structlog

logger = structlog.get_logger()


@dataclass
class PipelineConfig:
    """Configuration for ETL pipeline."""
    source_path: str
    target_path: str
    checkpoint_path: str
    entity_type: str
    partition_columns: List[str]
    quality_threshold: float = 0.95


class BronzeToSilverPipeline:
    """
    Pipeline for transforming Bronze (raw) data to Silver (cleaned).
    Implements data quality checks and standardization.
    """

    def __init__(
        self,
        spark: SparkSession,
        config: PipelineConfig
    ):
        self.spark = spark
        self.config = config
        self._quality_metrics = {}

    def run(self) -> Dict[str, Any]:
        """Execute the pipeline."""
        logger.info(
            "starting_bronze_to_silver",
            entity_type=self.config.entity_type
        )

        try:
            # Read bronze data
            bronze_df = self._read_bronze()

            # Apply transformations
            cleaned_df = self._clean_data(bronze_df)
            validated_df = self._validate_data(cleaned_df)
            enriched_df = self._enrich_data(validated_df)

            # Write to silver
            self._write_silver(enriched_df)

            # Return metrics
            return {
                "success": True,
                "records_processed": bronze_df.count(),
                "records_output": enriched_df.count(),
                "quality_metrics": self._quality_metrics,
                "completed_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error("pipeline_failed", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    def _read_bronze(self) -> DataFrame:
        """Read data from bronze layer."""
        logger.info("reading_bronze", path=self.config.source_path)

        return self.spark.read \
            .format("delta") \
            .load(self.config.source_path)

    def _clean_data(self, df: DataFrame) -> DataFrame:
        """Clean and standardize data."""
        logger.info("cleaning_data")

        # Remove duplicates
        df = df.dropDuplicates()

        # Trim string columns
        string_cols = [f.name for f in df.schema.fields if f.dataType.simpleString() == "string"]
        for col in string_cols:
            df = df.withColumn(col, F.trim(F.col(col)))

        # Standardize null representations
        df = df.na.replace(["", "NULL", "null", "N/A"], None)

        # Add metadata
        df = df.withColumn("_cleaned_at", F.current_timestamp())
        df = df.withColumn("_source_file", F.input_file_name())

        return df

    def _validate_data(self, df: DataFrame) -> DataFrame:
        """Validate data quality."""
        logger.info("validating_data")

        original_count = df.count()

        # Check for required fields (entity-specific)
        required_fields = self._get_required_fields()
        for field in required_fields:
            df = df.filter(F.col(field).isNotNull())

        # Data type validation
        df = self._validate_data_types(df)

        # Business rule validation
        df = self._validate_business_rules(df)

        final_count = df.count()

        # Calculate quality metrics
        self._quality_metrics["completeness"] = final_count / original_count if original_count > 0 else 0
        self._quality_metrics["records_dropped"] = original_count - final_count

        # Check quality threshold
        if self._quality_metrics["completeness"] < self.config.quality_threshold:
            logger.warning(
                "quality_below_threshold",
                completeness=self._quality_metrics["completeness"],
                threshold=self.config.quality_threshold
            )

        return df

    def _enrich_data(self, df: DataFrame) -> DataFrame:
        """Enrich data with derived fields."""
        logger.info("enriching_data")

        entity_type = self.config.entity_type

        if entity_type == "transaction":
            df = self._enrich_transaction(df)
        elif entity_type == "account":
            df = self._enrich_account(df)
        elif entity_type == "invoice":
            df = self._enrich_invoice(df)

        # Add processing metadata
        df = df.withColumn("_processed_at", F.current_timestamp())
        df = df.withColumn("_pipeline_version", F.lit("1.0.0"))

        return df

    def _write_silver(self, df: DataFrame):
        """Write data to silver layer."""
        logger.info("writing_silver", path=self.config.target_path)

        writer = df.write \
            .format("delta") \
            .mode("append") \
            .option("mergeSchema", "true")

        if self.config.partition_columns:
            writer = writer.partitionBy(*self.config.partition_columns)

        writer.save(self.config.target_path)

        logger.info("silver_write_complete", records=df.count())

    def _get_required_fields(self) -> List[str]:
        """Get required fields for entity type."""
        required = {
            "transaction": ["id", "date", "amount", "account_id"],
            "account": ["id", "name", "type"],
            "invoice": ["id", "vendor_id", "amount"],
            "vendor": ["id", "name"]
        }
        return required.get(self.config.entity_type, ["id"])

    def _validate_data_types(self, df: DataFrame) -> DataFrame:
        """Validate and cast data types."""
        entity_type = self.config.entity_type

        if entity_type == "transaction":
            df = df.withColumn("amount", F.col("amount").cast("decimal(18,2)"))
            df = df.withColumn("date", F.to_timestamp("date"))
            df = df.filter(F.col("amount").isNotNull())

        return df

    def _validate_business_rules(self, df: DataFrame) -> DataFrame:
        """Apply business rule validation."""
        entity_type = self.config.entity_type

        if entity_type == "transaction":
            # Amount must be positive
            df = df.filter(F.col("amount") >= 0)

        return df

    def _enrich_transaction(self, df: DataFrame) -> DataFrame:
        """Enrich transaction data."""
        # Add fiscal period
        df = df.withColumn(
            "fiscal_year",
            F.year("date")
        )
        df = df.withColumn(
            "fiscal_quarter",
            F.quarter("date")
        )
        df = df.withColumn(
            "fiscal_month",
            F.month("date")
        )

        # Categorize amount
        df = df.withColumn(
            "amount_category",
            F.when(F.col("amount") < 100, "small")
            .when(F.col("amount") < 10000, "medium")
            .otherwise("large")
        )

        return df

    def _enrich_account(self, df: DataFrame) -> DataFrame:
        """Enrich account data."""
        return df

    def _enrich_invoice(self, df: DataFrame) -> DataFrame:
        """Enrich invoice data."""
        # Calculate days until due
        df = df.withColumn(
            "days_until_due",
            F.datediff(F.col("due_date"), F.current_date())
        )

        return df
