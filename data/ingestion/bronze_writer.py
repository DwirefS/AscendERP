"""
Bronze Layer Writer for ANTS Data Lakehouse.
Writes raw ingested data to ANF bronze layer.
"""
from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import aiofiles
import structlog

from data.ingestion.connectors.erp_connector import DataRecord

logger = structlog.get_logger()


@dataclass
class BronzeWriterConfig:
    """Configuration for bronze layer writer."""
    base_path: str = "/mnt/anf/lakehouse/bronze"
    batch_size: int = 100
    file_format: str = "json"  # json, parquet, delta
    compression: str = "gzip"
    partition_by: List[str] = None

    def __post_init__(self):
        if self.partition_by is None:
            self.partition_by = ["source", "entity_type", "ingestion_date"]


class BronzeLayerWriter:
    """
    Writes raw data records to bronze layer on ANF.
    Supports batching, partitioning, and multiple formats.
    """

    def __init__(self, config: BronzeWriterConfig):
        self.config = config
        self._current_batch = []
        self._records_written = 0

    async def write_records(
        self,
        records: AsyncIterator[DataRecord],
        source_name: str
    ) -> Dict[str, Any]:
        """
        Write records to bronze layer.
        Returns statistics about the write operation.
        """
        logger.info(
            "starting_bronze_write",
            source=source_name,
            base_path=self.config.base_path
        )

        write_start = datetime.utcnow()
        stats = {
            "records_written": 0,
            "files_created": 0,
            "bytes_written": 0,
            "partitions": set()
        }

        try:
            async for record in records:
                self._current_batch.append(record)

                # Write batch when size reached
                if len(self._current_batch) >= self.config.batch_size:
                    batch_stats = await self._flush_batch(source_name)
                    self._update_stats(stats, batch_stats)

            # Write remaining records
            if self._current_batch:
                batch_stats = await self._flush_batch(source_name)
                self._update_stats(stats, batch_stats)

            stats["duration_seconds"] = (datetime.utcnow() - write_start).total_seconds()
            stats["partitions"] = list(stats["partitions"])

            logger.info(
                "bronze_write_complete",
                records=stats["records_written"],
                files=stats["files_created"],
                duration=stats["duration_seconds"]
            )

        except Exception as e:
            logger.error("bronze_write_failed", error=str(e))
            stats["error"] = str(e)

        return stats

    async def _flush_batch(self, source_name: str) -> Dict[str, Any]:
        """Flush current batch to storage."""
        if not self._current_batch:
            return {"records_written": 0}

        # Group records by partition
        partitioned_records = self._partition_records(self._current_batch)

        batch_stats = {
            "records_written": 0,
            "files_created": 0,
            "bytes_written": 0,
            "partitions": set()
        }

        for partition_key, records in partitioned_records.items():
            file_stats = await self._write_partition(
                records=records,
                partition_key=partition_key,
                source_name=source_name
            )

            batch_stats["records_written"] += file_stats["records_written"]
            batch_stats["files_created"] += 1
            batch_stats["bytes_written"] += file_stats["bytes_written"]
            batch_stats["partitions"].add(partition_key)

        # Clear batch
        self._current_batch = []

        return batch_stats

    def _partition_records(
        self,
        records: List[DataRecord]
    ) -> Dict[str, List[DataRecord]]:
        """Group records by partition key."""
        partitioned = {}

        for record in records:
            partition_key = self._get_partition_key(record)

            if partition_key not in partitioned:
                partitioned[partition_key] = []

            partitioned[partition_key].append(record)

        return partitioned

    def _get_partition_key(self, record: DataRecord) -> str:
        """Generate partition key for a record."""
        parts = []

        for partition_col in self.config.partition_by:
            if partition_col == "source":
                parts.append(f"source={record.source}")
            elif partition_col == "entity_type":
                parts.append(f"entity_type={record.entity_type}")
            elif partition_col == "ingestion_date":
                date_str = record.extracted_at.strftime("%Y-%m-%d")
                parts.append(f"ingestion_date={date_str}")
            elif partition_col == "year":
                parts.append(f"year={record.extracted_at.year}")
            elif partition_col == "month":
                parts.append(f"month={record.extracted_at.month:02d}")

        return "/".join(parts)

    async def _write_partition(
        self,
        records: List[DataRecord],
        partition_key: str,
        source_name: str
    ) -> Dict[str, Any]:
        """Write records for a partition to file."""
        # Create partition directory
        partition_path = Path(self.config.base_path) / partition_key
        partition_path.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        filename = f"data_{timestamp}.{self.config.file_format}"

        if self.config.compression == "gzip":
            filename += ".gz"

        file_path = partition_path / filename

        # Write based on format
        if self.config.file_format == "json":
            bytes_written = await self._write_json(records, file_path)
        elif self.config.file_format == "parquet":
            bytes_written = await self._write_parquet(records, file_path)
        else:
            raise ValueError(f"Unsupported format: {self.config.file_format}")

        logger.debug(
            "partition_written",
            partition=partition_key,
            file=str(file_path),
            records=len(records),
            bytes=bytes_written
        )

        return {
            "records_written": len(records),
            "bytes_written": bytes_written,
            "file_path": str(file_path)
        }

    async def _write_json(
        self,
        records: List[DataRecord],
        file_path: Path
    ) -> int:
        """Write records as JSONL (newline-delimited JSON)."""
        bytes_written = 0

        # Convert records to JSON
        json_lines = []
        for record in records:
            json_obj = {
                "id": record.id,
                "source": record.source,
                "entity_type": record.entity_type,
                "data": record.data,
                "metadata": record.metadata,
                "extracted_at": record.extracted_at.isoformat()
            }
            json_line = json.dumps(json_obj) + "\n"
            json_lines.append(json_line)
            bytes_written += len(json_line.encode('utf-8'))

        # Write to file
        async with aiofiles.open(file_path, mode='w') as f:
            await f.writelines(json_lines)

        return bytes_written

    async def _write_parquet(
        self,
        records: List[DataRecord],
        file_path: Path
    ) -> int:
        """Write records as Parquet (requires PyArrow)."""
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            # Convert records to Arrow table
            data = {
                "id": [r.id for r in records],
                "source": [r.source for r in records],
                "entity_type": [r.entity_type for r in records],
                "data": [json.dumps(r.data) for r in records],
                "metadata": [json.dumps(r.metadata) for r in records],
                "extracted_at": [r.extracted_at.isoformat() for r in records]
            }

            table = pa.Table.from_pydict(data)

            # Write parquet file
            pq.write_table(table, file_path, compression=self.config.compression)

            # Get file size
            return file_path.stat().st_size

        except ImportError:
            logger.error("pyarrow_not_installed")
            raise

    def _update_stats(
        self,
        total_stats: Dict[str, Any],
        batch_stats: Dict[str, Any]
    ):
        """Update total statistics with batch statistics."""
        total_stats["records_written"] += batch_stats.get("records_written", 0)
        total_stats["files_created"] += batch_stats.get("files_created", 0)
        total_stats["bytes_written"] += batch_stats.get("bytes_written", 0)

        if "partitions" in batch_stats:
            total_stats["partitions"].update(batch_stats["partitions"])


