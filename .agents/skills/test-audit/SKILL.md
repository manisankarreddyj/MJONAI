---
name: test-audit
description: Find low-value tests that cost more than they protect — assertion-free probes, tautologies, duplicates, tests pinned to a dead/buggy contract, or coverage of deleted code. Use to prune a bloated suite or before/after a big cleanup. Report-only; deletions go through review + a green full suite.
---

# MJONAI /test-audit — a test must protect behavior, not just exist

A 900-test suite is only an asset if most tests can fail. After the dead-code purge this is the
next hygienic pass. Report-only; any deletion is a reviewed manifest, then a green full run.

## What to flag (each with an evidence card: `test_file:line`)

- **No-assertion probes** — a test that calls code but asserts nothing (or only `assert x is not None`).
- **Tautologies / always-true** — asserts on a constant the test itself set; mocks that make the
  assertion trivially true; `assert True`.
- **Coverage-of-nothing** — asserts on `to_dict()` keys alone, dataclass serialization with no behavior.
- **Wrong-contract pins** — tests that pinned a *buggy* behavior (e.g. the old K1 `reason=` kwarg, the
  pre-fix flat-2% trail, the removed `cb:close`, deleted-module imports). These must be **updated**, not kept.
- **Dead-code tests** — imports of modules that no longer exist, or tests of a symbol with zero
  production callers. Should be deleted with the module.
- **Duplicates / mergeable** — same behavior asserted in N files; consolidate.

## Method
1. `git grep -n "def test_" -- tests tests/research` + per-file grep for `assert` density.
2. Cross-check every imported test subject still exists + has a production consumer
   (`git grep -l <symbol> -- mjonai apps`) — orphan imports are deletion candidates.
3. Mutation-check the valuable survivors: would this test fail if the behavior regressed? If not, it's a probe.
4. Consult the documented flakes before touching them: `test_module12::test_concurrent_split_brain_race_condition`,
   `test_debate_room::test_conduct_adversarial_debate_unanimous_approval`.

## Deliverable
An evidence-card table (delete / update / keep) → owner approval → delete (with `git rm`) → full
non-network suite + research suite green → commit `test: ...`. Confirm the count dips by exactly
the number removed; a clean run is a regression if the count didn't move as predicted.
