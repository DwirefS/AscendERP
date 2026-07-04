"""
Hash-chained execution receipts (audit trail) for the agent harness.

Each :class:`Receipt` captures one harness run: who ran, on what input
(canonical-json sha256), which actions, which policy decisions, which skills,
and at what cost. Receipts are chained: each receipt's hash covers its body
plus the previous receipt's hash, so any tampering breaks ``verify()``.

Design contract: docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §3.6 / §5.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

import structlog

logger = structlog.get_logger()

GENESIS_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    """Deterministic JSON encoding (sorted keys, compact separators)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def hash_inputs(input_data: Any) -> str:
    """sha256 over the canonical-json encoding of ``input_data``."""
    return hashlib.sha256(canonical_json(input_data).encode("utf-8")).hexdigest()


@dataclass
class Receipt:
    """One audited harness run."""

    receipt_id: str = field(default_factory=lambda: f"RCPT-{uuid.uuid4().hex[:12]}")
    agent_id: str = ""
    agent_type: str = ""
    trace_id: str = ""
    tenant_id: str = ""
    inputs_hash: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    policy_decisions: List[Dict[str, Any]] = field(default_factory=list)
    skills_used: List[str] = field(default_factory=list)
    cost: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    prev_hash: str = ""
    hash: str = ""

    def body(self) -> Dict[str, Any]:
        """Receipt content covered by the hash (everything except ``hash``)."""
        data = asdict(self)
        data.pop("hash", None)
        return data

    def compute_hash(self) -> str:
        """sha256(prev_hash + canonical json of the receipt body)."""
        payload = self.prev_hash + canonical_json(self.body())
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReceiptSink(Protocol):
    """Anything that can durably store a sealed receipt."""

    async def store(self, receipt: Receipt) -> None:  # pragma: no cover - protocol
        ...


class PostgresReceiptSink:
    """
    Durable receipt storage in the existing ``audit.receipts`` table.

    Adapts the hash-chained :class:`Receipt` to the table that
    ``DatabaseClient.initialize_schemas`` creates (which predates the chained
    receipt format): ``ensure_schema()`` extends the table with
    ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS`` for the chain fields
    (``receipt_id``, ``prev_hash``, ``skills_used`` JSONB, ...), so both the
    legacy ``DatabaseClient.insert_receipt`` rows and chained receipts coexist
    in one audit table. The full receipt body is also stored in ``details``
    (JSONB) for lossless auditability.
    """

    def __init__(self, db: Any) -> None:
        """``db`` is a connected ``src.core.memory.database.DatabaseClient``."""
        self._db = db
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        """Create/extend ``audit.receipts`` so chained receipts round-trip."""
        if self._schema_ready:
            return
        await self._db.execute("CREATE SCHEMA IF NOT EXISTS audit;")
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS audit.receipts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                receipt_type TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT,
                resource TEXT,
                details JSONB DEFAULT '{}',
                policy_decision TEXT,
                hash TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        for ddl in (
            "ALTER TABLE audit.receipts ADD COLUMN IF NOT EXISTS receipt_id TEXT",
            "ALTER TABLE audit.receipts ADD COLUMN IF NOT EXISTS agent_type TEXT",
            "ALTER TABLE audit.receipts ADD COLUMN IF NOT EXISTS inputs_hash TEXT",
            "ALTER TABLE audit.receipts ADD COLUMN IF NOT EXISTS actions JSONB",
            "ALTER TABLE audit.receipts ADD COLUMN IF NOT EXISTS policy_decisions JSONB",
            "ALTER TABLE audit.receipts ADD COLUMN IF NOT EXISTS skills_used JSONB",
            "ALTER TABLE audit.receipts ADD COLUMN IF NOT EXISTS cost JSONB",
            "ALTER TABLE audit.receipts ADD COLUMN IF NOT EXISTS prev_hash TEXT",
            "ALTER TABLE audit.receipts ADD COLUMN IF NOT EXISTS receipt_created_at TEXT",
        ):
            await self._db.execute(ddl)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_receipts_tenant_chain "
            "ON audit.receipts (tenant_id, created_at) WHERE receipt_id IS NOT NULL"
        )
        self._schema_ready = True

    async def store(self, receipt: Receipt) -> None:
        """Persist one sealed receipt (call after ``ReceiptChain.append``)."""
        await self.ensure_schema()
        action = receipt.actions[0].get("type", "harness_run") if receipt.actions else "harness_run"
        await self._db.execute(
            """
            INSERT INTO audit.receipts (
                receipt_type, trace_id, tenant_id, agent_id, action, details, hash,
                receipt_id, agent_type, inputs_hash, actions, policy_decisions,
                skills_used, cost, prev_hash, receipt_created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            """,
            "harness_chain",
            receipt.trace_id,
            receipt.tenant_id,
            receipt.agent_id,
            str(action),
            canonical_json(receipt.to_dict()),
            receipt.hash,
            receipt.receipt_id,
            receipt.agent_type,
            receipt.inputs_hash,
            canonical_json(receipt.actions),
            canonical_json(receipt.policy_decisions),
            canonical_json(receipt.skills_used),
            canonical_json(receipt.cost),
            receipt.prev_hash,
            receipt.created_at,
        )

    async def load(self, tenant_id: str) -> List[Receipt]:
        """Load a tenant's chained receipts in append order."""
        await self.ensure_schema()
        rows = await self._db.fetch(
            """
            SELECT receipt_id, agent_id, agent_type, trace_id, tenant_id,
                   inputs_hash, actions, policy_decisions, skills_used, cost,
                   receipt_created_at, prev_hash, hash
            FROM audit.receipts
            WHERE tenant_id = $1 AND receipt_id IS NOT NULL
            ORDER BY created_at ASC, receipt_created_at ASC
            """,
            tenant_id,
        )

        def _json(value: Any, default: Any) -> Any:
            if value is None:
                return default
            if isinstance(value, str):
                return json.loads(value)
            return value

        return [
            Receipt(
                receipt_id=row["receipt_id"],
                agent_id=row["agent_id"],
                agent_type=row["agent_type"] or "",
                trace_id=row["trace_id"],
                tenant_id=row["tenant_id"],
                inputs_hash=row["inputs_hash"] or "",
                actions=_json(row["actions"], []),
                policy_decisions=_json(row["policy_decisions"], []),
                skills_used=_json(row["skills_used"], []),
                cost=_json(row["cost"], {}),
                created_at=row["receipt_created_at"] or "",
                prev_hash=row["prev_hash"] or "",
                hash=row["hash"],
            )
            for row in rows
        ]


