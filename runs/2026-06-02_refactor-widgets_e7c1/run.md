# Run 2026-06-02_refactor-widgets_e7c1

- **Task:** split the bloated `widgets.py` into cohesive modules — behavior-preservingly,
  proven by a before/after equivalence gate (refactor pack demo).
- **Created:** 2026-06-02 11:02
- **Status:** complete — SHIP (good split); bad-split fixture demonstrably NO-SHIP

## Conductor plan

Refactoring run. The bar is **behavior equivalence**, not "looks cleaner": a split
may SHIP only if, vs the pre-refactor snapshot, **tests pass identically AND the
public API surface is unchanged AND golden outputs are byte-identical**. Any
difference → revert.

| Role | Why (one line) |
|---|---|
| `refactor_scout` | run `bloat`, rank offenders, propose split boundaries by shared symbols |
| `refactorer` | snapshot before, perform the split, preserve the public API, run the gate |
| `code_reviewer` / `acceptance_gate` | independently re-run the equivalence gate before SHIP |

## Trigger (refactor_scout)

`bloat bloated/widgets.py --max-loc 80 --max-defs 5` → **exit 1**: loc 110 (>80),
defs 9 (>5). The eight public functions form four shared-symbol clusters →
`text` (slugify/shout share `_normalize_ws`), `mathx` (lcm uses gcd), `listx`,
`money` (share `CENTS_PER_DOLLAR`). After the split, `bloat` on the package is
**exit 0** (every module under budget). Full output: `artifacts/trigger.md`.

## Behavior-equivalence gate

Before-snapshots captured first: `artifacts/api_before.json`, `artifacts/golden_before.json`.

**Good split (`split/`) → SHIP** (`artifacts/equivalence_good.md`):

| gate | result |
|---|---|
| tests | `test_widgets.py` exit 0 — pass identically |
| api | surface vs `api_before.json` — **identical** (added/removed/changed all empty) |
| golden | 11 cases vs `golden_before.json` — **byte-identical** |

**Bad split (`bad_split/`) → NO-SHIP + revert** (`artifacts/equivalence_bad.md`):
`money.format_cents` silently dropped its cents zero-pad.

| gate | result |
|---|---|
| tests | exit 0 — **still pass** (they don't assert sub-dollar amounts) |
| api | **identical** — signatures unchanged, so `api` can't see it |
| golden | **DIFFERS** — `format_cents_neg`: `-$0.07` → `-$0.7` → **exit 1, NO-SHIP** |

This is the point of the pack: `golden` is the behavioral truth — it catches a
regression that both the test suite **and** the API surface miss. Per the hard
rule, the bad split is reverted entirely.

## Final result summary

The good split ships: bloat cleared, and tests + api + golden all identical to the
pre-refactor snapshot — verified independently. The bad-split fixture is caught by
golden and reverted. The before/after numbers and the RED/GREEN verdicts are pinned
in `maw-tools/selftest_all.py` (§8), so this write-up cannot drift from the tools.

> **# MAW-TODO** — `branch_count` approximates cyclomatic complexity; split cohesion
> is shared-symbol grouping, not full call-graph community detection. The equivalence
> gate (tests + api + golden) is the real, hard guarantee.
