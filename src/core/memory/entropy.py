"""
Memory Entropy Management — the excretory system of the memory substrate.

Implements the whitepaper §6.4 "Memory Entropy and Aging" design as real code:
data classes age through hot → warm → cold windows and decay through the
stages Compress → Summarize → Archive → Purge, run nightly by SelfOps
DataOps agents.

| Data Class          | Hot     | Warm   | Cold    | Decay Rule                        |
|---------------------|---------|--------|---------|-----------------------------------|
| Episodic (general)  | 90 days | 1 year | 7 years | Compress -> Archive -> Purge      |
| Episodic (SOX)      | 90 days | 1 year | Forever | Compress -> Archive (never purge) |
| Semantic (customer) | 180 days| 3 years| 7 years | Summarize -> Archive -> Purge     |
| Procedural          | Always  | N/A    | N/A     | Version control only              |

Purging is destructive and therefore requires explicit governance approval;
without it every purge is a dry-run that only *reports* what would be
deleted. All timestamps flow through an injectable ``clock`` so runs are
deterministic under test.
"""
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import structlog

logger = structlog.get_logger()

# Rows are matched to a policy's class tag via metadata->>'data_class';
# rows without a tag belong to the 'general' class.
_CLASS_PREDICATE = "COALESCE(metadata->>'data_class', 'general') = ${n}"

# Per-table SQL specifics (fully-qualified name + byte-size expression).
_TABLES: Dict[str, Dict[str, str]] = {
    "episodic": {"fq": "memory.episodic", "bytes": "octet_length(content::text)"},
    "semantic": {"fq": "memory.semantic", "bytes": "octet_length(content)"},
    "procedural": {"fq": "memory.procedural", "bytes": "octet_length(pattern::text)"},
}


@dataclass(frozen=True)
class EntropyPolicy:
    """Aging policy for one memory data class (whitepaper §6.4 table row).

    ``data_class`` is ``"<table>.<tag>"`` (e.g. ``"episodic.sox"``) or just
    ``"<table>"`` when the policy applies table-wide. Window fields are days
    since row creation; ``None`` means "no such window" (e.g. Forever).
    """
    data_class: str
    hot_days: Optional[int]
    warm_days: Optional[int]
    cold_days: Optional[int]
    decay_rule: List[str] = field(default_factory=list)
    never_purge: bool = False

    @property
    def table(self) -> str:
        return self.data_class.split(".", 1)[0]

    @property
    def class_tag(self) -> Optional[str]:
        parts = self.data_class.split(".", 1)
        return parts[1] if len(parts) == 2 else None


#: Whitepaper §6.4 Entropy Management Policies table, verbatim.
DEFAULT_POLICIES: List[EntropyPolicy] = [
    EntropyPolicy(
        data_class="episodic.general",
        hot_days=90, warm_days=365, cold_days=7 * 365,
        decay_rule=["compress", "archive", "purge"],
    ),
    EntropyPolicy(
        data_class="episodic.sox",
        hot_days=90, warm_days=365, cold_days=None,  # cold window: Forever
        decay_rule=["compress", "archive"],
        never_purge=True,
    ),
    EntropyPolicy(
        data_class="semantic.customer",
        hot_days=180, warm_days=3 * 365, cold_days=7 * 365,
        decay_rule=["summarize", "archive", "purge"],
    ),
    EntropyPolicy(
        data_class="procedural",
        hot_days=None, warm_days=None, cold_days=None,
        decay_rule=[],  # version control only — no aging
        never_purge=True,
    ),
]


@dataclass
class EntropyReport:
    """Outcome of one entropy cycle: per-stage counts + reclaim estimate."""
    generated_at: str
    dry_run: bool
    stages: Dict[str, int] = field(default_factory=lambda: {
        "compressed": 0,
        "summarized_rows": 0,
        "summary_rows_created": 0,
        "archived": 0,
        "purge_candidates": 0,
        "purged": 0,
    })
    bytes_reclaimed: int = 0
    by_class: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def _bump(self, data_class: str, stage: str, count: int) -> None:
        self.stages[stage] = self.stages.get(stage, 0) + count
        cls = self.by_class.setdefault(data_class, {})
        cls[stage] = cls.get(stage, 0) + count