class BronzeLayerReader:
    """
    Reads data from bronze layer.
    Used for debugging and bronze→silver pipeline input.
    """

    def __init__(self, base_path: str = "/mnt/anf/lakehouse/bronze"):
        self.base_path = base_path

    async def read_partition(
        self,
        partition_path: str,
        file_format: str = "json"
    ) -> List[Dict[str, Any]]:
        """Read all records from a partition."""
        full_path = Path(self.base_path) / partition_path

        if not full_path.exists():
            logger.warning("partition_not_found", path=str(full_path))
            return []

        records = []

        # Read all files in partition
        for file_path in full_path.glob(f"*.{file_format}*"):
            file_records = await self._read_file(file_path, file_format)
            records.extend(file_records)

        logger.info(
            "partition_read",
            partition=partition_path,
            records=len(records)
        )

        return records

    async def _read_file(
        self,
        file_path: Path,
        file_format: str
    ) -> List[Dict[str, Any]]:
        """Read records from a file."""
        if file_format == "json":
            return await self._read_json(file_path)
        elif file_format == "parquet":
            return await self._read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported format: {file_format}")

    async def _read_json(self, file_path: Path) -> List[Dict[str, Any]]:
        """Read JSONL file."""
        records = []

        async with aiofiles.open(file_path, mode='r') as f:
            async for line in f:
                if line.strip():
                    records.append(json.loads(line))

        return records

    async def _read_parquet(self, file_path: Path) -> List[Dict[str, Any]]:
        """Read Parquet file."""
        import pyarrow.parquet as pq

        table = pq.read_table(file_path)
        return table.to_pylist()
