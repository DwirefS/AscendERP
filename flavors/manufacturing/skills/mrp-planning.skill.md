---
name: mrp-planning
version: 1.0.0
domain: manufacturing
description: Explode BOMs, net requirements against inventory, and choose lot sizes with explicit trade-off reasoning.
triggers:
  - mrp
  - bom explosion
  - material requirements
  - netting
  - lot sizing
  - planned order
  - shortage
  - reorder
  - safety stock
tools:
  - inventory_query
  - bom_explorer
  - po_writer
  - policy_scheduler
---
# MRP Planning Procedure

## 1. BOM explosion
1. Start from independent demand: open work/sales orders + forecast, by due date.
2. Explode level by level (low-level coding: process each material at its
   deepest BOM level only once, after all parents are netted).
3. Gross requirement per component = Σ over parents of
   (parent planned quantity × quantity_per_unit), offset by the parent's
   lead time so the component is due when the parent *starts*, not ships.
4. Include scrap/yield allowance where the routing has a known loss rate:
   gross ÷ (1 − scrap_rate). Don't double-count if already in the BOM factor.

## 2. Netting logic (per material, per period, in date order)
```
net_requirement = gross_requirement
                − on_hand_available (on_hand − safety_stock − allocations)
                − scheduled_receipts (open POs / open work orders)
```
- Negative net ⇒ covered; carry the projected balance forward.
- Positive net ⇒ create a planned order, offset by lead time.
  If the offset start lands in the past, flag as **expedite** — do not
  silently plan in the past.
- Safety stock is a floor, not free inventory: netting that dips into it
  should raise a warning even when no order is strictly needed yet.

## 3. Lot sizing trade-offs
| Method | Pick when | Cost of choosing it |
|---|---|---|
| **Lot-for-lot (L4L)** | Expensive items, volatile demand, short setups | Max order count → ordering/setup cost, supplier irritation |
| **EOQ** = √(2·D·S/H) | Stable demand, real setup + holding costs known | Ignores lumpy timing; remnants create carry-over stock |
| **Fixed period (POQ)** | Regular delivery cadence (weekly bucket) | Averages demand spikes into the bucket — verify capacity |
| **Min/Max (ROP)** | Cheap C-class hardware, consumables | Decoupled from the plan; can miss demand steps |
- Larger lots: fewer setups, better unit price — but more WIP, longer queues,
  slower defect discovery (a bad lot is a *big* bad lot), more cash tied up.
- Smaller lots: better flow and OTD — but setup share rises; check the
  bottleneck's setup share (<20%) before reducing lot sizes there.

## 4. Sanity checks before releasing the plan
1. Capacity: rough-cut check planned hours vs available hours per work
   center; >95% on the bottleneck means the plan is fiction — re-level.
2. Supplier: planned PO inside supplier lead time ⇒ expedite flag + suggest
   an alternate supplier from the qualified list (compare OTD %, defect ppm).
3. Nervousness: avoid re-planning churn — apply a time fence (frozen ~1 lead
   time) and only auto-change orders outside it.
4. Output: planned orders (material, qty, start, due), expedite list,
   shortage projection vs schedule, and assumptions used.
