"""
Manufacturing PRREEL agents.

Six BaseAgent subclasses implementing deterministic, LLM-optional domain
logic per the manufacturing flavor design (docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §4).
"""

from flavors.manufacturing.agents.production_planner_agent import ProductionPlannerAgent
from flavors.manufacturing.agents.quality_agent import QualityAgent
from flavors.manufacturing.agents.maintenance_agent import MaintenanceAgent
from flavors.manufacturing.agents.procurement_agent import ProcurementAgent, PO_APPROVAL_THRESHOLD
from flavors.manufacturing.agents.inventory_agent import InventoryAgent
from flavors.manufacturing.agents.ehs_compliance_agent import EHSComplianceAgent, LOTO_REQUIRED_STEPS

__all__ = [
    "ProductionPlannerAgent",
    "QualityAgent",
    "MaintenanceAgent",
    "ProcurementAgent",
    "InventoryAgent",
    "EHSComplianceAgent",
    "PO_APPROVAL_THRESHOLD",
    "LOTO_REQUIRED_STEPS",
]
