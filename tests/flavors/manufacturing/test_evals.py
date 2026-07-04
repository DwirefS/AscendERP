"""
Tests for the WS-3 Evidence Engine: core EvalRunner/Scorecard mechanics and
the manufacturing golden tasks + experiments against the real agents.

Ground truth for the golden tasks is derived from the agents' own documented
rules, so the real agents are expected to score highly — these tests are the
proof that the eval harness measures what the code actually does.
"""
import asyncio
import json

import pytest

from src.core.evals.runner import EvalRunner, GoldenTask
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


def _exact_scorer(actual, expected):
    return 1.0 if actual == expected["value"] else 0.0


def _make_task(task_id="t1", value=42, scorer=_exact_scorer):
    return GoldenTask(
        task_id=task_id,
        description="test task",
        input_data={"value": value},
        expected={"value": value},
        scorer=scorer,
        tags=["test"],
        domain="test",
    )


# ---------------------------------------------------------------------------
# EvalRunner core mechanics
# ---------------------------------------------------------------------------


async def test_runner_scores_latency_and_aggregates():
    async def subject(input_data):
        return input_data["value"]

    tasks = [_make_task("a", 1), _make_task("b", 2)]
    report = await EvalRunner().run(tasks, subject, name="unit")

    assert report.name == "unit"
    assert [r.task_id for r in report.results] == ["a", "b"]
    assert all(r.score == 1.0 for r in report.results)
    assert all(r.latency_ms >= 0.0 for r in report.results)
    assert report.mean_score == 1.0
    assert report.pass_rate == 1.0
    assert report.p50_latency_ms <= report.p95_latency_ms
    assert report.finished_at >= report.started_at


async def test_runner_exception_scores_zero_with_error():
    async def subject(input_data):
        if input_data["value"] == 2:
            raise ValueError("boom")
        return input_data["value"]

    tasks = [_make_task("ok", 1), _make_task("bad", 2)]
    report = await EvalRunner().run(tasks, subject, name="unit")

    bad = next(r for r in report.results if r.task_id == "bad")
    assert bad.score == 0.0
    assert "boom" in bad.error
    assert report.mean_score == pytest.approx(0.5)
    assert report.pass_rate == pytest.approx(0.5)


async def test_runner_timeout_scores_zero():
    async def slow_subject(input_data):
        await asyncio.sleep(5.0)
        return input_data["value"]

    report = await EvalRunner(timeout_s=0.05).run(
        [_make_task("slow", 1)], slow_subject, name="unit"
    )
    result = report.results[0]
    assert result.score == 0.0
    assert "timeout" in result.error


async def test_runner_clamps_scorer_output():
    def wild_scorer(actual, expected):
        return 5.0 if actual > 0 else -3.0

    async def subject(input_data):
        return input_data["value"]

    tasks = [
        _make_task("hi", 1, scorer=wild_scorer),
        _make_task("lo", -1, scorer=wild_scorer),
    ]
    report = await EvalRunner().run(tasks, subject, name="unit")
    scores = {r.task_id: r.score for r in report.results}
    assert scores == {"hi": 1.0, "lo": 0.0}


# ---------------------------------------------------------------------------
# Scorecard
# ---------------------------------------------------------------------------


async def test_scorecard_markdown_contains_task_rows_and_summary():
    async def subject(input_data):
        return input_data["value"]

    report = await EvalRunner().run(
        [_make_task("alpha", 1), _make_task("beta", 2)], subject, name="md_report"
    )
    markdown = Scorecard.to_markdown([report], title="Test Card")

    assert "# Test Card" in markdown
    assert "| md_report |" in markdown
    assert "| alpha |" in markdown
    assert "| beta |" in markdown


