"""
Silver to Gold ETL Pipeline.
Creates business-ready aggregated views for the Medallion architecture.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window
import structlog

logger = structlog.get_logger()


@dataclass
class GoldLayerConfig:
    """Configuration for Gold layer pipeline."""
    source_path: str
    target_path: str
    entity_type: str
    aggregation_level: str  # daily, weekly, monthly, yearly
    metrics: List[str]


class SilverToGoldPipeline:
    """
    Pipeline for transforming Silver (cleaned) data to Gold (business-ready).
    Creates aggregated views optimized for analytics and agent queries.
    """

    def __init__(
        self,
        spark: SparkSession,
        config: GoldLayerConfig
    ):
        self.spark = spark
        self.config = config

    def run(self) -> Dict[str, Any]:
        """Execute the pipeline."""
        logger.info(
            "starting_silver_to_gold",
            entity_type=self.config.entity_type,
            aggregation=self.config.aggregation_level
        )

        try:
            # Read silver data
            silver_df = self._read_silver()

            # Create gold views
            gold_df = self._create_gold_view(silver_df)

            # Write to gold
            self._write_gold(gold_df)

            return {
                "success": True,
                "records_processed": silver_df.count(),
                "records_output": gold_df.count(),
                "aggregation_level": self.config.aggregation_level,
                "completed_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error("gold_pipeline_failed", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    def _read_silver(self) -> DataFrame:
        """Read data from silver layer."""
        logger.info("reading_silver", path=self.config.source_path)

        return self.spark.read \
            .format("delta") \
            .load(self.config.source_path)

    def _create_gold_view(self, df: DataFrame) -> DataFrame:
        """Create business-ready aggregated view."""
        entity_type = self.config.entity_type

        if entity_type == "transaction":
            return self._create_transaction_kpis(df)
        elif entity_type == "invoice":
            return self._create_invoice_metrics(df)
        elif entity_type == "sales":
            return self._create_sales_analytics(df)
        elif entity_type == "inventory":
            return self._create_inventory_metrics(df)
        else:
            # Generic aggregation
            return self._create_generic_aggregation(df)

    def _create_transaction_kpis(self, df: DataFrame) -> DataFrame:
        """Create transaction KPIs (Finance Gold layer)."""
        logger.info("creating_transaction_kpis")

        agg_level = self.config.aggregation_level

        # Define time grouping
        if agg_level == "daily":
            time_col = F.to_date("date")
        elif agg_level == "weekly":
            time_col = F.date_trunc("week", "date")
        elif agg_level == "monthly":
            time_col = F.date_trunc("month", "date")
        elif agg_level == "yearly":
            time_col = F.date_trunc("year", "date")
        else:
            time_col = F.to_date("date")

        # Aggregate by time period and account
        gold_df = df.groupBy(
            time_col.alias("period"),
            "account_id",
            "fiscal_year",
            "fiscal_quarter"
        ).agg(
            F.count("id").alias("transaction_count"),
            F.sum("amount").alias("total_amount"),
            F.avg("amount").alias("avg_amount"),
            F.min("amount").alias("min_amount"),
            F.max("amount").alias("max_amount"),
            F.stddev("amount").alias("stddev_amount"),
            F.countDistinct("vendor_id").alias("unique_vendors"),
            F.first("currency").alias("currency")
        )

        # Add derived metrics
        gold_df = gold_df.withColumn(
            "amount_variance",
            F.col("stddev_amount") / F.col("avg_amount")
        )

        # Add period-over-period comparison
        window_spec = Window.partitionBy("account_id").orderBy("period")
        gold_df = gold_df.withColumn(
            "prev_period_amount",
            F.lag("total_amount", 1).over(window_spec)
        )
        gold_df = gold_df.withColumn(
            "amount_change_pct",
            (F.col("total_amount") - F.col("prev_period_amount")) / F.col("prev_period_amount") * 100
        )

        # Add metadata
        gold_df = gold_df.withColumn("_aggregation_level", F.lit(agg_level))
        gold_df = gold_df.withColumn("_created_at", F.current_timestamp())

        return gold_df

    def _create_invoice_metrics(self, df: DataFrame) -> DataFrame:
        """Create invoice aging and payment metrics."""
        logger.info("creating_invoice_metrics")

        # Aging buckets
        gold_df = df.withColumn(
            "aging_bucket",
            F.when(F.col("days_until_due") > 30, "current")
            .when(F.col("days_until_due").between(0, 30), "30_days")
            .when(F.col("days_until_due").between(-30, 0), "60_days")
            .when(F.col("days_until_due").between(-60, -30), "90_days")
            .otherwise("over_90_days")
        )

        # Aggregate by vendor and aging bucket
        gold_df = gold_df.groupBy(
            F.date_trunc(self.config.aggregation_level, "created_at").alias("period"),
            "vendor_id",
            "aging_bucket"
        ).agg(
            F.count("id").alias("invoice_count"),
            F.sum("amount").alias("total_outstanding"),
            F.avg("amount").alias("avg_invoice_amount")
        )

        # Pivot aging buckets
        gold_df = gold_df.groupBy("period", "vendor_id").pivot("aging_bucket").agg(
            F.first("total_outstanding")
        )

        gold_df = gold_df.withColumn("_created_at", F.current_timestamp())

        return gold_df

    def _create_sales_analytics(self, df: DataFrame) -> DataFrame:
        """Create sales performance metrics."""
        logger.info("creating_sales_analytics")

        gold_df = df.groupBy(
            F.date_trunc(self.config.aggregation_level, "sale_date").alias("period"),
            "product_id",
            "region",
            "sales_rep_id"
        ).agg(
            F.count("id").alias("sales_count"),
            F.sum("revenue").alias("total_revenue"),
            F.sum("quantity").alias("total_quantity"),
            F.avg("unit_price").alias("avg_unit_price"),
            F.countDistinct("customer_id").alias("unique_customers")
        )

        # Calculate revenue per customer
        gold_df = gold_df.withColumn(
            "revenue_per_customer",
            F.col("total_revenue") / F.col("unique_customers")
        )

        # Add rolling averages
        window_spec = Window.partitionBy("product_id", "region").orderBy("period").rowsBetween(-3, 0)
        gold_df = gold_df.withColumn(
            "rolling_4period_avg_revenue",
            F.avg("total_revenue").over(window_spec)
        )

        gold_df = gold_df.withColumn("_created_at", F.current_timestamp())

        return gold_df

    def _create_inventory_metrics(self, df: DataFrame) -> DataFrame:
        """Create inventory turnover and stock metrics."""
        logger.info("creating_inventory_metrics")

        gold_df = df.groupBy(
            F.date_trunc(self.config.aggregation_level, "snapshot_date").alias("period"),
            "product_id",
            "warehouse_id"
        ).agg(
            F.avg("quantity_on_hand").alias("avg_stock_level"),
            F.min("quantity_on_hand").alias("min_stock_level"),
            F.max("quantity_on_hand").alias("max_stock_level"),
            F.sum("units_sold").alias("total_units_sold"),
            F.sum("units_received").alias("total_units_received"),
            F.avg("reorder_point").alias("avg_reorder_point")
        )

        # Calculate inventory turnover ratio
        gold_df = gold_df.withColumn(
            "inventory_turnover",
            F.col("total_units_sold") / F.col("avg_stock_level")
        )

        # Calculate days of inventory
        gold_df = gold_df.withColumn(
            "days_of_inventory",
            365 / F.col("inventory_turnover")
        )

        # Stockout risk indicator
        gold_df = gold_df.withColumn(
            "stockout_risk",
            F.when(F.col("min_stock_level") <= F.col("avg_reorder_point"), "high")
            .when(F.col("min_stock_level") <= F.col("avg_reorder_point") * 1.5, "medium")
            .otherwise("low")
        )

        gold_df = gold_df.withColumn("_created_at", F.current_timestamp())

        return gold_df

    def _create_generic_aggregation(self, df: DataFrame) -> DataFrame:
        """Create generic time-based aggregation."""
        logger.info("creating_generic_aggregation")

        # Use first timestamp column found
        timestamp_cols = [f.name for f in df.schema.fields
                         if "timestamp" in f.dataType.simpleString() or "date" in f.dataType.simpleString()]

        if not timestamp_cols:
            logger.warning("no_timestamp_column_found")
            return df

        time_col = timestamp_cols[0]

        # Simple count aggregation
        gold_df = df.groupBy(
            F.date_trunc(self.config.aggregation_level, time_col).alias("period")
        ).agg(
            F.count("*").alias("record_count")
        )

        gold_df = gold_df.withColumn("_created_at", F.current_timestamp())

        return gold_df

    def _write_gold(self, df: DataFrame):
        """Write data to gold layer."""
        logger.info("writing_gold", path=self.config.target_path)

        df.write \
            .format("delta") \
            .mode("overwrite") \
            .partitionBy("period") \
            .save(self.config.target_path)

        logger.info("gold_write_complete", records=df.count())
