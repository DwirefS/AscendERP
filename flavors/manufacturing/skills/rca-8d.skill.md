---
name: rca-8d
version: 1.0.0
domain: manufacturing
description: Run a disciplined 8D root cause analysis with fishbone categories and 5-why drilling for nonconformances and field failures.
triggers:
  - root cause
  - rca
  - 8d
  - corrective action
  - capa
  - fishbone
  - five why
  - nonconformance
  - ncr investigation
tools:
  - ncr_writer
  - quality_inspections
  - maintenance_history
---
# 8D Root Cause Analysis Procedure

## The eight disciplines
1. **D1 — Team:** assemble people who touch the process (operator, quality,
   process engineer, supplier rep if material is implicated). One champion.
2. **D2 — Describe the problem:** quantify with Is/Is-Not — what part, what
   defect, how many, when first seen, where in the routing, which machines,
   which lots. A problem you can't state numerically isn't bounded yet.
3. **D3 — Interim containment:** protect the customer now. Quarantine
   suspect stock (on-hand, WIP, in-transit, at customer), 100% inspect,
   mark certified stock. Verify containment actually catches the defect.
4. **D4 — Root cause:** see methods below. Identify both the *occurrence*
   root cause (why it happened) and the *escape* root cause (why detection
   missed it). Both must be answered or the 8D is incomplete.
5. **D5 — Choose permanent corrective action:** prove it removes the root
   cause (trial run, simulation, capability study) before deploying.
6. **D6 — Implement & validate:** deploy, then verify with data over time
   (e.g. 30 days of SPC without signal). Remove containment only after.
7. **D7 — Prevent recurrence:** update FMEA, control plan, work
   instructions, PM tasks; read across to similar parts/lines/suppliers.
8. **D8 — Recognize the team and close** with evidence attached.

## D4 method 1 — Fishbone (Ishikawa) categories (6M)
- **Machine:** wear, calibration, PM overdue, fixturing, parameter drift.
- **Method:** work instruction wrong/ambiguous, sequence, setup procedure.
- **Material:** lot variation, supplier change, storage/handling, expiry.
- **Man (people):** training, handoffs, fatigue, unofficial workarounds.
- **Measurement:** gauge R&R, wrong instrument, sampling plan, rounding.
- **Mother nature (environment):** temperature, humidity, vibration, dust.
Brainstorm causes per bone, then vote/test the top candidates with data.

## D4 method 2 — 5-Why guidance
- Ask "why" from the defect toward the *system*, not toward a person.
  Stopping at "operator error" is a sign you stopped too early — ask why the
  process allowed or didn't catch the error.
- Each "why" must be verified (evidence, test, record) before the next.
- Branch when answers fork; track occurrence and escape legs separately.
- You're at root cause when fixing it plausibly prevents *all* recurrence,
  and when the next "why" would leave your control (e.g. "gravity exists").

## Quality bar
A finished RCA names: verified occurrence cause, verified escape cause,
corrective action with owner and date, validation evidence, and read-across
scope. Reject "retrained operator" as a sole corrective action.