async def test_scorecard_compare_and_json_roundtrip(tmp_path):
    async def good(input_data):
        return input_data["value"]

    async def bad(input_data):
        return -999

    tasks = [_make_task("a", 1), _make_task("b", 2)]
    runner = EvalRunner()
    winner = await runner.run(tasks, good, name="winner")
    loser = await runner.run(tasks, bad, name="loser")

    comparison = Scorecard.compare([winner, loser])
    assert comparison["best"] == "winner"
    assert [row["name"] for row in comparison["reports"]] == ["winner", "loser"]
    assert list(comparison["by_task"]) == ["a", "b"]  # sorted task ids

    path = Scorecard.to_json(tmp_path / "card.json", [winner, loser], comparison)
    payload = json.loads(path.read_text())
    assert len(payload["reports"]) == 2
    assert payload["comparison"]["best"] == "winner"


# ---------------------------------------------------------------------------
# Golden tasks against the real agents
# ---------------------------------------------------------------------------


async def test_spc_golden_tasks_against_real_quality_agent():
    report = await EvalRunner().run(SPC_TASKS, spc_subject, name="spc")
    assert len(report.results) == len(SPC_TASKS) >= 10
    failing = [(r.task_id, r.score, r.error) for r in report.results if r.score < 0.8]
    assert report.mean_score >= 0.8, f"SPC golden tasks below 0.8: {failing}"


async def test_reorder_golden_tasks_against_real_procurement_agent():
    report = await EvalRunner().run(REORDER_TASKS, reorder_subject, name="reorder")
    assert len(report.results) == len(REORDER_TASKS) >= 7
    failing = [(r.task_id, r.score, r.error) for r in report.results if r.score < 0.8]
    assert report.mean_score >= 0.8, f"Reorder golden tasks below 0.8: {failing}"


async def test_maintenance_golden_tasks_against_real_maintenance_agent():
    report = await EvalRunner().run(
        MAINTENANCE_TASKS, maintenance_subject, name="maintenance"
    )
    assert len(report.results) == len(MAINTENANCE_TASKS) >= 7
    failing = [(r.task_id, r.score, r.error) for r in report.results if r.score < 0.8]
    assert report.mean_score >= 0.8, f"Maintenance golden tasks below 0.8: {failing}"


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------


async def test_solo_vs_council_returns_two_reports_and_comparison():
    outcome = await run_solo_vs_council_disposition(seed=42)

    solo, council = outcome["solo"], outcome["council"]
    assert len(solo.results) == len(council.results) == 12
    assert 0.0 <= solo.mean_score <= 1.0
    assert 0.0 <= council.mean_score <= 1.0

    comparison = outcome["comparison"]
    assert {row["name"] for row in comparison["reports"]} == {
        "quality_agent_solo",
        "quality_council",
    }
    assert comparison["best"] in ("quality_agent_solo", "quality_council")
    # Deterministic subjects: a second run reproduces the exact scores.
    again = await run_solo_vs_council_disposition(seed=42)
    assert [r.score for r in again["solo"].results] == [r.score for r in solo.results]
    assert [r.score for r in again["council"].results] == [
        r.score for r in council.results
    ]


async def test_dispatch_policy_eval_ranks_all_five_rules():
    outcome = await run_dispatch_policy_eval(seed=42)
    report, ranking = outcome["report"], outcome["ranking"]

    assert len(report.results) == 5
    assert {entry["rule"] for entry in ranking} == {"EDD", "SPT", "CR", "WSPT", "FIFO"}
    # Ranking is sorted best-first by objective.
    objectives = [entry["objective"] for entry in ranking]
    assert objectives == sorted(objectives, reverse=True)
    # Real KPIs travel with the ranking.
    for entry in ranking:
        assert 0.0 <= entry["kpis"]["otd_rate"] <= 1.0
        assert 0.0 <= entry["kpis"]["oee"] <= 1.0
        assert entry["kpis"]["total_cost"] > 0.0


async def test_dispatch_policy_eval_deterministic_for_same_seed():
    first = await run_dispatch_policy_eval(seed=42)
    second = await run_dispatch_policy_eval(seed=42)

    def signature(outcome):
        return [
            (r.task_id, r.score, r.detail.get("objective"), r.detail.get("kpis"))
            for r in outcome["report"].results
        ]

    assert signature(first) == signature(second)
    assert [e["rule"] for e in first["ranking"]] == [
        e["rule"] for e in second["ranking"]
    ]
