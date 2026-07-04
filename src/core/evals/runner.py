"""
Eval runner: executes golden tasks against a subject and scores the results.

A :class:`GoldenTask` carries a known-correct expectation and a scorer
``callable(actual, expected) -> float`` in ``[0, 1]``. The
:class:`EvalRunner` executes each task against a *subject*
(``callable(input_data) -> awaitable result``), measures wall-clock latency,
scores the result, and folds everything into an :class:`EvalReport`.

Failure semantics (per WS-3 design):
  * a subject exception scores 0.0 with the error recorded;
  * a subject timeout (optional ``timeout_s``) scores 0.0 with a timeout error;
  * scorer outputs are clamped into ``[0, 1]``;
  * a task *passes* when its score >= ``PASS_THRESHOLD`` (0.7).

Everything is deterministic given a deterministic subject: tasks run
sequentially in the order given, and no randomness is introduced here.
"""
from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

import structlog

logger = structlog.get_logger()

#: A task passes when its score reaches this threshold.
PASS_THRESHOLD = 0.7

Scorer = Callable[[Any, Dict[str, Any]], float]
Subject = Callable[[Dict[str, Any]], Awaitable[Any]]


@dataclass
class GoldenTask:
    """One benchmark task with a known-correct expectation."""

    task_id: str
    description: str
    input_data: Dict[str, Any]
    expected: Dict[str, Any]
    scorer: Scorer
    tags: List[str] = field(default_factory=list)
    domain: str = "general"


@dataclass
class TaskResult:
    """Outcome of one golden task run."""

    task_id: str
    score: float
    latency_ms: float
    error: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "score": round(self.score, 4),
            "latency_ms": round(self.latency_ms, 3),
            "error": self.error,
            "detail": self.detail,
        }


@dataclass
class EvalReport:
    """Aggregated results of one eval run."""

    name: str
    results: List[TaskResult]
    mean_score: float
    pass_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    started_at: datetime
    finished_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tasks": len(self.results),
            "mean_score": round(self.mean_score, 4),
            "pass_rate": round(self.pass_rate, 4),
            "p50_latency_ms": round(self.p50_latency_ms, 3),
            "p95_latency_ms": round(self.p95_latency_ms, 3),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "results": [r.to_dict() for r in self.results],
        }


def _percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile (deterministic, no interpolation surprises)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def _clamp01(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


class EvalRunner:
    """Executes golden tasks sequentially against a subject and scores them."""

    def __init__(self, timeout_s: Optional[float] = None) -> None:
        self.timeout_s = timeout_s

    async def run(
        self,
        tasks: Sequence[GoldenTask],
        subject: Subject,
        name: str,
    ) -> EvalReport:
        """
        Run every task against ``subject`` and aggregate an :class:`EvalReport`.

        Args:
            tasks: Golden tasks, executed in the given order.
            subject: ``callable(input_data) -> awaitable result``.
            name: Report name (e.g. the subject/experiment identifier).
        """
        started_at = datetime.utcnow()
        results: List[TaskResult] = []
        log = logger.bind(eval_name=name, tasks=len(tasks))
        log.info("eval_run_started")

        for task in tasks:
            t0 = time.monotonic()
            score = 0.0
            error: Optional[str] = None
            detail: Dict[str, Any] = {}
            try:
                coro = subject(task.input_data)
                if self.timeout_s is not None:
                    actual = await asyncio.wait_for(coro, timeout=self.timeout_s)
                else:
                    actual = await coro
                if isinstance(actual, dict) and isinstance(actual.get("detail"), dict):
                    detail = dict(actual["detail"])
                score = _clamp01(task.scorer(actual, task.expected))
            except asyncio.TimeoutError:
                error = f"timeout after {self.timeout_s}s"
                log.warning("eval_task_timeout", task_id=task.task_id)
            except Exception as exc:  # scored as zero — the eval must not crash
                error = f"{type(exc).__name__}: {exc}"
                log.warning("eval_task_error", task_id=task.task_id, error=str(exc))
            latency_ms = (time.monotonic() - t0) * 1000.0
            results.append(
                TaskResult(
                    task_id=task.task_id,
                    score=score,
                    latency_ms=latency_ms,
                    error=error,
                    detail=detail,
                )
            )

        finished_at = datetime.utcnow()
        scores = [r.score for r in results]
        latencies = [r.latency_ms for r in results]
        report = EvalReport(
            name=name,
            results=results,
            mean_score=sum(scores) / len(scores) if scores else 0.0,
            pass_rate=(
                sum(1 for s in scores if s >= PASS_THRESHOLD) / len(scores)
                if scores
                else 0.0
            ),
            p50_latency_ms=_percentile(latencies, 0.50),
            p95_latency_ms=_percentile(latencies, 0.95),
            started_at=started_at,
            finished_at=finished_at,
        )
        log.info(
            "eval_run_finished",
            mean_score=round(report.mean_score, 4),
            pass_rate=round(report.pass_rate, 4),
            p95_latency_ms=round(report.p95_latency_ms, 2),
        )
        return report
