"""
Hash-chained execution receipts (audit trail) for the agent harness.

Each :class:`Receipt` captures one harness run: who ran, on what input
(canonical-json sha256), which actions, which policy decisions, which skills,
and at what cost. Receipts are chained: each receipt's hash covers its body
plus the previous receipt's hash, so any tampering breaks ``verify()``.

Design contract: docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §3.6 / §5.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

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


class ReceiptChain:
    """
    Append-only, hash-chained list of receipts.

    Appends are single, atomic list operations, which is sufficient for
    asyncio concurrency (no awaits inside the critical section).
    """

    def __init__(self) -> None:
        self._receipts: List[Receipt] = []

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
        return receipt

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
