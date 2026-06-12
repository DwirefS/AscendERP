"""Manufacturing workflows (capital-markets style: async run with stage results)."""

from flavors.manufacturing.workflows.order_to_production import (
    OrderToProductionWorkflow,
)
from flavors.manufacturing.workflows.predictive_maintenance import (
    PredictiveMaintenanceWorkflow,
)
from flavors.manufacturing.workflows.quality_rca import QualityRCAWorkflow
from flavors.manufacturing.workflows.supply_disruption_response import (
    SupplyDisruptionResponseWorkflow,
)

__all__ = [
    "OrderToProductionWorkflow",
    "PredictiveMaintenanceWorkflow",
    "QualityRCAWorkflow",
    "SupplyDisruptionResponseWorkflow",
]
