# Multi-Agent Workflow

**A framework for turning a single Claude assistant into a coordinated team of specialized agents — with built-in quality loops, independent verification, and shared memory — for tackling complex tasks like ML experiments, debugging, and research.**

Instead of one model doing one pass, a *conductor* reads your task, assembles the right team of specialist agents (planner, workers, critics, validators), and runs them through a pipeline where they hand work off to each other, check each other, and iterate until the result actually holds up. It's designed to run on Claude Code with no per-token API cost.

> **Status:** Architecture & design complete (see [`docs/`](docs/)), and a **working
> minimal version now runs** — Phases 1–3 of [`docs/08-build-strategy.md`](docs/08-build-strategy.md).
> A small roster of subagents, the `/maw` conductor skill, and deterministic helper
> tools are implemented and tested end to end (see the [worked example](examples/README.md)).
> **The full ML validation pack (Phase 3.7) now works too** — all **nine validator
> agents** and their deterministic `ml_checks.py` checks (leakage, overfitting,
> baseline, metrics, calibration, variance, reproducibility, data-quality,
> robustness), an `/ml-experiment` skill that gates a run on all nine, and a
> committed worked example where a planted data leak is caught (NO-SHIP) and fixed
> (SHIP). **The code-work pack (Phase 3.8) now works too** — seven roster agents,
> the `code_checks.py` AST tools (`refs` blast-radius, `syntax`, `test`, `dupes`),
> the inline `# MAW-DEP` + central `deps.md` hidden-dependency annotator and the
> bug/RCA documentation system, with a committed coupling demo (a hidden precondition
> + planted bug reproduced, traced, fixed, and annotated). **A front-end / UI pack
> now works too** — nine computed gates (`web_checks.py`: contrast, a11y, budget,
> links, markup, responsive, plus `style`/`changed`/`tokens` to **prove a requested
> change was actually applied with no style drift**), eight roster agents, a
> `/frontend` skill, and committed demos (six planted defects each caught then fixed;
> a "make the button blue #1a73e8" change proven applied, with no-op + drift fixtures
> caught as NO-SHIP). Every check is
> self-tested green-on-good / red-on-bad and the whole thing is pinned by a
> self-validation harness (`selftest_all.py`, **PASS 74/74** — raw output in
> [`selftest_output.txt`](selftest_output.txt)). A few deeper pieces (CV-fold
> stability, the full robustness perturbation suite, the dependency-DAG scheduler,
> front-end visual/pixel regression) remain design-only. See [What works today](#what-works-today-vs-whats-still-design).

---

## The problem it solves

A single LLM pass is fast but fragile: no second opinion, no check on whether the output is actually correct, and for technical work (ML especially) the most impressive-looking results are often the most misleading. This framework makes **multi-agent coordination and self-verification the default**, so that:

- work is **decomposed** across specialists instead of crammed into one prompt,
- output is **critiqued and revised in a loop** until it meets an explicit quality bar,
- results are **independently verified** before they're accepted,
- and the whole run is **self-documenting** — every agent's reasoning and hand-off is written to disk as readable markdown.

## How it works

```
your task
   │
   ▼
┌─────────────┐   reads a roster of available specialist roles, then
│  CONDUCTOR  │   plans the team: which roles, how many, which pattern,
└─────────────┘   with what quality bar — staying within safety caps
   │
   ▼
┌──────────────────────────────────────────────┐
│  the team executes (orchestrate / pipeline /   │
│  parallel / route), passing markdown hand-off  │
│  notes between agents and sharing a journal     │
└──────────────────────────────────────────────┘
   │
   ▼
┌─────────────┐   generate → evaluate → revise, looping until the
│ QUALITY LOOP│   output clears the bar (the "refine" pattern)
└─────────────┘
   │
   ▼
┌─────────────┐   an INDEPENDENT agent (not the one that did the work)
│ ACCEPTANCE  │   checks: did we answer the real ask? does every claim
│    GATE     │   trace to evidence? does it run end-to-end?  SHIP / NO-SHIP
└─────────────┘
   │
   ▼
result + a readable run folder documenting how it got there
```

## Key features

- **Conductor (dynamic team assembly).** Given a task, it intelligently selects which specialist agents are actually needed and how many — conservative by default, escalating only when quality checks fail, all within hard caps on agent count and cost.
- **Composable orchestration patterns.** `pipeline`, `orchestrate` (lead + workers), `parallel` (fan-out + reduce), `route` (classify + specialist), and `debate` — mixed and nested as a task requires.
- **Recursive quality loop (`refine`).** A generate → evaluate → revise loop that wraps *any* pattern and repeats until output meets an explicit, rubric-based bar. This is the core mechanism for compounding quality rather than relying on a single lucky pass.
- **Markdown memory & automatic hand-offs.** Each agent keeps local notes; the team shares a journal; and at every step the framework auto-writes a structured hand-off note and passes it to the next agent — so a multi-agent chain runs from one instruction with no manual prompt-threading. Every run produces a human-readable folder you can open and audit.
- **Independent acceptance gate.** A terminal verification step run by a *different* agent than produced the work, checking task conformance, claim-to-evidence consistency (anti-overclaiming), and end-to-end soundness — with an optional human sign-off for high-stakes runs.
- **Dependency-aware parallelism.** Work runs concurrently only when it's truly independent (scheduled against a dependency graph); discovered hidden couplings feed back so the system stops parallelizing things that secretly conflict.
- **Domain validation packs.** Specialized agents + checks for domains where naive results mislead (below).

## Domain packs

### ML validation
A generic "looks good" critic isn't enough for machine learning — the best-looking metric is often an artifact. This pack ships specialized validators with deterministic, tool-computed checks (not LLM guesswork) for the ways ML results mislead: **overfitting** (train/test gap, learning curves, CV stability), **data leakage** (target/temporal/group leakage, the shuffled-label control), **misleading metrics** (imbalance, wrong metric for the goal), **weak baselines & non-significant gains**, **distribution shift & shortcut learning**, **calibration**, **label quality**, and **reproducibility**. A model only counts as "good" once it survives the audits *and* an independent acceptance gate. See [`docs/06-ml-validation.md`](docs/06-ml-validation.md).

### Code & debugging
A methodology pack for working on real codebases: reproduce-first bug finding, structured bug reports, a hypothesis-driven debugging loop (bisection, delta-debugging), written **root-cause analyses** (not just patches), fix + permanent regression test, a disciplined comment policy (explain *why*, never restate *what*), and — notably — a convention for capturing **hidden dependencies / spaghetti coupling** both inline (a greppable marker right above the line) and in a central, queryable dependency map that also makes parallelization safe. See [`docs/07-code-and-debugging.md`](docs/07-code-and-debugging.md).

### Front-end / UI
"Looks good to me" is exactly what ships inaccessible, broken, bloated pages. This pack makes the front-end bar a set of **deterministic, computed gates** — pure stdlib (`html.parser`, `re`), no browser, no npm — run by specialized auditors: **contrast** (the real WCAG 2.x ratio, pass ≥ 4.5 / 3.0 large), **a11y** (alt-less images, unlabeled controls, skipped heading levels, missing `lang`/`<title>`), **budget** (page bytes + element/request counts), **links** (every internal anchor/asset resolves), **markup** (unclosed tags, duplicate ids), and **responsive** (viewport meta + `@media` presence). It also **proves a requested change was actually applied**: **changed** (a no-op or wrong-target edit fails — "it better actually be changed"), **style** (the exact resolved value of a `selector { property }` for before/after), and **tokens** (scan CSS against a `design-tokens.json` and fail on any off-palette/off-grid value = style drift). A `ux_critic` adds an *advisory* aesthetic read and a `visual_verifier` documents before/after (driving Claude-in-Chrome where available) — both explicitly **not** hard gates. A page (or change) only ships once it clears every deterministic gate *and* an independent acceptance gate re-runs them on the files on disk. True visual/pixel-regression ("does it render right in a browser") needs a real browser and is `# MAW-TODO`. Run it with `/frontend <task>`; see the worked demos in [`examples/frontend_demo/`](examples/frontend_demo/) and [`examples/change_demo/`](examples/change_demo/).

## How you'd use it

The framework installs as a set of agent and workflow definitions in your Claude Code config directory (`~/.claude/`), so it's available in **every** terminal automatically — no per-project setup. Day to day:

```bash
cd your-project          # any folder you want to work in
claude                   # start Claude Code (runs on your subscription)
/maw fix the failing test in payments.py      # the team assembles and goes
```

The agents operate on the files in your current folder, while their definitions live once in `~/.claude/`. Runs on a Claude Pro/Max subscription with no separate API billing. See [`docs/08-build-strategy.md`](docs/08-build-strategy.md) for the full build and install plan.

## Quick start

The working minimal version lives in this repo under [`.claude/`](.claude/) and
[`maw-tools/`](maw-tools/). From inside the repo:

```bash
claude                                  # start Claude Code (on your subscription)
/maw <your task>                        # the conductor assembles the team and runs it
```

For example: `/maw implement normalize_whitespace in examples/sample_app/textutil.py so the tests pass`.
The conductor scaffolds a `runs/<timestamp>_<slug>/` folder, delegates to the
`planner → worker → critic` team through markdown hand-off notes, loops the critic
until the bar is met, and finishes with an **independent `acceptance_gate`**
(SHIP / NO-SHIP). See the [worked example](examples/README.md) for an actual run.

To make `/maw` available from any folder, install the agents and skill under
`~/.claude/` — see [`INSTALL.md`](INSTALL.md).

The deterministic tools run standalone, no model needed:

```bash
python maw-tools/scaffold_run.py init "demo task" --agents planner,worker,critic
python maw-tools/checks.py test --cmd "python test_textutil.py" --cwd examples/sample_app
python maw-tools/checks.py gap --train 0.98 --test 0.81 --tol 0.05
```

## Requirements & running the tests

**Requirements: just Python 3.10+ — no third-party packages.** The tests and the
`maw-tools/` scripts use only the standard library on purpose, so the repo runs
anywhere with nothing to `pip install`. (No `pytest` needed — see the note below.)

If `python` isn't on your PATH (common on Windows, where it resolves to the
Microsoft Store stub), use **`uv run python …`** (uv is lightweight and what this
project assumes) or the **`py …`** launcher. Substitute that for `python` in every
command below.

