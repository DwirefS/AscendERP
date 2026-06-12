"""
Deterministic factory seed data for the Manufacturing flavor.

`build_seed(seed)` builds a small but realistic discrete-manufacturing plant:
8 machines across 3 work centers (cutting, machining, assembly), 4 products
with 2-4 step routings and BOMs over 10 raw materials, inventory items with
reorder points and lead times, 4 suppliers with varied OTD/defect/lead-time
profiles, and 12 open work orders with staggered due dates and priorities.

All randomness flows through a single ``numpy.random.Generator`` seeded with
``seed`` and all ids are fixed strings, so the same seed always yields exactly
the same data (tests, the simulator, and the swarm engine rely on this).
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import structlog

from flavors.manufacturing.models import (
    BOMLine,
    InventoryItem,
    Machine,
    Priority,
    Product,
    Supplier,
    WorkOrder,
    WorkOrderStatus,
)

logger = structlog.get_logger()

#: Fixed time origin for all seeded due dates / schedules (a Monday, 06:00).
SEED_ANCHOR = datetime(2026, 1, 5, 6, 0, 0)

# (machine_id, name, work_center, operations, uph, setup_min, mtbf_h, vibration, scrap)
_MACHINE_SPECS = [
    ("M-CUT-01", "Laser Cutter A", "cutting", ("cut",), 40.0, 15.0, 420.0, 0.05, 0.008),
    ("M-CUT-02", "Band Saw B", "cutting", ("cut",), 25.0, 10.0, 300.0, 0.15, 0.012),
    ("M-MILL-01", "CNC Mill 1", "machining", ("machine",), 18.0, 30.0, 380.0, 0.10, 0.010),
    ("M-MILL-02", "CNC Mill 2 (aging)", "machining", ("machine",), 14.0, 35.0, 150.0, 0.55, 0.020),
    ("M-TURN-01", "CNC Lathe 1", "machining", ("machine",), 20.0, 25.0, 320.0, 0.20, 0.012),
    ("M-ASM-01", "Assembly Cell 1", "assembly", ("assemble",), 12.0, 20.0, 500.0, 0.05, 0.008),
    ("M-ASM-02", "Assembly Cell 2", "assembly", ("assemble",), 10.0, 20.0, 450.0, 0.10, 0.010),
    ("M-TEST-01", "Test & Pack Station", "assembly", ("assemble", "test"), 15.0, 10.0, 550.0, 0.03, 0.005),
]

# material_id -> (name, unit_cost, preferred_supplier_id)
_MATERIAL_SPECS = {
    "RM-STEEL": ("Steel Sheet 3mm", 12.0, "SUP-1"),
    "RM-ALU": ("Aluminium Billet", 9.0, "SUP-1"),
    "RM-BRG": ("Bearing Kit", 6.5, "SUP-2"),
    "RM-FST": ("Fastener Pack", 0.4, "SUP-2"),
    "RM-MTR": ("Drive Motor 1.5kW", 85.0, "SUP-3"),
    "RM-GBX": ("Gearbox 20:1", 60.0, "SUP-3"),
    "RM-PNT": ("Powder Coat Paint", 18.0, "SUP-3"),
    "RM-SEAL": ("Seal Kit", 3.2, "SUP-2"),
    "RM-PCB": ("Control Board v4", 45.0, "SUP-4"),
    "RM-PKG": ("Packaging Set", 2.1, "SUP-2"),
}

_PRODUCT_SPECS = [
    ("P-100", "Conveyor Roller", ["cut", "machine"], 85.0, 52.0,
     [("RM-STEEL", 2.0), ("RM-BRG", 2.0), ("RM-SEAL", 1.0)]),
    ("P-200", "Drive Assembly", ["cut", "machine", "assemble"], 240.0, 150.0,
     [("RM-ALU", 1.5), ("RM-GBX", 1.0), ("RM-FST", 4.0), ("RM-SEAL", 2.0)]),
    ("P-300", "Motorized Conveyor Unit", ["cut", "machine", "assemble", "test"], 520.0, 330.0,
     [("RM-STEEL", 3.0), ("RM-MTR", 1.0), ("RM-PCB", 1.0), ("RM-FST", 6.0), ("RM-PNT", 0.4)]),
    ("P-400", "Frame Kit", ["cut", "assemble"], 130.0, 78.0,
     [("RM-STEEL", 4.0), ("RM-FST", 8.0), ("RM-PNT", 0.6), ("RM-PKG", 1.0)]),
]

_SUPPLIER_SPECS = [
    ("SUP-1", "Atlas Metals", ["RM-STEEL", "RM-ALU"], 0.97, 180.0, 5.0, 1.08, "domestic"),
    ("SUP-2", "Pacifica Components", ["RM-BRG", "RM-FST", "RM-SEAL", "RM-PKG"], 0.82, 1900.0, 21.0, 0.78, "overseas"),
    ("SUP-3", "Midline Industrial", ["RM-GBX", "RM-MTR", "RM-PNT"], 0.90, 650.0, 10.0, 0.96, "domestic"),
    ("SUP-4", "Voltaic Electronics", ["RM-PCB", "RM-MTR"], 0.93, 400.0, 14.0, 1.18, "overseas"),
]

#: Deterministic tight/loose pattern for the 12 work orders (True = tight due date).
_TIGHT_PATTERN = [True, False, True, False, True, False, True, False, False, True, False, False]

_CUSTOMER_IDS = [f"CUST-{i:02d}" for i in range(1, 6)]

#: Days of demand the seeded work-order book roughly represents (used for
#: daily-usage and reorder-point estimates).
DEMAND_BASIS_DAYS = 14.0


@dataclass
class FactorySeed:
    """Container for one deterministic plant snapshot."""
    seed: int
    anchor: datetime
    machines: List[Machine] = field(default_factory=list)
    products: List[Product] = field(default_factory=list)
    inventory: List[InventoryItem] = field(default_factory=list)
    suppliers: List[Supplier] = field(default_factory=list)
    work_orders: List[WorkOrder] = field(default_factory=list)
    customer_ids: List[str] = field(default_factory=list)

    @property
    def products_by_id(self) -> Dict[str, Product]:
        return {p.product_id: p for p in self.products}

    @property
    def inventory_by_id(self) -> Dict[str, InventoryItem]:
        return {i.material_id: i for i in self.inventory}


def build_seed(seed: int = 42) -> FactorySeed:
    """
    Build the deterministic factory seed.

    Args:
        seed: Base random seed; the same value always produces identical data.

    Returns:
        A fully populated :class:`FactorySeed`.
    """
    rng = np.random.default_rng(seed)

    machines: List[Machine] = []
    for mid, name, wc, ops, uph, setup, mtbf, vib, scrap in _MACHINE_SPECS:
        machines.append(Machine(
            machine_id=mid,
            name=name,
            work_center=wc,
            operations=list(ops),
            units_per_hour=round(uph * float(rng.uniform(0.9, 1.15)), 2),
            setup_minutes=round(setup * float(rng.uniform(0.85, 1.2)), 1),
            mtbf_hours=round(mtbf * float(rng.uniform(0.85, 1.15)), 1),
            mttr_hours=round(float(rng.uniform(1.5, 6.0)), 2),
            vibration_trend=round(min(1.0, vib * float(rng.uniform(0.8, 1.3))), 3),
            scrap_rate_baseline=round(scrap * float(rng.uniform(0.8, 1.4)), 4),
            runtime_hours_since_pm=round(float(rng.uniform(0.0, 300.0)), 1),
        ))

    products = [
        Product(
            product_id=pid,
            name=name,
            routing=list(routing),
            bom=[BOMLine(material_id=m, quantity_per_unit=q) for m, q in bom],
            unit_price=price,
            standard_cost=cost,
        )
        for pid, name, routing, price, cost, bom in _PRODUCT_SPECS
    ]

    suppliers = [
        Supplier(
            supplier_id=sid, name=name, materials=list(mats),
            otd_rate=otd, defect_ppm=ppm, lead_time_days=lead,
            price_index=price_idx, region=region,
        )
        for sid, name, mats, otd, ppm, lead, price_idx, region in _SUPPLIER_SPECS
    ]
    supplier_lead = {s.supplier_id: s.lead_time_days for s in suppliers}

    # 12 open work orders: every product appears at least once, the rest drawn
    # from the generator; tight/loose due dates follow a fixed pattern.
    product_ids = [p.product_id for p in products]
    wo_products = list(product_ids) + [
        product_ids[int(rng.integers(0, len(product_ids)))] for _ in range(8)
    ]
    work_orders: List[WorkOrder] = []
    for i in range(12):
        tight = _TIGHT_PATTERN[i]
        quantity = float(int(rng.integers(20, 121)))
        if tight:
            due_hours = float(rng.uniform(24.0, 72.0))
            priority = Priority.CRITICAL if rng.random() < 0.4 else Priority.HIGH
        else:
            due_hours = float(rng.uniform(120.0, 400.0))
            priority = Priority.NORMAL if rng.random() < 0.7 else Priority.LOW
        work_orders.append(WorkOrder(
            work_order_id=f"WO-{i + 1:04d}",
            product_id=wo_products[i],
            quantity=quantity,
            due_date=SEED_ANCHOR + timedelta(hours=round(due_hours, 1)),
            status=WorkOrderStatus.RELEASED,
            priority=priority,
            customer_id=_CUSTOMER_IDS[int(rng.integers(0, len(_CUSTOMER_IDS)))],
            released_at=SEED_ANCHOR,
        ))

    # Inventory sized off the open order book: some items comfortably stocked,
    # some near (or below) their reorder points.
    products_by_id = {p.product_id: p for p in products}
    need: Dict[str, float] = defaultdict(float)
    for wo in work_orders:
        for line in products_by_id[wo.product_id].bom:
            need[line.material_id] += line.quantity_per_unit * wo.quantity

    inventory: List[InventoryItem] = []
    for material_id, (name, unit_cost, pref_sup) in _MATERIAL_SPECS.items():
        daily_usage = max(need.get(material_id, 0.0) / DEMAND_BASIS_DAYS, 1.0)
        lead_days = supplier_lead[pref_sup]
        safety = round(daily_usage * 3.0, 1)
        inventory.append(InventoryItem(
            material_id=material_id,
            name=name,
            on_hand=round(need.get(material_id, 0.0) * float(rng.uniform(0.5, 1.3))
                          + daily_usage * 2.0, 1),
            on_order=0.0,
            reorder_point=round(daily_usage * lead_days + safety, 1),
            safety_stock=safety,
            unit_cost=unit_cost,
            lead_time_days=lead_days,
            preferred_supplier_id=pref_sup,
        ))

    factory = FactorySeed(
        seed=seed,
        anchor=SEED_ANCHOR,
        machines=machines,
        products=products,
        inventory=inventory,
        suppliers=suppliers,
        work_orders=work_orders,
        customer_ids=list(_CUSTOMER_IDS),
    )
    logger.debug(
        "factory_seed_built",
        seed=seed,
        machines=len(machines),
        products=len(products),
        materials=len(inventory),
        suppliers=len(suppliers),
        work_orders=len(work_orders),
    )
    return factory
