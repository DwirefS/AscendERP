---
name: spc-analysis
version: 1.0.0
domain: manufacturing
description: Interpret control charts, apply Western Electric rules, and judge process capability (Cp/Cpk) on inspection measurement series.
triggers:
  - spc
  - control chart
  - western electric
  - out of control
  - process capability
  - cpk
  - inspection measurements
  - quality trend
tools:
  - quality_inspections
  - ncr_writer
---
# SPC Analysis Procedure

## 1. Build the chart correctly
1. Use at least 20–25 subgroups before trusting control limits.
2. Compute center line (X̄) and limits at ±3σ from the *process* data, never
   from the spec limits. Control limits describe the voice of the process;
   spec limits describe the voice of the customer. Do not mix them.
3. Zones: Zone C = within 1σ, Zone B = 1–2σ, Zone A = 2–3σ of the center line.

## 2. Western Electric rules (signal = special cause)
1. **Rule 1:** one point beyond 3σ (Zone A boundary) — strongest signal.
2. **Rule 2:** 2 of 3 consecutive points beyond 2σ on the same side.
3. **Rule 3:** 4 of 5 consecutive points beyond 1σ on the same side.
4. **Rule 4:** 8 consecutive points on the same side of the center line.
Supplementary patterns worth flagging:
- 6 points steadily increasing/decreasing → trend (tool wear, warm-up drift).
- 14 points alternating up/down → overcontrol or two-stream sampling.
- Sudden tightening (15 points hugging the center) → check the gauge or
  suspect data — processes rarely improve spontaneously.

## 3. Respond proportionally
- One signal ⇒ investigate that timeframe: material lot change, shift change,
  setup, tool replacement, gauge recalibration.
- Repeated signals ⇒ stop, contain (quarantine since last good check), open an
  NCR with the affected work order and quantity, escalate severity if shipped.
- No signal ⇒ leave the process alone. Adjusting a stable process on noise
  (tampering) *increases* variation.

## 4. Capability (only when in control)
- Cp = (USL − LSL) / 6σ — potential capability, ignores centering.
- Cpk = min(USL − μ, μ − LSL) / 3σ — actual capability with centering.
- Guidance: Cpk ≥ 1.67 excellent (safety-critical target), 1.33–1.67
  capable, 1.0–1.33 marginal (tighten control, consider 100% inspection),
  < 1.0 not capable (expect nonconformances; containment + improvement).
- Cp high but Cpk low ⇒ the process is precise but off-center: re-center
  first (cheap) before attacking variation (expensive).
- Never report Cpk for an out-of-control process — the σ estimate is invalid.

## 5. Output expectations
Report: chart type, rule(s) violated with point indices, probable-cause
hypotheses, containment recommendation, Cp/Cpk with sample size, and a
disposition recommendation (use-as-is / rework / scrap) with rationale.