**Run the worked example's tests directly** (plain stdlib, exits 0 on pass):

```bash
cd examples/sample_app
python test_textutil.py          # -> "PASS — all 6 cases passed", exit 0
# Windows / no python on PATH:  uv run python test_textutil.py
```

**Run them through the framework's test gate** — the same wrapper the `critic` and
`acceptance_gate` use, which reports a machine-readable pass/fail:

```bash
python maw-tools/checks.py test --cmd "python test_textutil.py" --cwd examples/sample_app
# -> {"check": "test", "exit_code": 0, "passed": true, ...}
```

**Self-test the checks themselves** (the tools are verified against known-good and
known-bad fixtures, so a regression in the gate logic turns this red):

```bash
python maw-tools/selftest_checks.py     # -> 4/4 assertions pass
```

**Self-test the ML and code checks** (every check verified green-on-good / red-on-bad):

```bash
uv run python maw-tools/selftest_ml_checks.py     # -> 21/21 assertions pass
uv run python maw-tools/selftest_code_checks.py   # -> 10/10 assertions pass
uv run python maw-tools/selftest_web_checks.py    # -> 27/27 assertions pass
```

### Self-validation (run the framework against itself)

One command runs everything end-to-end and asserts **values, not just exit codes** —
so a silent drift in the model, the examples, or the committed write-ups turns it red:

