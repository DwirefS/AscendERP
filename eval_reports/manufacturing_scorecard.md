# Manufacturing Evidence Engine Scorecard

## Summary

| Report | Tasks | Mean score | Pass rate | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|
| spc_golden_tasks | 11 | 1.0000 | 100.00% | 0.2 | 0.3 |
| reorder_golden_tasks | 8 | 1.0000 | 100.00% | 0.1 | 0.1 |
| maintenance_golden_tasks | 8 | 1.0000 | 100.00% | 0.1 | 0.3 |

## spc_golden_tasks

Ran 11 tasks, 2026-07-04T07:52:13.635057 -> 2026-07-04T07:52:13.637313.

| Task | Score | Latency ms | Error |
|---|---:|---:|---|
| spc_cpk_capable | 1.000 | 0.1 |  |
| spc_cpk_incapable | 1.000 | 0.1 |  |
| spc_cpk_marginal | 1.000 | 0.2 |  |
| spc_drift | 1.000 | 0.2 |  |
| spc_in_control_gaussian | 1.000 | 0.3 |  |
| spc_rule1_spike | 1.000 | 0.3 |  |
| spc_rule2_two_of_three | 1.000 | 0.2 |  |
| spc_rule3_four_of_five | 1.000 | 0.1 |  |
| spc_rule4_sustained_shift | 1.000 | 0.2 |  |
| spc_sigma_zero_constant | 1.000 | 0.1 |  |
| spc_supplier_material_return | 1.000 | 0.2 |  |

## reorder_golden_tasks

Ran 8 tasks, 2026-07-04T07:52:13.637362 -> 2026-07-04T07:52:13.638313.

| Task | Score | Latency ms | Error |
|---|---:|---:|---|
| reorder_above_point_no_po | 1.000 | 0.1 |  |
| reorder_big_po_pending_approval | 1.000 | 0.1 |  |
| reorder_breach_single_supplier | 1.000 | 0.1 |  |
| reorder_demand_driven_breach | 1.000 | 0.1 |  |
| reorder_dominant_supplier_wins | 1.000 | 0.1 |  |
| reorder_excluded_supplier_fallback | 1.000 | 0.1 |  |
| reorder_just_below_threshold_auto | 1.000 | 0.1 |  |
| reorder_unsourced_material | 1.000 | 0.1 |  |

## maintenance_golden_tasks

Ran 8 tasks, 2026-07-04T07:52:13.638351 -> 2026-07-04T07:52:13.639419.

| Task | Score | Latency ms | Error |
|---|---:|---:|---|
| pm_combined_wear_and_vibration | 1.000 | 0.3 |  |
| pm_exact_threshold_triggers | 1.000 | 0.1 |  |
| pm_high_runtime_triggers | 1.000 | 0.1 |  |
| pm_low_risk_no_order | 1.000 | 0.1 |  |
| pm_risk_clamped_at_one | 1.000 | 0.1 |  |
| pm_risk_ordering_across_fleet | 1.000 | 0.1 |  |
| pm_telemetry_override | 1.000 | 0.1 |  |
| pm_vibration_alone_insufficient | 1.000 | 0.1 |  |

## Experiment: Solo QualityAgent vs QualityCouncil (NCR disposition)

## Summary

| Report | Tasks | Mean score | Pass rate | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|
| quality_agent_solo | 12 | 1.0000 | 100.00% | 0.0 | 0.0 |
| quality_council | 12 | 1.0000 | 100.00% | 0.5 | 0.9 |

## quality_agent_solo

Ran 12 tasks, 2026-07-04T07:52:13.639579 -> 2026-07-04T07:52:13.639656.

| Task | Score | Latency ms | Error |
|---|---:|---:|---|
| d01_minor_control_signal_only | 1.000 | 0.0 |  |
| d02_minor_few_defects | 1.000 | 0.0 |  |
| d03_minor_many_defects | 1.000 | 0.0 |  |
| d04_major_economical_rework | 1.000 | 0.0 |  |
| d05_major_cheap_rework | 1.000 | 0.0 |  |
| d06_major_uneconomical_rework | 1.000 | 0.0 |  |
| d07_critical_small_lot | 1.000 | 0.0 |  |
| d08_critical_large_lot | 1.000 | 0.0 |  |
| d09_supplier_major | 1.000 | 0.0 |  |
| d10_supplier_critical | 1.000 | 0.0 |  |
| d11_supplier_minor_defects | 1.000 | 0.0 |  |
| d12_major_cheap_vs_valuable | 1.000 | 0.0 |  |

