---
name: refactor
description: Refactoring conductor (refactor pack). Detects bloated files and splits them behavior-preservingly, gated by a deterministic before/after equivalence check (tests identical + api surface unchanged + golden outputs byte-identical). Any divergence reverts the refactor. Use for /maw refactor <path>, or when asked to split/clean up an over-large module.
---

# /maw refactor — the refactoring conductor

You split bloated files into cohesive modules **without changing behavior**, and
you *prove* it. The bar is not "looks cleaner" — it is the **behavior-equivalence
gate**: against the pre-refactor snapshot, **tests pass identically, the public API
surface is unchanged, AND golden outputs are byte-identical**. Any difference → the
refactor is reverted. Read `CLAUDE.md` first.

If `python` is not on PATH, use `uv run python` for the `maw-tools/` commands. The
tools are pure stdlib (`ast`, `inspect`).

## The team

| Role | Tool (`refactor_checks.py …`) | Owns |
|---|---|---|
| `refactor_scout` (haiku) | `bloat` | the trigger: rank offenders, propose cohesive split boundaries (group by shared symbols) |
| `refactorer` | `api` + `golden` (+ `code_checks test`) | perform the split, preserve the public API, run the equivalence gate |
| `code_reviewer` / `acceptance_gate` | re-run the gate | **independent** equivalence verification before SHIP |

## The behavior-equivalence gate (hard NO-SHIP rules)

```
A refactor may SHIP only if, vs the PRE-refactor snapshot, ALL hold:
  [ ] tests:  the existing suite passes identically (code_checks test, exit 0)
  [ ] api:    public API surface unchanged (refactor_checks api --baseline, exit 0)
  [ ] golden: harness outputs byte-identical (refactor_checks golden --compare, exit 0)
ANY difference  ->  REVERT the refactor entirely and report what diverged. NO-SHIP.
```

`golden` is the behavioral truth: it can catch a regression that the tests miss and
that the API surface (signatures unchanged) cannot see. `api` catches dropped/renamed
exports and changed signatures. Both are required; neither alone is sufficient.

## Procedure

1. **Scout (trigger + plan).** `refactor_scout` runs `bloat` on the target path,
   ranks offenders worst-first, and writes `artifacts/split_plan.md` — the proposed
   modules and which public names + private helpers move into each (grouped by shared
   symbols; genuinely-shared symbols stay in a `_common` module). If nothing is over
   budget, stop — there is no refactor to do.
2. **Scaffold the run folder** (`scaffold_run.py init … --agents
   conductor,refactor_scout,refactorer,code_reviewer,acceptance_gate`). The plan gate
   (`plan_check`) applies as usual.
3. **Snapshot BEFORE (the refactorer, before any edit):**
   ```bash
   uv run python maw-tools/refactor_checks.py api    --module <mod> --src-dir <dir> > artifacts/api_before.json
   uv run python maw-tools/refactor_checks.py golden --harness <harness.py> --src-dir <dir> --snapshot artifacts/golden_before.json
   uv run python maw-tools/code_checks.py     test   --cmd "<test cmd>" --cwd <dir>
   ```
4. **Split.** `refactorer` creates the cohesive modules, moves each cluster, makes the
   original module a re-export package/shim with an **identical `__all__`**, fixes imports.
5. **Equivalence gate.** Re-run tests + `api --baseline` + `golden --compare`. **All
   three green → proceed; any red → `git checkout`/restore the original and STOP** with
   a report of the divergence.
6. **Independent verification.** `code_reviewer` / `acceptance_gate` (a different agent)
   **re-runs the three checks themselves** against the on-disk tree — it does not trust
   the refactorer's report. SHIP only on genuine, reproduced equivalence.
7. **Report**: the new layout, the bloat before/after, and the equivalence evidence.

## Principles
- **Compute first, reason second** — equivalence is the tools' exit codes, not a vibe.
- **Behavior first** — a cleaner structure that changes any output is a FAILED refactor.
- **Everything in markdown on disk** — the run is reconstructable from its folder.
- See the worked demo: `examples/refactor_demo/` (bloated → split SHIP; bad split NO-SHIP)
  and its committed run folder.

> **# MAW-TODO** — `branch_count` approximates cyclomatic complexity (it counts
> branch-ish AST nodes), not the exact McCabe number; and split-boundary cohesion is
> shared-symbol grouping, not full call-graph community detection. Deeper metrics are
> not built. The equivalence gate (tests + api + golden) is the hard, real guarantee.