```bash
uv run python maw-tools/selftest_all.py   # -> PASS 74/74 assertions held, exit 0
```

It guarantees, in one pass:
- all per-tool self-tests pass (`selftest_checks.py` 4/4, `selftest_ml_checks.py`
  21/21, `selftest_code_checks.py` 10/10, `selftest_web_checks.py` 27/27);
- the code example (`examples/sample_app`) still passes through the `checks.py test` gate;
- the ML example reproduces its documented numbers — leaky run `train/test == 1.000`
  with the **leakage gate firing** (`shuffle` exit 1), honest run `test ≈ 0.783 /
  train ≈ 0.743` (seed 7) with the gap, baseline (gain ≈ 0.242, CI excludes 0) and
  calibration (ECE ≈ 0.064) gates passing;
- **all nine ML validators exercised** on the example artifacts, pinning their values —
  F1 ≈ 0.759, data sha256, class balance 0.5325, multi-seed mean ≈ 0.757 (variance
  gate), and the feature-dominance max `|corr|` ≈ 0.361 (robustness);
- **the code-work pack exercised** on `examples/coupling_demo` — the regression test
  is **RED before the fix and GREEN after** (`[3, 1, 3, 1, 2]` → `[1, 2, 3]`), `refs`
  finds the **4** call sites of the coupled symbol, and the inline `# MAW-DEP[D01]`
  markers + the `deps.md` entry + the BUG/RCA files all exist where claimed;
