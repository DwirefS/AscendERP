# docs/essays — Labeled Speculation

This directory is the home for the **essay tier** of the corpus, established
by decision [D-021](../decisions/DECISION_LOG.md) ("the carve"): ideas sorted
into verdict tiers, **nothing deleted**.

## What belongs here

Writing where the author is *thinking in public* — personal metaphysics,
long-horizon speculation, and reflections that are valuable as vision but are
**not part of the engineering claims path**:

- The fractal-semantic-space / "gravitational coherence" theory of LLMs
- Consciousness and singularity reflections
- Any future piece that explores rather than asserts

Per the audit ([`docs/plans/PHILOSOPHY_TO_REALITY.md`](../plans/PHILOSOPHY_TO_REALITY.md)
§3.6), content in this tier is **labeled speculation**: it makes no
implementation claims, cites no fabricated metrics, and is never referenced
as evidence by the README, the decision log, or the eval reports.

## Where the essays currently live

The essay-tier material is still embedded in the whitepaper files
(`ASCEND_EOS_WHITEPAPER_FINAL.md`, `docs/whitepaper_addition.md` Edition 3
sections, `WHITEPAPER_3_COLLECTIVE_INTELLIGENCE.md`). **Moving those sections
out of the whitepapers is the author's call** — this directory only
establishes the destination and the label. When sections migrate here, they
keep their full text (no-deletions doctrine) and gain a one-line header:

> *Essay — labeled speculation per D-021. Not an engineering claim.*

## What does NOT belong here

- Anything measured (that goes to `eval_reports/`)
- Architecture decisions (those go to `docs/decisions/DECISION_LOG.md`)
- Implementation plans (those go to `docs/plans/`)
- Safety-engineering content buried inside essays (e.g. the kill-switch /
  constrained-optimization list) — extract that into the WS-2 security docs.