## quality_council

Ran 12 tasks, 2026-07-04T07:52:13.639701 -> 2026-07-04T07:52:13.646671.

| Task | Score | Latency ms | Error |
|---|---:|---:|---|
| d01_minor_control_signal_only | 1.000 | 0.9 |  |
| d02_minor_few_defects | 1.000 | 0.7 |  |
| d03_minor_many_defects | 1.000 | 0.5 |  |
| d04_major_economical_rework | 1.000 | 0.6 |  |
| d05_major_cheap_rework | 1.000 | 0.5 |  |
| d06_major_uneconomical_rework | 1.000 | 0.6 |  |
| d07_critical_small_lot | 1.000 | 0.6 |  |
| d08_critical_large_lot | 1.000 | 0.5 |  |
| d09_supplier_major | 1.000 | 0.6 |  |
| d10_supplier_critical | 1.000 | 0.5 |  |
| d11_supplier_minor_defects | 1.000 | 0.5 |  |
| d12_major_cheap_vs_valuable | 1.000 | 0.4 |  |

## Comparison

Best mean score: **quality_agent_solo**

| Task | quality_agent_solo | quality_council |
|---|---:|---:|
| d01_minor_control_signal_only | 1.000 | 1.000 |
| d02_minor_few_defects | 1.000 | 1.000 |
| d03_minor_many_defects | 1.000 | 1.000 |
| d04_major_economical_rework | 1.000 | 1.000 |
| d05_major_cheap_rework | 1.000 | 1.000 |
| d06_major_uneconomical_rework | 1.000 | 1.000 |
| d07_critical_small_lot | 1.000 | 1.000 |
| d08_critical_large_lot | 1.000 | 1.000 |
| d09_supplier_major | 1.000 | 1.000 |
| d10_supplier_critical | 1.000 | 1.000 |
| d11_supplier_minor_defects | 1.000 | 1.000 |
| d12_major_cheap_vs_valuable | 1.000 | 1.000 |

## Experiment: Dispatch Policy Eval

## Summary

| Report | Tasks | Mean score | Pass rate | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|
| dispatch_policy_eval | 5 | 0.8150 | 100.00% | 2.4 | 2.9 |

## dispatch_policy_eval

Ran 5 tasks, 2026-07-04T07:52:13.647524 -> 2026-07-04T07:52:13.659956.

| Task | Score | Latency ms | Error |
|---|---:|---:|---|
| dispatch_cr | 0.822 | 2.5 |  |
| dispatch_edd | 0.824 | 2.9 |  |
| dispatch_fifo | 0.824 | 2.3 |  |
| dispatch_spt | 0.802 | 2.4 |  |
| dispatch_wspt | 0.803 | 2.3 |  |

## Dispatch Rule Ranking (168h, 3 replications, seed 42)

Objective = 0.5*otd_rate + 0.3*oee - 0.2*total_cost/cost_baseline (AutoOptimizeLoop weights).

| Rank | Rule | Objective | OTD | OEE | Scrap | Throughput | Total cost | Makespan h |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | FIFO | 0.6475 | 1.000 | 0.934 | 0.0180 | 747.6 | 81,394 | 39.3 |
| 2 | EDD | 0.6472 | 1.000 | 0.933 | 0.0182 | 747.0 | 81,461 | 40.1 |
| 3 | CR | 0.6446 | 1.000 | 0.925 | 0.0185 | 746.6 | 81,529 | 38.9 |
| 4 | WSPT | 0.6067 | 0.917 | 0.936 | 0.0167 | 750.3 | 81,197 | 41.8 |
| 5 | SPT | 0.6044 | 0.917 | 0.931 | 0.0181 | 747.3 | 81,721 | 45.0 |
