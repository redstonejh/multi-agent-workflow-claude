# Run 2026-06-02_frontend-demo_c53d

- **Task:** build an accessible Acme signup page; prove the front-end gates catch
  real defects and clear once fixed (front-end pack demo).
- **Created:** 2026-06-02 10:10
- **Status:** complete — SHIP

## Conductor plan

Front-end pack run (sibling of the ML pack docs/06 and code pack docs/07). The
quality bar is **"passes the deterministic gates,"** not "the critic likes it."
Aesthetic judgment is advisory; the hard PASS/FAIL gates are `web_checks.py`.

Team (governor cap max_agents 5 — the auditors run **in sequence over the shared
on-disk files**, like the ML validators, so the roster fits):

| Role | Why (one line) |
|---|---|
| `planner` | decompose the page + the gate checklist |
| `ui_builder` | write index.html + style.css |
| `a11y_auditor` | owns `a11y` + `contrast` gates |
| `responsive_checker` | owns `responsive` (viewport + @media) gate |
| `perf_budgeter` | owns `budget` gate |
| `markup_validator` | owns `markup` + `links` gates |
| `ux_critic` | advisory rubric (NOT a hard gate) |
| `acceptance_gate` | independent terminal re-run of every check on disk |

### The hard-gate rubric (refine loop enforces this)
```
PASS requires ALL of (each = the named web_checks.py subcommand, exit 0):
  [ ] contrast:   every text/bg pair >= 4.5 (AA normal) / 3.0 (large)
  [ ] a11y:       0 violations (img-alt, control-label, heading-skip, lang, title)
  [ ] links:      every internal link/anchor/asset resolves
  [ ] markup:     no unclosed/mismatched tags, no duplicate ids
  [ ] budget:     total bytes / elements / requests within budget
  [ ] responsive: viewport meta present AND >= 1 @media query
ADVISORY (not a gate): ux_critic aesthetic read; true visual-regression is # MAW-TODO.
```

## Final result summary

The planted page started with **six** deterministically-caught defects; the
refine loop fixed each and the auditors re-ran green. Raw tool output for both
states is in `artifacts/audit_before.md` and `artifacts/audit_after.md`.

| Gate | BEFORE (defect) | AFTER (fixed) |
|---|---|---|
| contrast (button) | `#9aa0a6` on `#fff` = **2.64:1** -> FAIL | `#fff` on `#1558b0` = **6.87:1** -> PASS |
| a11y | **3** violations (img-alt, control-label, heading-skip) -> FAIL | **0** -> PASS |
| links | broken `#main` anchor -> FAIL | all resolve -> PASS |
| responsive | no `<meta viewport>` -> FAIL | viewport + `@media` -> PASS |
| budget (3000 B) | **4742 B** (inline blob) -> FAIL | **1838 B** -> PASS |
| markup | well-formed (not a planted defect) -> PASS | well-formed -> PASS |

- **Component critic (ux_critic):** advisory PASS — layout reads cleanly; noted
  that "does it *look* good" is model judgment, not a computed gate.
- **Acceptance gate:** re-ran all six `web_checks.py` subcommands against the
  on-disk files. Every gate exit 0 on the fixed page; every gate fired on the
  defective snapshot. Verdict: **SHIP**.
- The numbers above are pinned in `maw-tools/selftest_all.py` (§5) and proven by
  `maw-tools/selftest_web_checks.py`, so this write-up cannot silently drift.

> **# MAW-TODO** — visual / pixel-level regression ("does it render correctly in
> a real browser") needs the Chrome connector or a headless-browser dep and is
> out of scope for the deterministic, stdlib-only pack. The source-level gates
> above are the hard gates.
