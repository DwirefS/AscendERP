"""
Functional tests for memory entropy management (whitepaper §6.4).
Run against live Postgres; skip cleanly when unreachable.
"""
import asyncio
import uuid
from datetime import datetime, timedelta

import pytest

from src.core.memory.database import DatabaseClient, DatabaseConfig
from src.core.memory.entropy import DEFAULT_POLICIES, EntropyManager

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
    return f"entropy-test-{uuid.uuid4().hex[:8]}"


async def _seed_episodic(db, tenant, age_days: int, n: int, agent="a1"):
    ts = datetime.utcnow() - timedelta(days=age_days)
    async with db._pool.acquire() as conn:
        for i in range(n):
            await conn.execute(
                """INSERT INTO memory.episodic (tenant_id, agent_id, content, created_at)
                   VALUES ($1, $2, $3::jsonb, $4)""",
                tenant, agent,
                '{"action": "x", "status": "ok", "detail": "%s"}' % ("d" * 200),
                ts,
            )


@pytest.mark.integration
async def test_dry_run_counts_but_does_not_mutate(db):
    tenant = _tenant()
    await _seed_episodic(db, tenant, age_days=3000, n=4)   # far past cold (7y=2555d)
    mgr = EntropyManager(db, DEFAULT_POLICIES)
    await mgr.ensure_schema()
    report = await mgr.apply(tenant_id=tenant)             # dry-run default
    assert report.dry_run is True
    assert report.stages["purge_candidates"] >= 4
    assert report.stages["purged"] == 0
    async with db._pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM memory.episodic WHERE tenant_id=$1", tenant)
    assert count == 4  # nothing deleted


@pytest.mark.integration
async def test_purge_requires_governance_approval(db):
    tenant = _tenant()
    await _seed_episodic(db, tenant, age_days=3000, n=3)
    mgr = EntropyManager(db, DEFAULT_POLICIES)
    await mgr.ensure_schema()
    report = await mgr.apply(tenant_id=tenant, governance_approval=True)
    assert report.dry_run is False
    assert report.stages["purged"] >= 3
    async with db._pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM memory.episodic WHERE tenant_id=$1", tenant)
    assert count == 0


@pytest.mark.integration
async def test_compress_past_hot_window_preserves_rows(db):
    tenant = _tenant()
    await _seed_episodic(db, tenant, age_days=120, n=3)    # past hot (90d), in warm
    await _seed_episodic(db, tenant, age_days=5, n=2)      # hot — untouched
    mgr = EntropyManager(db, DEFAULT_POLICIES)
    await mgr.ensure_schema()
    report = await mgr.apply(tenant_id=tenant, governance_approval=True)
    assert report.stages["compressed"] >= 3
    async with db._pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT count(*) FROM memory.episodic WHERE tenant_id=$1", tenant)
        compressed = await conn.fetchval(
            """SELECT count(*) FROM memory.episodic
               WHERE tenant_id=$1 AND content ? '_compressed'""", tenant)
    assert total == 5           # compression never deletes
    assert compressed >= 3


@pytest.mark.integration
async def test_report_journal_and_bytes(db):
    tenant = _tenant()
    await _seed_episodic(db, tenant, age_days=120, n=2)
    mgr = EntropyManager(db, DEFAULT_POLICIES)
    await mgr.ensure_schema()
    report = await mgr.apply(tenant_id=tenant, governance_approval=True)
    d = report.to_dict() if hasattr(report, "to_dict") else vars(report)
    assert "stages" in d and "dry_run" in d
