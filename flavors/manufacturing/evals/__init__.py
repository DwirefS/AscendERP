"""
Manufacturing Evidence Engine (WS-3).

Golden tasks with analytically known answers for the SPC quality agent,
reorder-point procurement agent and predictive-maintenance agent, plus the
two headline experiments (solo vs council NCR disposition, dispatch-rule
policy eval). Run everything with ``python -m flavors.manufacturing.evals``.
"""
from flavors.manufacturing.evals.golden_tasks import (
    MAINTENANCE_TASKS,
    REORDER_TASKS,
    SPC_TASKS,
    maintenance_subject,
    reorder_subject,
    spc_subject,
)
from flavors.manufacturing.evals.experiments import (
    run_dispatch_policy_eval,
    run_solo_vs_council_disposition,
)

__all__ = [
    "MAINTENANCE_TASKS",
    "REORDER_TASKS",
    "SPC_TASKS",
    "maintenance_subject",
    "reorder_subject",
    "spc_subject",
    "run_dispatch_policy_eval",
    "run_solo_vs_council_disposition",
]
