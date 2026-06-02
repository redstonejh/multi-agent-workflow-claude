---
name: frontend
description: Front-end / UI conductor (front-end pack). Like /maw, but the refine loop pulls in the front-end auditors (a11y_auditor, responsive_checker, perf_budgeter, markup_validator) backed by maw-tools/web_checks.py and scores against the hard-gate front-end rubric (a11y/contrast/links/markup/budget/responsive must all pass) instead of a vibe score; ux_critic is advisory only and the acceptance gate re-runs the deterministic checks against the on-disk files before SHIP. Use for building/iterating a static UI, or when the user runs /frontend <task>.
---

# /frontend — the front-end conductor

You are running the Multi-Agent Workflow conductor specialized for front-end /
UI work. A generic "looks good to me" critic is exactly what ships inaccessible,
broken, bloated pages, so for the front-end the quality bar is **"passes the
deterministic gates,"** not "the critic likes it." Read `CLAUDE.md` first.

If `python` is not on PATH, use `uv run python` for every `maw-tools/` command
(this machine is one such case). The pack is **pure stdlib** (`html.parser`, `re`)
— no browser, no npm.

## What changes vs. plain /maw

- The team draws from the **front-end roster**, each backed by a deterministic
  `maw-tools/web_checks.py` subcommand:

  | Agent | Tool (`web_checks.py …`) | Gate it owns |
  |---|---|---|
  | `ui_builder` | (writes the page) | produces/revises HTML/CSS/JS |
  | `a11y_auditor` | `a11y` + `contrast` | accessibility + WCAG contrast |
  | `responsive_checker` | `responsive` | viewport meta + `@media` presence |
  | `perf_budgeter` | `budget` | page-weight + element/request budget |
  | `markup_validator` | `markup` + `links` | well-formedness + internal links |
  | `change_verifier` | `changed` + `style` | the requested change is provably applied |
  | `style_drift_auditor` | `tokens` | no off-palette / off-token style drift |
  | `ux_critic` | (rubric) | **advisory only** — not a hard gate |
  | `visual_verifier` | (Chrome, if available) | **advisory only** — pixel diff is # MAW-TODO |

  **Conservative by default:** start with the gates the task needs (almost always
  `a11y_auditor` + `markup_validator`) and add the others as warranted. The roster
  exceeds `max_agents` 5, so **run the auditors in sequence over the shared
  on-disk files** (not as concurrent roles); justify each in `run.md`.
- The evaluator scores against the **hard-gate rubric** below — a checklist, not a
  number. Any failed gate ⇒ FAIL with a specific, named critique.
- Each auditor **runs its `web_checks.py` tool first** and only interprets.
- The **acceptance gate re-runs the checks against the on-disk files** as its
  end-to-end step and only SHIPs on genuine, reproduced passes.

## The hard-gate front-end rubric (the refine loop enforces this)

```
PASS requires ALL applicable gates (each = the named web_checks.py subcommand exit 0):
  [ ] contrast:   every text/background pair >= 4.5 (AA normal) / 3.0 (large)
  [ ] a11y:       0 violations — img-alt, control-label, heading-skip, lang, title
  [ ] links:      every internal link/anchor/asset resolves
  [ ] markup:     no unclosed/mismatched tags, no duplicate ids
  [ ] budget:     total bytes / elements / requests within budget
  [ ] responsive: viewport meta present AND >= 1 @media query (PRESENCE only)
  [ ] change:     IF a specific change was requested — it is demonstrably applied
                  in the source (changed exit 0: changed AND matches the expected
                  value; a no-op or wrong-target edit FAILS)
  [ ] drift:      IF a design-tokens.json exists — no off-palette/off-token value
                  was introduced (tokens exit 0)

ADVISORY (NOT gates): ux_critic's usability/aesthetic read; visual_verifier's
before/after screenshot comparison (model judgment — full screenshot-diff is # MAW-TODO).
SCORE/ship ONLY if every applicable hard gate passes; otherwise FAIL + the named
critique (which gate, which number, which element).
```

When a UI **change** was requested, the bar is explicit: a run may only SHIP if the
requested change is **demonstrably present in the source** (`change_verifier`) AND
**no token drift was introduced** (`style_drift_auditor`). "I edited it" is not
evidence; the `changed` gate's exit code is.

Mark a gate **N/A** honestly when it genuinely doesn't apply (e.g. `responsive`
for an intentionally fixed-width email template) rather than fabricating a pass.

> **# MAW-TODO — the visual layer.** These gates are source-level and computed.
> "Does the page actually render and look correct in a real browser" (visual /
> pixel-regression) needs the Chrome connector or a headless-browser dep and is
> **not built**. `ux_critic` is advisory; never claim the rendered pixels were
> checked. The deterministic source gates are the hard bar.

## Procedure

1. **Assess & plan the team** (conductor logic, `.claude/agents/conductor.md`).
   State the real objective (the UI and who uses it), not just "make a page".
   Default shape: `planner → ui_builder → [a11y_auditor, markup_validator,
   perf_budgeter, responsive_checker]` in a refine loop → `acceptance_gate`,
   adding/removing auditors as the task warrants. Stay within governor caps
   (max_agents 5 — run auditors in sequence over the shared files). Justify each
   role in one line in `run.md`.
   **When a specific UI change was requested** (e.g. "make the button blue and
   larger"), add `change_verifier` and (if a `design-tokens.json` exists)
   `style_drift_auditor`. The `change_verifier` must **snapshot the BEFORE value
   first — before `ui_builder` edits** — so the change is provable; then it asserts
   the edit landed. `visual_verifier` is optional + advisory.
2. **Scaffold the run folder:**
   ```bash
   uv run python maw-tools/scaffold_run.py init "<task>" \
       --agents conductor,planner,ui_builder,a11y_auditor,markup_validator,perf_budgeter,responsive_checker,ux_critic,acceptance_gate --json
   ```
   Write the plan + the rubric you'll enforce into `run.md`'s "Conductor plan".
3. **Delegate with hand-offs** (scaffold `handoff` helper at every boundary):
   planner → ui_builder (writes `index.html`/`style.css`) → each auditor runs its
   tool and writes its `*_report.md` + a `memory.md` finding.
4. **Refine loop against the rubric.** The auditors collectively return PASS only
   if every applicable hard gate passes. On FAIL the critique is a hand-off back to
   `ui_builder` naming the gate + number + element; the builder fixes and the
   auditors re-run. `ux_critic` contributes advisory notes, never a block/ship.
   Stop on PASS, `max_iters`, or plateau.
5. **Acceptance gate (independent, terminal, once).** Delegate to
   `acceptance_gate`. It **re-runs every `web_checks.py` subcommand against the
   files on disk** (it does not trust the auditors' say-so) and confirms the final
   report claims nothing the numbers don't support. When a change was requested it
   **independently re-runs `changed` (against the recorded before-value) and
   `tokens`**, and only SHIPs if the requested change is demonstrably present AND no
   drift was introduced. SHIP only on genuine passes.
6. **Report**: result, run-folder path, which gates passed (with numbers), the
   gate verdict. Only state what the run folder's recorded numbers support; keep
   visual/aesthetic claims explicitly advisory.

## Principles
- **Compute first, reason second** — the verdicts come from `web_checks.py`, the
  agents interpret. A check's exit code is the gate.
- **Conservative team, escalate on failure.** Cheap models (haiku) for the
  auditors; the conductor and the independent gate stay stronger.
- **Everything in markdown on disk** — the run is reconstructable from its folder.
- See the worked demo: `examples/frontend_demo/` and its committed run folder
  `runs/2026-06-02_frontend-demo_c53d/`.
