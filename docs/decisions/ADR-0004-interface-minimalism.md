# ADR-0004: Interface minimalism — four ports, no speculative ABCs

**Status:** ACCEPTED (owner-delegated 2026-08-24) — **PARTIALLY EXECUTED**: MarketData port exists (`research/data/base_provider.py`); LLMProvider thin wrap pending; Broker port deferred by design

## Context
Blueprint §47 lists ~19 interfaces (MarketDataProvider … ModelRegistry). For a solo-operated system each ABC is a permanent abstraction tax. Audit shows existing code already isolates most concerns via module boundaries (repository façade, provider classes in research/data/, llm_bridge vendor dispatch).

## Decision
Create/maintain ONLY ports where a second implementation is concrete or imminent:
- `MarketData` — formalize existing base_provider.py; second impl: dhanhq (planned).
- `ForecastModel` — new; second impl guaranteed by design (baselines + 3 TSFMs).
- `LLMProvider` — thin wrap of llm_bridge dispatch table; second impl = any OpenAI-compatible endpoint (exists today as fallback path).
- `Broker` — deferred until live-ladder work starts; paper path is the first implementation.

Everything else stays function/module-level. Registry pattern already covers strategy replaceability without an ABC.

## Consequences
Some future refactor cost if portfolio optimization arrives (then add PortfolioOptimizer port at that moment, not before). Benefit: zero speculative indirection; grep-ability preserved.
