"""
Scorecard: side-by-side comparison and rendering of EvalReports.

``Scorecard.compare`` produces a deterministic comparison dict;
``Scorecard.to_markdown`` renders reports (and an optional comparison) as
readable tables; ``Scorecard.to_json`` writes everything to disk.

Ordering is deterministic everywhere: reports keep their given order, task
rows are sorted by ``task_id``, and comparison winners break ties by report
name.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import structlog

from src.core.evals.runner import EvalReport

logger = structlog.get_logger()


class Scorecard:
    """Comparison and rendering utilities over :class:`EvalReport` objects."""

    @staticmethod
    def compare(reports: Sequence[EvalReport]) -> Dict[str, Any]:
        """
        Build a side-by-side comparison of reports.

        Returns a dict with one summary row per report (given order) and the
        winning report by mean score (ties broken by name, ascending).
        """
        rows: List[Dict[str, Any]] = [
            {
                "name": r.name,
                "tasks": len(r.results),
                "mean_score": round(r.mean_score, 4),
                "pass_rate": round(r.pass_rate, 4),
                "p50_latency_ms": round(r.p50_latency_ms, 3),
                "p95_latency_ms": round(r.p95_latency_ms, 3),
            }
            for r in reports
        ]
        best: Optional[str] = None
        if rows:
            best = min(rows, key=lambda row: (-row["mean_score"], row["name"]))["name"]

        # Per-task side-by-side where task ids overlap (sorted for determinism).
        task_scores: Dict[str, Dict[str, float]] = {}
        for report in reports:
            for result in report.results:
                task_scores.setdefault(result.task_id, {})[report.name] = round(
                    result.score, 4
                )
        by_task = {task_id: task_scores[task_id] for task_id in sorted(task_scores)}

        return {"reports": rows, "best": best, "by_task": by_task}

    @staticmethod
    def to_markdown(
        reports: Sequence[EvalReport],
        comparison: Optional[Dict[str, Any]] = None,
        title: str = "Eval Scorecard",
    ) -> str:
        """Render reports (and an optional comparison) as markdown tables."""
        lines: List[str] = [f"# {title}", ""]

        lines.append("## Summary")
        lines.append("")
        lines.append("| Report | Tasks | Mean score | Pass rate | p50 ms | p95 ms |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for r in reports:
            lines.append(
                f"| {r.name} | {len(r.results)} | {r.mean_score:.4f} "
                f"| {r.pass_rate:.2%} | {r.p50_latency_ms:.1f} "
                f"| {r.p95_latency_ms:.1f} |"
            )
        lines.append("")

        for r in reports:
            lines.append(f"## {r.name}")
            lines.append("")
            lines.append(
                f"Ran {len(r.results)} tasks, {r.started_at.isoformat()} -> "
                f"{r.finished_at.isoformat()}."
            )
            lines.append("")
            lines.append("| Task | Score | Latency ms | Error |")
            lines.append("|---|---:|---:|---|")
            for result in sorted(r.results, key=lambda x: x.task_id):
                lines.append(
                    f"| {result.task_id} | {result.score:.3f} "
                    f"| {result.latency_ms:.1f} | {result.error or ''} |"
                )
            lines.append("")

        if comparison is not None:
            lines.append("## Comparison")
            lines.append("")
            best = comparison.get("best")
            if best is not None:
                lines.append(f"Best mean score: **{best}**")
                lines.append("")
            by_task = comparison.get("by_task") or {}
            names = [row["name"] for row in comparison.get("reports", [])]
            if by_task and names:
                header = "| Task | " + " | ".join(names) + " |"
                lines.append(header)
                lines.append("|---|" + "---:|" * len(names))
                for task_id in sorted(by_task):
                    scores = by_task[task_id]
                    cells = [
                        f"{scores[n]:.3f}" if n in scores else "-" for n in names
                    ]
                    lines.append(f"| {task_id} | " + " | ".join(cells) + " |")
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def to_json(
        path: Union[str, Path],
        reports: Sequence[EvalReport],
        comparison: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Write reports (+ optional comparison/extra) as JSON; returns the path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: Dict[str, Any] = {
            "reports": [r.to_dict() for r in reports],
        }
        if comparison is not None:
            payload["comparison"] = comparison
        if extra is not None:
            payload["extra"] = extra
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
        logger.info("scorecard_json_written", path=str(path), reports=len(reports))
        return path
