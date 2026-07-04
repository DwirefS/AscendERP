"""
Functional tests for durable receipts (backlog item 6, D-023).

PostgresReceiptSink + ReceiptChain(sink=...): live-Postgres round-trip,
tamper detection on load, and the availability-over-durability guarantee
(a broken sink never breaks in-memory appends). DB tests skip cleanly
when Postgres is unreachable (same pattern as test_entropy.py).
"""
import uuid

import pytest

from src.core.harness.receipts import (
    GENESIS_HASH,
    PostgresReceiptSink,
    Receipt,
    ReceiptChain,
)
from src.core.memory.database import DatabaseClient, DatabaseConfig

CFG = DatabaseConfig(host="localhost", port=5432, database="ants_test",
                     username="test_user", password="test_pass")


@pytest.fixture
async def db():
    client = DatabaseClient(CFG)
    try:
        await client.connect()
    except Exception:
        pytest.skip("PostgreSQL unreachable — start it with `make dev`")
    await client.initialize_schemas()
    yield client
    await client.disconnect()


def _tenant() -> str:
    return f"receipt-test-{uuid.uuid4().hex[:8]}"


def _receipt(tenant: str, i: int) -> Receipt:
    return Receipt(
        agent_id=f"agent-{i}",
        agent_type="manufacturing.quality",
        trace_id=f"trace-{i}",
        tenant_id=tenant,
        inputs_hash="ab" * 32,
        actions=[{"type": "disposition", "ncr": f"NCR-{i}"}],
        policy_decisions=[{"policy": "threshold", "allowed": True}],
        skills_used=["spc-analysis", "ncr-disposition"],
        cost={"tokens": 100 + i, "usd": 0.01 * i},
    )


@pytest.mark.integration
async def test_store_load_round_trip_preserves_chain(db):
    tenant = _tenant()
    chain = ReceiptChain(sink=PostgresReceiptSink(db))
    for i in range(3):
        chain.append(_receipt(tenant, i))
    await chain.flush_sink()

    restored = await ReceiptChain.load_from_sink(db, tenant)
    assert len(restored) == 3
    assert restored.verify() is True
    assert restored.head_hash == chain.head_hash
    assert [r.hash for r in restored.receipts] == [r.hash for r in chain.receipts]
    # Full field fidelity, including JSONB fields.
    got, want = restored.receipts[1], chain.receipts[1]
    assert got.skills_used == want.skills_used
    assert got.actions == want.actions
    assert got.policy_decisions == want.policy_decisions
    assert got.cost == want.cost
    assert got.created_at == want.created_at


@pytest.mark.integration
async def test_tamper_in_db_detected_on_load(db):
    tenant = _tenant()
    chain = ReceiptChain(sink=PostgresReceiptSink(db))
    for i in range(2):
        chain.append(_receipt(tenant, i))
    await chain.flush_sink()

    # Tamper: rewrite the stored actions of the first receipt.
    await db.execute(
        """UPDATE audit.receipts
           SET actions = '[{"type": "disposition", "ncr": "NCR-FORGED"}]'::jsonb
           WHERE tenant_id = $1 AND receipt_id = $2""",
        tenant, chain.receipts[0].receipt_id,
    )
    with pytest.raises(ValueError, match="failed verification"):
        await ReceiptChain.load_from_sink(db, tenant)


@pytest.mark.integration
async def test_empty_tenant_loads_empty_verified_chain(db):
    restored = await ReceiptChain.load_from_sink(db, _tenant())
    assert len(restored) == 0
    assert restored.verify() is True
    assert restored.head_hash == GENESIS_HASH


@pytest.mark.integration
async def test_tenants_are_isolated(db):
    tenant_a, tenant_b = _tenant(), _tenant()
    chain_a = ReceiptChain(sink=PostgresReceiptSink(db))
    chain_a.append(_receipt(tenant_a, 0))
    chain_b = ReceiptChain(sink=PostgresReceiptSink(db))
    chain_b.append(_receipt(tenant_b, 0))
    await chain_a.flush_sink()
    await chain_b.flush_sink()

    restored_b = await ReceiptChain.load_from_sink(db, tenant_b)
    assert len(restored_b) == 1
    assert restored_b.receipts[0].tenant_id == tenant_b
    assert restored_b.verify() is True


@pytest.mark.integration
async def test_legacy_insert_receipt_rows_coexist(db):
    """Chained receipts share audit.receipts with legacy insert_receipt rows."""
    tenant = _tenant()
    await db.insert_receipt(
        receipt_type="legacy", trace_id="t-legacy", tenant_id=tenant,
        agent_id="old-agent", action="approve", actor="human",
        resource="PO-1", details={"po": 1}, policy_decision="allow",
        previous_hash=None,
    )
    chain = ReceiptChain(sink=PostgresReceiptSink(db))
    chain.append(_receipt(tenant, 0))
    await chain.flush_sink()

    # Legacy rows (receipt_id IS NULL) are excluded from the chain load.
    restored = await ReceiptChain.load_from_sink(db, tenant)
    assert len(restored) == 1
    assert restored.verify() is True


class _ExplodingSink:
    """Sink stand-in for a DB outage: every store raises."""

    def __init__(self):
        self.attempts = 0

    async def store(self, receipt):
        self.attempts += 1
        raise ConnectionError("database is down")


async def test_sink_failure_never_breaks_in_memory_append():
    """Availability over durability: appends succeed through a dead sink."""
    sink = _ExplodingSink()
    chain = ReceiptChain(sink=sink)
    tenant = _tenant()
    for i in range(3):
        appended = chain.append(_receipt(tenant, i))
        assert appended.hash  # sealed despite the sink outage
    await chain.flush_sink()  # must not raise
    assert sink.attempts == 3
    assert len(chain) == 3
    assert chain.verify() is True