- **the front-end pack exercised** on `examples/frontend_demo` — the planted defects
  fire and clear: contrast **2.64:1 → 6.87:1**, a11y **3 → 0** violations, the
  over-budget page **4742 B** (fails) vs the fixed **1838 B** (within the 3000 B
  budget), with `links` and `responsive` RED before / GREEN after;
- **change-verification exercised** on `examples/change_demo` — the `.btn` background
  is pinned **#e0e0e0 → #1a73e8**, `changed` is **GREEN on the real edit and RED on
  the no-op** fixture, and `tokens` is **RED on the off-palette drift** fixture
  (#2b7de9) — a requested change can't be claimed without proof, and a fix can't
  smuggle in style drift;
- **claim-to-evidence (dogfooding):** the numbers the committed ML run folder
  ([`runs/2026-06-01_ml-leakage-demo_81f1/`](runs/2026-06-01_ml-leakage-demo_81f1/))
  claims are recomputed fresh and asserted to still match — the metrics JSON, the
  prose in `run.md`, and the on-disk prediction arrays (reproduced bit-for-bit).

Every expected value is a named constant at the top of
[`selftest_all.py`](maw-tools/selftest_all.py) with a one-line comment, so a
legitimate model/seed change has exactly one place to update — and an *illegitimate*
drift is caught with both the expected and the real value printed.

> **Why no pytest?** The example deliberately uses a plain stdlib test runner so the
> repo has zero install steps and the `checks.py test` gate works on any machine.
> pytest is a fine choice for a larger suite — if you add it (`uv run pip install
> pytest`), point the gate at it the same way: `checks.py test --cmd "pytest -q"`.
> The framework doesn't care which test command it runs; it only gates on the exit
> code, so any runner (stdlib, pytest, jest, go test, …) works.

## What works today vs. what's still design

Honest scope — only the lines below actually run; everything else is still design,
and is marked as such:

**Works now (Phases 1–3 of [doc 08](docs/08-build-strategy.md)):**
- A 5-role roster of subagents in [`.claude/agents/`](.claude/agents/): `conductor`,
  `planner`, `worker`, `critic`, `acceptance_gate` (cheap models for routine roles,
  stronger models for the conductor and the independent gate).
- The [`/maw` conductor skill](.claude/skills/maw/SKILL.md): assess → select a
  conservative team → scaffold → delegate → refine loop → acceptance gate, within
  governor caps.
- Markdown memory + automatic hand-offs ([`docs/05`](docs/05-memory-and-handoffs.md)
  template enforced by a deterministic helper).
- Deterministic, model-free tools in [`maw-tools/`](maw-tools/): `scaffold_run.py`
  (run folders + hand-off files), `checks.py` (test runner + stats + a
  train-test-gap demo), and `selftest_checks.py` (verifies the checks against
  known-good/known-bad fixtures so the gate logic can't silently regress).
- A verified [end-to-end example](examples/README.md): four subagents, hand-off
  files, a passing refine loop, and a SHIP verdict.
- The **full ML validation pack (Phase 3.7,
  [`docs/06`](docs/06-ml-validation.md)) — all nine validators**:
  - `maw-tools/ml_checks.py` — nine deterministic, pure-stdlib checks, each JSON
    out with a `passed` field and exit 0/1 so gates run on the exit code:
    `gap` (train-test gap), `shuffle` (shuffled-label leakage control), `baseline`
    (model vs. majority class with a bootstrap-CI + permutation significance test),
    `metrics` (confusion matrix + precision/recall/F1 + the accuracy-on-imbalanced
    flag), `ece` (calibration error), `variance` (multi-seed mean/std/CI; fails if a
    gain is smaller than the seed-to-seed std), `repro` (sha256 of the dataset +
    asserts a seed was captured), `dataquality` (class balance + duplicate rows +
    missing/NaN scan), `robustness` (feature-dominance proxy — a feature whose
    `|corr|` with the label dominates is a shortcut/leak).
  - `maw-tools/selftest_ml_checks.py` — every check asserted **green-on-clean /
    red-on-bad** (**21/21**), so a check can't silently regress.
  - **Nine validator agents** (cheap haiku models; each runs its tool first, then
    interprets): `leakage_auditor`, `overfitting_checker`, `baseline_enforcer`,
    `metric_validator`, `calibration_checker`, `variance_auditor`,
    `reproducibility_checker`, `data_quality_auditor`, `robustness_tester`.
  - The **`/ml-experiment` skill** — wires the validators into the refine loop
    against a **hard-gate rubric with all nine gates**, and the acceptance gate
    **re-runs the checks against the on-disk artifacts** before SHIP.
  - A committed [worked example](examples/ml_experiment/README.md): a tiny dataset
    + training script with a **planted data-leakage bug**. The run
    ([`runs/2026-06-01_ml-leakage-demo_81f1/`](runs/2026-06-01_ml-leakage-demo_81f1/))
    shows the shuffled-label control catching the leak (**NO-SHIP**, leaky control
    accuracy 1.000 vs 0.575 chance), the fix, and the honest model shipping
    (**SHIP**, 0.783 test vs 0.542 baseline, gain CI [0.133, 0.350], F1 0.759,
    ECE 0.064) — verified by an independent acceptance gate that re-ran every check.
- The **full code-work pack (Phase 3.8,
  [`docs/07`](docs/07-code-and-debugging.md)) — seven agents + AST tools**:
  - `maw-tools/code_checks.py` — deterministic, pure-stdlib, JSON out, exit 0/1:
    `refs` (AST-scan every file:line that references a symbol — the computed
    blast radius behind hidden-dependency detection, with `--expect N` to pin it),
    `syntax` (`compile()` each file; catches syntax errors **and** null-byte
    corruption — see RCA-001), `test` (forwards to `checks.py`), and `dupes`
    (structural clone function bodies; fuzzy near-dup is `# MAW-TODO`).
  - `maw-tools/selftest_code_checks.py` — each subcommand asserted green-on-good /
    red-on-bad (**10/10**).
  - **Seven roster agents** (each runs its tool first, then interprets):
    `repro_engineer`, `bug_hunter`, `debugger`, `rca_writer`, `fixer`, `dep_mapper`,
    `code_reviewer` (the independent acceptance-gate reviewer for code).
  - The **hidden-dependency annotator** — `dep_mapper` writes an inline
    `# MAW-DEP[id]` marker above the coupled code **and** a central `deps.md` entry
    (endpoints, type, risk, blast radius, where-annotated), linked by a stable id —
    and the **bug/RCA documentation system** (`bugs/BUG-NNN.md` + the RCA template).
  - A committed [worked example](examples/coupling_demo/README.md): a **hidden
    coupling** (`dedupe_orders` silently requires pre-sorted input) + a **planted
    bug**. The run
    ([`runs/2026-06-02_coupling-demo_1e1e/`](runs/2026-06-02_coupling-demo_1e1e/))
    reproduces the failure (`[3, 1, 3, 1, 2]`), files [`BUG-002`](bugs/BUG-002-unsorted-dedupe.md),
    traces the root cause, annotates the coupling (`# MAW-DEP[D01]` + [`deps.md`](examples/coupling_demo/deps.md)),
    writes the [RCA](bugs/RCA-BUG-002-unsorted-dedupe.md), fixes it with a regression
    test (`[1, 2, 3]`), and ships on an **independent code review** that re-ran every
    check itself.
- The **front-end / UI pack — nine checks + eight agents + the `/frontend` skill**:
  - `maw-tools/web_checks.py` — nine deterministic, pure-stdlib (`html.parser`, `re`)
    checks, JSON out + exit 0/1: `contrast` (the exact WCAG 2.x ratio, pass ≥ 4.5 /
    3.0 large), `a11y` (img-without-alt, unlabeled controls, skipped heading levels,
    missing `<html lang>`, missing `<title>`), `budget` (total bytes incl. local
    assets + element/request counts), `links` (every internal anchor/asset resolves),
    `markup` (unclosed/mismatched tags + duplicate ids), `responsive` (viewport meta
    + `@media` presence), and — for **change-verification** — `style` (the exact
    resolved value of a `selector { property }`), `changed` (assert a value actually
    changed vs a pre-change snapshot; a no-op or wrong-target edit fails), and
    `tokens` (scan CSS against a `design-tokens.json` and flag off-palette/off-grid
    values = style drift).
  - `maw-tools/selftest_web_checks.py` — every subcommand asserted green-on-good /
    red-on-bad incl. the pinned contrast math and the before/after style values
    (**27/27**).
  - **Eight roster agents** (auditors on haiku; each runs its tool first, then
    interprets): `ui_builder`, `a11y_auditor`, `responsive_checker`, `perf_budgeter`,
    `markup_validator`, `change_verifier` (snapshots before, proves the change
    landed), `style_drift_auditor` (token conformance), plus the **advisory**
    `ux_critic` (aesthetic read) and `visual_verifier` (before/after, Claude-in-Chrome
    where available) — both **not** hard gates.
  - The **`/frontend` skill** — wires the auditors into the refine loop against a
    **hard-gate rubric** (contrast/a11y/links/markup/budget/responsive, plus
    change + drift when a change was requested), and the acceptance gate **re-runs
    the checks against the on-disk files** before SHIP.
  - A committed [worked demo](examples/frontend_demo/README.md): a signup page with
    **six planted defects** (low-contrast button **2.64:1**, alt-less image, skipped
    heading, missing viewport, broken `#anchor`, **4742 B** over-budget inline blob).
    The run ([`runs/2026-06-02_frontend-demo_c53d/`](runs/2026-06-02_frontend-demo_c53d/))
    shows every gate firing on the defective page and clearing on the fix (a11y 3 → 0,
    contrast 2.64:1 → 6.87:1, **1838 B** within budget) — verified by an independent
    acceptance gate that re-ran every check.
  - A second committed [change-verification demo](examples/change_demo/README.md):
    "make the primary button blue (#1a73e8) and larger". The run
    ([`runs/2026-06-02_change-verify_6cc9/`](runs/2026-06-02_change-verify_6cc9/))
    proves the value moved **#e0e0e0 → #1a73e8** with no token drift (**SHIP**), and
    shows the gates biting on a **no-op** fixture (edit claimed but not applied →
    `changed` exit 1) and a **drift** fixture (off-palette `#2b7de9` → `tokens`
    exit 1) → **NO-SHIP**.
- A **whole-framework self-validation harness**
  ([`maw-tools/selftest_all.py`](maw-tools/selftest_all.py)): runs all per-tool
  self-tests, reproduces all three worked examples, exercises the nine ML validators,
  the code-work pack, and the **front-end pack** on the example artifacts, and
  **dogfoods the committed ML run folder** — recomputing the numbers it claims and
  asserting they still match (values, not just exit codes; incl. the pinned contrast
  ratios, a11y before/after counts, and demo page byte budget). **PASS 74/74, exit 0**
  — raw output committed in [`selftest_output.txt`](selftest_output.txt).

**Still design-only (Phase 4+):**
- **Deeper ML checks not yet built** ([`docs/06`](docs/06-ml-validation.md)):
  CV-fold stability (a `cv` check), the **full robustness suite** beyond the
  feature-dominance proxy (input-perturbation stability, counterfactual /
  distribution-shift / recent-period probes), and temporal/group leakage splitters.
  `# MAW-TODO`
- The **dependency-DAG scheduler** ([`docs/07 §1`](docs/07-code-and-debugging.md) /
  [`docs/01`](docs/01-architecture.md)) — `code_checks.py refs` + `deps.md` make the
  coupling graph that *would* feed it, but the current conductor runs code work
  **sequentially**; safe concurrent scheduling over that graph, and fuzzy
  near-duplicate detection in `dupes`, are not built. `# MAW-TODO`
- The `route` / `debate` patterns — the current conductor runs the team sequentially.
  `# MAW-TODO`
- **Front-end visual / aesthetic layer** ([front-end pack](examples/frontend_demo/README.md)):
  the `web_checks.py` gates are source-level and computed. **Visual / pixel-level
  regression** ("does the page actually render and lay out correctly in a real
  browser") needs the Chrome connector or a headless-browser dep and is **not built**;
  `ux_critic` only gives an *advisory* aesthetic read. The `responsive` check verifies
  viewport/`@media` *presence*, not that the layout actually reflows. `# MAW-TODO`
- The `debug` workflow skill (the `ml-experiment` skill now works — see above) and
  Phase-5 polish (path-resolution for `maw-tools/`, retention/compaction). `# MAW-TODO`

## Design documentation

The complete architecture is specified in [`docs/`](docs/):

| Doc | Contents |
|---|---|
| [`00-overview.md`](docs/00-overview.md) | Vision, design goals, the recursive-quality principle |
| [`01-architecture.md`](docs/01-architecture.md) | System layers, components, conductor, acceptance gate, concurrency |
| [`02-patterns.md`](docs/02-patterns.md) | The orchestration pattern library |
| [`03-api-design.md`](docs/03-api-design.md) | Developer-facing API and usage examples |
| [`04-roadmap.md`](docs/04-roadmap.md) | Phased build plan and open questions |
| [`05-memory-and-handoffs.md`](docs/05-memory-and-handoffs.md) | Markdown memory + automatic hand-off subsystem |
| [`06-ml-validation.md`](docs/06-ml-validation.md) | ML validators, checks, and evaluation rubric |
| [`07-code-and-debugging.md`](docs/07-code-and-debugging.md) | Bug methodology, RCA, hidden-dependency annotation |
| [`08-build-strategy.md`](docs/08-build-strategy.md) | The zero-extra-cost build path (runs on Claude Code) |

## Tech

Built on [Claude Code](https://code.claude.com), running on a Pro/Max subscription (no API key, no per-token cost). Agents are defined as configuration (subagents, skills, conventions); deterministic checks are plain stdlib Python scripts; the multi-agent runtime is provided by Claude Code. (The same configuration could later be driven by the Claude Agent SDK / API for unattended use — see [`docs/08`](docs/08-build-strategy.md).)