class EntropyManager:
    """Runs the decay/summarize/archive/purge lifecycle against the live
    memory schemas (``memory.episodic`` / ``memory.semantic`` /
    ``memory.procedural``).

    Deterministic under an injected ``clock`` (a zero-arg callable returning
    an aware :class:`datetime`). Purge deletes rows only when
    ``governance_approval=True``; otherwise it is a dry-run report.
    """

    def __init__(
        self,
        db_client,
        policies: Optional[List[EntropyPolicy]] = None,
        clock: Optional[Callable[[], datetime]] = None,
        journal_path: Optional[Union[str, Path]] = None,
        summarize_threshold: int = 20,
    ):
        self.db = db_client
        self.policies = list(policies) if policies is not None else list(DEFAULT_POLICIES)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.journal_path = Path(journal_path) if journal_path else None
        self._tenant = None
        self.summarize_threshold = summarize_threshold
        self._schema_ready = False

    # ------------------------------------------------------------------ #
    # Schema
    # ------------------------------------------------------------------ #

    async def ensure_schema(self) -> None:
        """Add the lifecycle column to every memory table (idempotent)."""
        for spec in _TABLES.values():
            await self.db.execute(
                f"ALTER TABLE {spec['fq']} "
                "ADD COLUMN IF NOT EXISTS lifecycle TEXT DEFAULT 'hot'"
            )
        self._schema_ready = True

    async def _ensure(self) -> None:
        if not self._schema_ready:
            await self.ensure_schema()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _cutoff(self, now: datetime, days: Optional[int]) -> Optional[datetime]:
        return now - timedelta(days=days) if days is not None else None

    @staticmethod
    def _predicate(param_num: int) -> str:
        return _CLASS_PREDICATE.format(n=param_num)

    def _stage_policies(self, stage: str) -> List[EntropyPolicy]:
        return [p for p in self.policies if stage in p.decay_rule and p.class_tag]

    @staticmethod
    def _rowcount(status: str) -> int:
        """Parse asyncpg status tags like 'UPDATE 7' / 'DELETE 3'."""
        try:
            return int(status.split()[-1])
        except (ValueError, IndexError):
            return 0

    # ------------------------------------------------------------------ #
    # Stage (a): compress — episodic rows past the hot window
    # ------------------------------------------------------------------ #

    async def compress(self, report: Optional[EntropyReport] = None) -> EntropyReport:
        """Replace episodic content past the hot window with a compact
        summary dict (keeps action/status/outcome, records original size)."""
        await self._ensure()
        now = self._clock()
        report = report or EntropyReport(generated_at=now.isoformat(), dry_run=True)

        for policy in self._stage_policies("compress"):
            if policy.table != "episodic" or policy.hot_days is None:
                continue
            cutoff = self._cutoff(now, policy.hot_days)
            spec = _TABLES[policy.table]
            rows = await self.db.fetch(
                f"""
                UPDATE {spec['fq']}
                SET content = jsonb_strip_nulls(jsonb_build_object(
                        'action', content->'action',
                        'status', content->'status',
                        'outcome', content->'outcome'
                    )) || jsonb_build_object(
                        '_compressed', true,
                        '_original_bytes', octet_length(content::text)
                    ),
                    lifecycle = 'compressed',
                    updated_at = $2
                WHERE created_at < $1 AND ($3::text IS NULL OR tenant_id = $3)
                  AND lifecycle = 'hot'
                  AND {self._predicate(4)}
                RETURNING (content->>'_original_bytes')::int
                          - octet_length(content::text) AS reclaimed
                """,
                cutoff, now, self._tenant, policy.class_tag,
            )
            reclaimed = sum(max(r["reclaimed"], 0) for r in rows)
            report._bump(policy.data_class, "compressed", len(rows))
            report.bytes_reclaimed += reclaimed
            if rows:
                logger.info(
                    "entropy_compress",
                    data_class=policy.data_class,
                    rows=len(rows),
                    bytes_reclaimed=reclaimed,
                )
        return report

    # ------------------------------------------------------------------ #
    # Stage (b): summarize — semantic rows past the hot window
    # ------------------------------------------------------------------ #

    async def summarize(self, report: Optional[EntropyReport] = None) -> EntropyReport:
        """Collapse groups of >threshold semantic detail rows past the hot
        window into ONE summary row per (tenant_id, agent_id) group per
        window. Originals are marked archived, never deleted here."""
        await self._ensure()
        now = self._clock()
        report = report or EntropyReport(generated_at=now.isoformat(), dry_run=True)

        for policy in self._stage_policies("summarize"):
            if policy.table != "semantic" or policy.hot_days is None:
                continue
            cutoff = self._cutoff(now, policy.hot_days)
            spec = _TABLES[policy.table]
            groups = await self.db.fetch(
                f"""
                SELECT tenant_id, agent_id, COUNT(*) AS n,
                       MIN(created_at) AS window_start,
                       MAX(created_at) AS window_end
                FROM {spec['fq']}
                WHERE created_at < $1 AND ($2::text IS NULL OR tenant_id = $2)
                  AND lifecycle = 'hot'
                  AND {self._predicate(3)}
                GROUP BY tenant_id, agent_id
                HAVING COUNT(*) > $4
                """,
                cutoff, self._tenant, policy.class_tag, self.summarize_threshold,
            )
            for group in groups:
                details = await self.db.fetch(
                    f"""
                    SELECT id, content
                    FROM {spec['fq']}
                    WHERE tenant_id = $1 AND agent_id = $2
                      AND created_at < $3 AND lifecycle = 'hot'
                      AND {self._predicate(4)}
                    ORDER BY created_at, id
                    """,
                    group["tenant_id"], group["agent_id"], cutoff, policy.class_tag,
                )
                snippets = "; ".join(str(d["content"])[:80] for d in details[:3])
                summary_text = (
                    f"[ENTROPY SUMMARY] {len(details)} {policy.data_class} memories "
                    f"for agent {group['agent_id']} between "
                    f"{group['window_start'].isoformat()} and "
                    f"{group['window_end'].isoformat()}. Highlights: {snippets}"
                )
                summary_metadata = {
                    "data_class": policy.class_tag,
                    "_summary": True,
                    "summarized_count": len(details),
                    "window_start": group["window_start"].isoformat(),
                    "window_end": group["window_end"].isoformat(),
                    "source_ids": [str(d["id"]) for d in details],
                }
                await self.db.execute(
                    f"""
                    INSERT INTO {spec['fq']}
                        (id, tenant_id, agent_id, content, metadata,
                         lifecycle, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, 'hot', $6, $6)
                    """,
                    str(uuid.uuid4()), group["tenant_id"], group["agent_id"],
                    summary_text, json.dumps(summary_metadata), now,
                )
                status = await self.db.execute(
                    f"""
                    UPDATE {spec['fq']}
                    SET lifecycle = 'archived', updated_at = $5
                    WHERE tenant_id = $1 AND agent_id = $2
                      AND created_at < $3 AND lifecycle = 'hot'
                      AND {self._predicate(4)}
                      AND COALESCE((metadata->>'_summary')::boolean, false) = false
                    """,
                    group["tenant_id"], group["agent_id"], cutoff,
                    policy.class_tag, now,
                )
                archived = self._rowcount(status)
                report._bump(policy.data_class, "summarized_rows", archived)
                report._bump(policy.data_class, "summary_rows_created", 1)
                logger.info(
                    "entropy_summarize",
                    data_class=policy.data_class,
                    tenant_id=group["tenant_id"],
                    agent_id=group["agent_id"],
                    detail_rows=archived,
                )
        return report

    # ------------------------------------------------------------------ #
    # Stage (c): archive — anything past the warm window
    # ------------------------------------------------------------------ #

    async def archive(self, report: Optional[EntropyReport] = None) -> EntropyReport:
        """Set lifecycle='archived' on rows past the warm window."""
        await self._ensure()
        now = self._clock()
        report = report or EntropyReport(generated_at=now.isoformat(), dry_run=True)

        for policy in self._stage_policies("archive"):
            if policy.warm_days is None:
                continue
            cutoff = self._cutoff(now, policy.warm_days)
            spec = _TABLES[policy.table]
            status = await self.db.execute(
                f"""
                UPDATE {spec['fq']}
                SET lifecycle = 'archived', updated_at = $2
                WHERE created_at < $1 AND ($3::text IS NULL OR tenant_id = $3)
                  AND lifecycle <> 'archived'
                  AND {self._predicate(4)}
                """,
                cutoff, now, self._tenant, policy.class_tag,
            )
            count = self._rowcount(status)
            report._bump(policy.data_class, "archived", count)
            if count:
                logger.info(
                    "entropy_archive", data_class=policy.data_class, rows=count
                )
        return report

    # ------------------------------------------------------------------ #
    # Stage (d): purge — DELETE past the cold window (governed)
    # ------------------------------------------------------------------ #

    async def purge(
        self,
        governance_approval: bool = False,
        report: Optional[EntropyReport] = None,
    ) -> EntropyReport:
        """Permanently delete rows past the cold window.

        Requires ``governance_approval=True`` to actually delete; the
        default is a dry-run that only reports what WOULD be purged.
        never_purge classes (e.g. SOX) are never deleted, approval or not.
        """
        await self._ensure()
        now = self._clock()
        report = report or EntropyReport(
            generated_at=now.isoformat(), dry_run=not governance_approval
        )
        report.dry_run = not governance_approval

        for policy in self._stage_policies("purge"):
            if policy.never_purge or policy.cold_days is None:
                continue
            cutoff = self._cutoff(now, policy.cold_days)
            spec = _TABLES[policy.table]
            candidate = await self.db.fetchone(
                f"""
                SELECT COUNT(*) AS n, COALESCE(SUM({spec['bytes']}), 0) AS bytes
                FROM {spec['fq']}
                WHERE created_at < $1 AND ($2::text IS NULL OR tenant_id = $2) AND {self._predicate(3)}
                """,
                cutoff, self._tenant, policy.class_tag,
            )
            candidates = candidate["n"]
            report._bump(policy.data_class, "purge_candidates", candidates)
            if not candidates:
                continue

            if governance_approval:
                status = await self.db.execute(
                    f"""
                    DELETE FROM {spec['fq']}
                    WHERE created_at < $1 AND ($2::text IS NULL OR tenant_id = $2) AND {self._predicate(3)}
                    """,
                    cutoff, self._tenant, policy.class_tag,
                )
                purged = self._rowcount(status)
                report._bump(policy.data_class, "purged", purged)
                report.bytes_reclaimed += int(candidate["bytes"])
                logger.info(
                    "entropy_purge",
                    data_class=policy.data_class,
                    rows=purged,
                    bytes_reclaimed=int(candidate["bytes"]),
                )
            else:
                logger.info(
                    "entropy_purge_dry_run",
                    data_class=policy.data_class,
                    would_purge=candidates,
                    would_reclaim_bytes=int(candidate["bytes"]),
                )
        return report

    # ------------------------------------------------------------------ #
    # Full cycle
    # ------------------------------------------------------------------ #

    async def apply(self, governance_approval: bool = False,
                tenant_id: str | None = None) -> EntropyReport:
        """Run the full decay chain (compress → summarize → archive → purge)
        across all policies, return an EntropyReport, and append a JSONL
        journal line when a journal path is configured."""
        await self._ensure()
        self._tenant = tenant_id
        now = self._clock()
        report = EntropyReport(
            generated_at=now.isoformat(), dry_run=not governance_approval
        )

        await self.compress(report)
        await self.summarize(report)
        await self.archive(report)
        await self.purge(governance_approval=governance_approval, report=report)

        if self.journal_path:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self.journal_path.open("a", encoding="utf-8") as journal:
                journal.write(json.dumps(report.to_dict(), default=str) + "\n")

        logger.info(
            "entropy_cycle_complete",
            dry_run=report.dry_run,
            stages=report.stages,
            bytes_reclaimed=report.bytes_reclaimed,
        )
        return report