class ReceiptChain:
    """
    Append-only, hash-chained list of receipts.

    Appends are single, atomic list operations, which is sufficient for
    asyncio concurrency (no awaits inside the critical section).

    Durability (``sink=``): when a :class:`ReceiptSink` (e.g.
    :class:`PostgresReceiptSink`) is attached, every ``append`` also schedules
    ``await sink.store(receipt)`` as a background task. This is deliberately
    **availability over durability**: the in-memory chain is the source of
    truth for a running agent, sink writes are fire-and-forget (serialized in
    append order, wrapped in try/except with a structlog warning), and a
    database outage therefore never blocks or fails an agent run — it only
    degrades the audit trail to in-memory until the DB returns. Use
    ``await flush_sink()`` to wait for pending sink writes (tests, shutdown).
    """

    def __init__(self, sink: Optional[ReceiptSink] = None) -> None:
        self._receipts: List[Receipt] = []
        self.sink = sink
        self._sink_tasks: set = set()
        self._sink_lock: Optional[asyncio.Lock] = None

    def __len__(self) -> int:
        return len(self._receipts)

    @property
    def receipts(self) -> List[Receipt]:
        return list(self._receipts)

    @property
    def head_hash(self) -> str:
        return self._receipts[-1].hash if self._receipts else GENESIS_HASH

    def append(self, receipt: Receipt) -> Receipt:
        """Link ``receipt`` to the chain head, seal its hash, and append it."""
        receipt.prev_hash = self.head_hash
        receipt.hash = receipt.compute_hash()
        self._receipts.append(receipt)
        logger.debug(
            "receipt_appended",
            receipt_id=receipt.receipt_id,
            agent_id=receipt.agent_id,
            hash=receipt.hash[:12],
        )
        if self.sink is not None:
            self._schedule_sink_store(receipt)
        return receipt

    def _schedule_sink_store(self, receipt: Receipt) -> None:
        """Fire-and-forget durable store; never raises into the caller."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "receipt_sink_skipped_no_event_loop", receipt_id=receipt.receipt_id
            )
            return
        if self._sink_lock is None:
            self._sink_lock = asyncio.Lock()
        task = loop.create_task(self._store_to_sink(receipt))
        self._sink_tasks.add(task)
        task.add_done_callback(self._sink_tasks.discard)

    async def _store_to_sink(self, receipt: Receipt) -> None:
        """Serialize sink writes in append order; swallow failures (see class doc)."""
        async with self._sink_lock:  # type: ignore[union-attr]
            try:
                await self.sink.store(receipt)  # type: ignore[union-attr]
            except Exception as exc:  # availability over durability
                logger.warning(
                    "receipt_sink_store_failed",
                    receipt_id=receipt.receipt_id,
                    error=str(exc),
                )

    async def flush_sink(self) -> None:
        """Wait for all pending sink writes (never raises)."""
        while self._sink_tasks:
            tasks = list(self._sink_tasks)
            await asyncio.gather(*tasks, return_exceptions=True)
            self._sink_tasks.difference_update(tasks)

    @classmethod
    async def load_from_sink(cls, db: Any, tenant_id: str) -> "ReceiptChain":
        """
        Restore a tenant's chain from ``audit.receipts`` and verify it.

        Raises ``ValueError`` when the stored chain fails ``verify()`` —
        i.e. any receipt was tampered with in the database.
        """
        sink = PostgresReceiptSink(db)
        chain = cls(sink=sink)
        chain._receipts = await sink.load(tenant_id)
        if not chain.verify():
            raise ValueError(
                f"receipt chain for tenant {tenant_id!r} failed verification: "
                "stored receipts were tampered with or reordered"
            )
        return chain

    def verify(self) -> bool:
        """Recompute every hash and link; False on any tampering."""
        prev = GENESIS_HASH
        for receipt in self._receipts:
            if receipt.prev_hash != prev:
                return False
            if receipt.compute_hash() != receipt.hash:
                return False
            prev = receipt.hash
        return True

    def to_jsonl(self, path: str | Path) -> int:
        """Write the chain as JSONL; returns number of receipts written."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fh:
            for receipt in self._receipts:
                fh.write(canonical_json(receipt.to_dict()) + "\n")
        return len(self._receipts)
