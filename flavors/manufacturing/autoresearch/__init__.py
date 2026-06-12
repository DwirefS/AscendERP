"""
AutoOptimize loop (Karpathy autoresearch-inspired) for scheduling policies.

See docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §3.3.
"""
from flavors.manufacturing.autoresearch.optimize_loop import (
    DEFAULT_OBJECTIVE_WEIGHTS,
    DISPATCH_RULES,
    FLOAT_BOUNDS,
    MUTABLE_FIELDS,
    AutoOptimizeLoop,
)

__all__ = [
    "AutoOptimizeLoop",
    "DEFAULT_OBJECTIVE_WEIGHTS",
    "DISPATCH_RULES",
    "FLOAT_BOUNDS",
    "MUTABLE_FIELDS",
]
