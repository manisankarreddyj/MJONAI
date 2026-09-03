# ADR-0001: No re-platforming; repair waves precede new capability

**Status:** PROPOSED (2026-08-24) · **Supersedes:** GPT blueprint §66 candidate stack as an implementation plan

## Context
The blueprint proposed adopting OpenBB/Qlib/VectorBT/Nautilus/MLflow/LangGraph etc. Audit showed a working, recently-stabilized system whose research instrument was methodologically repaired and regression-locked on 2026-08-22/23. Swapping infrastructure now would invalidate baselines and re-open settled defects.

## Decision
Evolve in place. Execute repair waves G1→G6 before adding capability (forecasting, experiments). External tech adopted only where a genuine gap exists (see TECHNOLOGY_RADAR.md).

## Alternatives rejected
- Big-bang migration to blueprint stack — destroys validated instrument + momentum of defect-repair program.
- Parallel new engine built alongside — violates one-source-of-truth anti-drift rules.

## Consequences
Short-term: fewer visible "modernization" wins. Long-term: compounding validity — every result stays traceable to the same measurement instrument.
