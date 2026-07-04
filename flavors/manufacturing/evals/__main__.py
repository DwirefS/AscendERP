"""
Evidence Engine CLI: run every manufacturing golden-task set and experiment,
then write ``eval_reports/manufacturing_scorecard.{json,md}``.

Usage:
    ENCRYPTION_MASTER_KEY=dev-only-key python -m flavors.manufacturing.evals
    (or: make eval)

The markdown scorecard is committed as evidence; the JSON is gitignored.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import List

import structlog

from src.core.evals.runner import EvalReport, EvalRunner
from src.core.evals.scorecard import Scorecard
from flavors.manufacturing.evals.experiments import (
    run_dispatch_policy_eval,
    run_solo_vs_council_disposition,
)
from flavors.manufacturing.evals.golden_tasks import (
    MAINTENANCE_TASKS,
    REORDER_TASKS,
    SPC_TASKS,
    maintenance_subject,
    reorder_subject,
    spc_subject,
)

logger = structlog.get_logger()

DEFAULT_OUTPUT_DIR = Path("eval_reports")


def _dispatch_ranking_markdown(ranking: List[dict]) -> str:
    lines = [
        "## Dispatch Rule Ranking (168h, 3 replications, seed 42)",
        "",
        "Objective = 0.5*otd_rate + 0.3*oee - 0.2*total_cost/cost_baseline "
        "(AutoOptimizeLoop weights).",
        "",
        "| Rank | Rule | Objective | OTD | OEE | Scrap | Throughput | Total cost | Makespan h |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, entry in enumerate(ranking, start=1):
        kpis = entry.get("kpis", {})
        lines.append(
            f"| {idx} | {entry['rule']} | {entry['objective']:.4f} "
            f"| {kpis.get('otd_rate', 0):.3f} | {kpis.get('oee', 0):.3f} "
            f"| {kpis.get('scrap_rate', 0):.4f} "
            f"| {kpis.get('throughput_units', 0):.1f} "
            f"| {kpis.get('total_cost', 0):,.0f} "
            f"| {kpis.get('makespan_hours', 0):.1f} |"
        )
    lines.append("")
    return "\n".join(lines)


async def main(output_dir: Path = DEFAULT_OUTPUT_DIR) -> int:
    runner = EvalRunner()

    # 1. Golden task sets against the real agents.
    spc_report = await runner.run(SPC_TASKS, spc_subject, name="spc_golden_tasks")
    reorder_report = await runner.run(
        REORDER_TASKS, reorder_subject, name="reorder_golden_tasks"
    )
    maintenance_report = await runner.run(
        MAINTENANCE_TASKS, maintenance_subject, name="maintenance_golden_tasks"
    )
    golden_reports = [spc_report, reorder_report, maintenance_report]

    # 2. Headline experiments.
    disposition = await run_solo_vs_council_disposition(seed=42)
    dispatch = await run_dispatch_policy_eval(seed=42)

    all_reports: List[EvalReport] = [
        *golden_reports,
        disposition["solo"],
        disposition["council"],
        dispatch["report"],
    ]

    # 3. Write the scorecard (markdown = committed evidence, JSON = local).
    output_dir.mkdir(parents=True, exist_ok=True)
    md_parts = [
        Scorecard.to_markdown(
            golden_reports, title="Manufacturing Evidence Engine Scorecard"
        ),
        Scorecard.to_markdown(
            [disposition["solo"], disposition["council"]],
            comparison=disposition["comparison"],
            title="Experiment: Solo QualityAgent vs QualityCouncil (NCR disposition)",
        ).replace("# Experiment:", "## Experiment:", 1),
        Scorecard.to_markdown(
            [dispatch["report"]], title="Experiment: Dispatch Policy Eval"
        ).replace("# Experiment:", "## Experiment:", 1),
        _dispatch_ranking_markdown(dispatch["ranking"]),
    ]
    md_path = output_dir / "manufacturing_scorecard.md"
    md_path.write_text("\n".join(md_parts))
    json_path = Scorecard.to_json(
        output_dir / "manufacturing_scorecard.json",
        all_reports,
        comparison=disposition["comparison"],
        extra={"dispatch_ranking": dispatch["ranking"]},
    )

    # 4. Human summary.
    print("\n=== Evidence Engine results ===")
    for report in golden_reports:
        print(
            f"{report.name:28s} mean={report.mean_score:.4f} "
            f"pass_rate={report.pass_rate:.2%} tasks={len(report.results)}"
        )
    solo, council = disposition["solo"], disposition["council"]
    print(
        f"solo_vs_council              solo={solo.mean_score:.4f} "
        f"council={council.mean_score:.4f} best={disposition['comparison']['best']}"
    )
    ranking = dispatch["ranking"]
    print(
        "dispatch_ranking             "
        + " > ".join(f"{r['rule']}({r['objective']:.3f})" for r in ranking)
    )
    print(f"scorecard: {md_path} and {json_path}")

    failed = [r for r in all_reports if not r.results]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
