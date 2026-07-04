"""
Evaluation harness (WS-3 Evidence Engine).

Converts claims into measured numbers: golden tasks with known answers are
executed against a subject callable, timed and scored; reports are compared
and rendered into scorecards (markdown/JSON).
"""
from src.core.evals.runner import EvalReport, EvalRunner, GoldenTask, TaskResult
from src.core.evals.scorecard import Scorecard

__all__ = [
    "EvalReport",
    "EvalRunner",
    "GoldenTask",
    "Scorecard",
    "TaskResult",
]
