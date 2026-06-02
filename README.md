# Multi-Agent Workflow

**Turn a single Claude assistant into a coordinated, self-verifying team of specialist agents — planner, workers, critics, validators — that hand work off, check each other, and iterate until the result actually holds up, all on a Claude Code subscription with no per-token API cost.**

*Status: architecture & design complete ([`docs/`](docs/)), and a working version runs today — Phases 1–3 of [`docs/08-build-strategy.md`](docs/08-build-strategy.md). What's real vs. still design is spelled out in [What works today](#what-works-today).*

## Quickstart

> **Requirements: Python 3.10+, standard library only** — nothing to `pip install`. If `python` isn't on your PATH (common on Windows, where it resolves to the Microsoft Store stub), use **`uv run python …`** or the **`py …`** launcher in every command below.

From inside this repo, start Claude Code and hand the conductor a task:

```bash
claude                                  # start Claude Code (runs on your subscription)
/maw implement normalize_whitespace in examples/sample_app/textutil.py so the tests pass
```

The conductor assembles a `planner → worker → critic` team, scaffolds a `runs/<timestamp>_<slug>/` folder, passes markdown hand-off notes between the agents, loops the critic until the quality bar is met, and finishes with an **independent `acceptance_gate`** (SHIP / NO-SHIP). Open the run folder to read exactly how it got there; a complete worked run is in [`examples/README.md`](examples/README.md).

Want to see the deterministic machinery without a model? The checks run standalone:

```bash
python maw-tools/checks.py test --cmd "python test_textutil.py" --cwd examples/sample_app
# -> {"check": "test", "exit_code": 0, "passed": true, ...}
```

The framework installs as agent + skill definitions in your Claude Code config (`~/.claude/`), so `/maw` works in **every** folder automatically — the definitions live once in `~/.claude/` while the agents operate on the files in your current directory. To install from any folder, see [`INSTALL.md`](INSTALL.md).

## How it works

A single LLM pass is fast but fragile: no second opinion, no check on whether the output is actually correct, and for technical work (ML especially) the most impressive-looking results are often the most misleading. This framework makes **multi-agent coordination and self-verification the default** — work is decomposed across specialists, critiqued and revised in a loop against an explicit bar, independently verified before it's accepted, and self-documented as readable markdown on disk.

A *conductor* reads your task and drives it through a fixed loop, in order:

| Stage | What happens |
|---|---|
| **Conductor** | Reads the task and selects the smallest reasonable team — which roles, how many, which orchestration pattern, what quality bar — conservative by default, escalating only when checks fail, all within hard "governor" caps on agent count and cost. |
| **Plan gate** | Before any agent runs, the proposed plan is vetted: `plan_check` (deterministic, hard) + `plan_reviewer` (advisory) check roster validity, the caps, and the required validators for the task type; the conductor re-plans (capped at 2 revisions) if flagged. |
| **Execution** | The team runs and passes structured hand-off notes between agents while sharing a journal — so a multi-agent chain runs from one instruction with no manual prompt-threading. Patterns: `pipeline`, `orchestrate` (lead + workers), `parallel` (fan-out + reduce), `route` (classify + specialist), `debate` — mixed and nested as needed. |
| **Refine loop** | `generate → evaluate → revise`, repeating until the output clears an explicit, rubric-based bar (the `refine` pattern) — the core mechanism for compounding quality rather than relying on a single lucky pass. |
| **Acceptance gate** | An independent agent (*not* the one that produced the work) checks task conformance, claim-to-evidence consistency (anti-overclaiming), and end-to-end soundness → **SHIP / NO-SHIP**, with optional human sign-off for high-stakes runs. |

Work runs concurrently only when it's genuinely independent (scheduled against a dependency graph); discovered hidden couplings feed back so the system stops parallelizing things that secretly conflict. Routine roles use cheaper models; the conductor and the two independent gates use stronger ones.

## What makes it distinctive: the quality bar is computation, and the framework checks itself

Most multi-agent setups let one model grade another's. Here the hard gates are **deterministic, model-free scripts** — *compute first, reason second*. A WCAG contrast ratio, a shuffled-label leakage control, a before/after behavioral diff: those are real numbers and exit codes, not an LLM's opinion. The agents only *interpret* what the tools compute, and **every check is itself self-tested** green-on-good / red-on-bad, so the gate logic can't silently regress.

The run is **bracketed by two independent gates** — the plan gate before, the acceptance gate after — each run by a different agent than the one doing the work.

And the whole framework **validates itself against reality.** One command re-runs every per-tool self-test, reproduces all the worked examples, and **dogfoods the committed run folders** — recomputing every documented number and asserting it still matches (values, not just exit codes):

```bash
uv run python maw-tools/selftest_all.py   # -> PASS 87/87 assertions held, exit 0
```

Every expected value is a named constant at the top of [`selftest_all.py`](maw-tools/selftest_all.py) with a one-line comment, so a legitimate model/seed change has exactly one place to update — and an *illegitimate* drift turns the suite red, printing both the expected and the real value. Raw output is committed in [`selftest_output.txt`](selftest_output.txt); the numbers in this README come from that run. What it pins, by pack:

- **Per-tool self-tests:** `selftest_checks.py` 4/4, `selftest_ml_checks.py` 21/21, `selftest_code_checks.py` 10/10, `selftest_web_checks.py` 27/27, `selftest_plan_check.py` 16/16, `selftest_refactor_checks.py` 10/10; and the code example still passes the `checks.py test` gate.
- **ML:** leaky run `train/test == 1.000` with the leakage gate firing (`shuffle` exit 1); honest run `test ≈ 0.783` / `train ≈ 0.743` (seed 7), gain ≈ 0.242 (CI [0.133, 0.350], excludes 0), ECE ≈ 0.064; plus F1 ≈ 0.759, data sha256, class balance 0.5325, multi-seed mean ≈ 0.757, feature-dominance max `|corr|` ≈ 0.361.
- **Code:** the regression test is RED before the fix (`[3, 1, 3, 1, 2]`) and GREEN after (`[1, 2, 3]`); `refs` finds the **4** call sites; the `# MAW-DEP[D01]` markers, `deps.md` entry, and BUG/RCA files all exist.
- **Front-end:** contrast 2.64:1 → 6.87:1, a11y 3 → 0, over-budget 4742 B (fails) vs 1838 B (within the 3000 B budget), `links`/`responsive` RED → GREEN; the `.btn` background pinned `#e0e0e0` → `#1a73e8`, `changed` GREEN on the real edit / RED on the no-op, `tokens` RED on the off-palette `#2b7de9` drift.
- **Plan gate:** an ML plan missing `leakage_auditor` is rejected (`plan_check` exit 1, naming the required-role rule); the corrected plan is accepted (exit 0).
- **Refactoring:** `bloat` RED on the bloated file (loc 110, defs 9) / GREEN on the split package; `api` identical pre/post the good split; `golden` GREEN on the good split and RED on the bad split.
- **Claim-to-evidence (dogfooding):** the numbers the committed ML run folder claims are recomputed fresh and asserted to match — the metrics JSON, the prose in `run.md`, and the on-disk prediction arrays (bit-for-bit).

## Domain packs

Beyond generic orchestration, specialized packs add deterministic gates for domains where naive results mislead. Each ships a stdlib check tool (JSON out, exit 0/1), agents that run the tool then interpret, a workflow skill, and a committed worked demo. Full enumerations are in the [reference](#reference); the docs and demos have the depth.

| Pack | What it catches | Tool · self-test | Skill |
|---|---|---|---|
| **ML validation** ([docs/06](docs/06-ml-validation.md)) | leakage, overfitting, weak/insignificant baselines, misleading metrics, miscalibration, seed variance, label/data quality, shortcut features, irreproducibility | `ml_checks.py` (9 checks) · 21/21 | `/ml-experiment` |
| **Code & debugging** ([docs/07](docs/07-code-and-debugging.md)) | undetected blast radius, hidden coupling, symptom-only fixes, syntax / null-byte corruption | `code_checks.py` (4 subcommands) · 10/10 | code roster via `/maw` |
| **Front-end / UI** ([demo](examples/frontend_demo/)) | low contrast, a11y violations, page bloat, broken links, malformed markup, non-responsiveness — plus *unverified* changes & style drift | `web_checks.py` (9 checks) · 27/27 | `/frontend` |
| **Refactoring** ([demo](examples/refactor_demo/)) | refactors that silently change behavior | `refactor_checks.py` (3 subcommands) · 10/10 | `/maw refactor <path>` |

A generic "looks good" critic is exactly what gets fooled by a leaked feature, an alt-less image, or a refactor that quietly drops a function — so each pack replaces the vibe check with a computed one, and each has a committed demo where the gate genuinely fires and then clears:

- **ML** — a planted data leak is caught (leaky control 1.000 vs 0.575 chance → **NO-SHIP**) and the fixed model ships (0.783 test vs 0.542 baseline → **SHIP**): [`runs/2026-06-01_ml-leakage-demo_81f1/`](runs/2026-06-01_ml-leakage-demo_81f1/).
- **Code** — a hidden coupling (`dedupe_orders` silently requires pre-sorted input) + a planted bug are reproduced, traced, annotated, RCA'd, and fixed: [`runs/2026-06-02_coupling-demo_1e1e/`](runs/2026-06-02_coupling-demo_1e1e/).
- **Front-end** — six planted defects each caught then fixed ([`frontend_demo`](examples/frontend_demo/)); a "make the button blue `#1a73e8`" change proven applied while a no-op and an off-palette drift are caught as NO-SHIP ([`change_demo`](examples/change_demo/)).
- **Refactoring** — a bloated module split with behavior preserved (**SHIP**), while a bad split that still *passes its tests and keeps an identical API* is caught by `golden` (`-$0.07 → -$0.7`) → **NO-SHIP + revert**: [`runs/2026-06-02_refactor-widgets_e7c1/`](runs/2026-06-02_refactor-widgets_e7c1/).

---

## Reference

The exhaustive lists live here so the sections above can stay readable. Each tool prints a JSON object with a `passed` field and exits 0/1, so callers gate on `$?`; all are pure standard library (no model, no network).

### Tools (`maw-tools/`)

| Tool | Subcommands (what each computes) | Self-test |
|---|---|---|
| `scaffold_run.py` | `init` (create a run folder), `handoff` (write a docs/05-template hand-off file) | — |
| `checks.py` | `test` (run a command, report pass/fail), `stats` (descriptive stats), `gap` (train-vs-test gap demo) | `selftest_checks.py` **4/4** |
| `ml_checks.py` | `gap` (train-test gap), `shuffle` (shuffled-label leakage control), `baseline` (model vs. majority class + bootstrap-CI + permutation significance), `metrics` (confusion + P/R/F1 + accuracy-on-imbalanced flag), `ece` (calibration error), `variance` (multi-seed mean/std/CI; fails if gain < seed-to-seed std), `repro` (dataset sha256 + seed captured), `dataquality` (class balance + duplicate rows + missing/NaN), `robustness` (feature-dominance proxy) | `selftest_ml_checks.py` **21/21** |
| `code_checks.py` | `refs` (AST blast-radius of a symbol, `--expect N` to pin), `syntax` (`compile()` each file; catches syntax errors **and** null-byte corruption — see RCA-001), `test` (forwards to `checks.py`), `dupes` (structural clone bodies; fuzzy near-dup is `# MAW-TODO`) | `selftest_code_checks.py` **10/10** |
| `web_checks.py` | `contrast` (WCAG 2.x ratio, ≥ 4.5 / 3.0 large), `a11y` (alt-less imgs, unlabeled controls, skipped headings, missing `lang`/`<title>`), `budget` (total bytes incl. local assets + element/request counts), `links` (internal anchors/assets resolve), `markup` (unclosed/mismatched tags + duplicate ids), `responsive` (viewport meta + `@media` presence), `style` (resolved value of a `selector { property }`), `changed` (a value actually changed vs a pre-change snapshot — no-op/wrong-target fails), `tokens` (CSS vs `design-tokens.json`; off-palette/off-grid = drift) | `selftest_web_checks.py` **27/27** |
| `plan_check.py` | validates the conductor's structured plan: roles exist in the roster, governor caps hold, `acceptance_gate` present, no duplicate/unjustified roles, required-role rules per task type fire (rule table in `GOVERNOR` + `REQUIRED_ROLES`) | `selftest_plan_check.py` **16/16** |
| `refactor_checks.py` | `bloat` (per-file LOC, def/class count, longest-function LOC, branch count ≈ cyclomatic complexity, imports vs configurable budgets; ranks offenders — the trigger), `api` (public surface = names + signatures, by import + introspection; `--baseline` to diff + gate), `golden` (run a harness, snapshot outputs; `--compare` asserts byte-identical — the behavioral truth) | `selftest_refactor_checks.py` **10/10** |

Required-role rules enforced by `plan_check`: **ml** → `leakage_auditor` + `baseline_enforcer`; **frontend** → `a11y_auditor` + `change_verifier`; **code** → `code_reviewer` + `dep_mapper`; every plan → `acceptance_gate`.

### Agents (`.claude/agents/`) — each runs its tool first, then interprets

| Group | Agents |
|---|---|
| **Core roster** | `conductor`, `planner`, `worker`, `critic`, `acceptance_gate` |
| **Plan gate** | `plan_reviewer` (independent, opus-tier; APPROVE / REVISE — advisory) |
| **ML validators** (haiku) | `leakage_auditor`, `overfitting_checker`, `baseline_enforcer`, `metric_validator`, `calibration_checker`, `variance_auditor`, `reproducibility_checker`, `data_quality_auditor`, `robustness_tester` |
| **Code & debugging** | `repro_engineer`, `bug_hunter`, `debugger`, `rca_writer`, `fixer`, `dep_mapper`, `code_reviewer` (the independent acceptance-gate reviewer for code) |
| **Front-end** | `ui_builder`; hard-gate auditors `a11y_auditor`, `responsive_checker`, `perf_budgeter`, `markup_validator`, `change_verifier`, `style_drift_auditor`; advisory `ux_critic` (aesthetic read) + `visual_verifier` (before/after, drives Claude-in-Chrome where available) — both explicitly **not** hard gates |
| **Refactoring** | `refactor_scout` (haiku; runs `bloat`, proposes split boundaries by shared symbols), `refactorer` (splits, preserves the public API, runs the equivalence gate) |

### Skills (`.claude/skills/`)

| Skill | Role |
|---|---|
| `/maw <task>` | the conductor: assess → plan gate → delegate → refine loop → acceptance gate; runs `bloat` as an advisory end-of-task nudge on code work |
| `/ml-experiment <task>` | wires the nine ML validators into the loop against a hard-gate rubric; the acceptance gate re-runs the checks against the on-disk artifacts before SHIP |
| `/frontend <task>` | wires the front-end auditors into the loop (gates: contrast/a11y/links/markup/budget/responsive, plus change + drift when a change was requested); acceptance gate re-runs them on disk |
| `/maw refactor <path>` | behavior-equivalence gate: a split may SHIP only if, vs the pre-refactor snapshot, **tests pass identically AND `api` is unchanged AND `golden` is byte-identical** — any difference reverts |

### Running the tests

The worked example uses a plain stdlib runner (no `pytest`), so the repo has zero install steps:

```bash
cd examples/sample_app && python test_textutil.py      # -> "PASS — all 6 cases passed", exit 0
python maw-tools/selftest_checks.py                    # the gate logic, 4/4
uv run python maw-tools/selftest_all.py                # everything, end-to-end, PASS 87/87
```

The per-tool self-tests (`selftest_ml_checks.py` 21/21, `selftest_code_checks.py` 10/10, `selftest_web_checks.py` 27/27, `selftest_plan_check.py` 16/16, `selftest_refactor_checks.py` 10/10) run the same way.

> **Why no pytest?** The plain stdlib runner means the `checks.py test` gate works on any machine with nothing to install. pytest is fine for a larger suite — install it and point the gate at it (`checks.py test --cmd "pytest -q"`); the framework only gates on the exit code, so any runner (stdlib, pytest, jest, go test, …) works.

## What works today

Everything in the [Reference](#reference) above is implemented and self-tested (Phases 1–3 of [doc 08](docs/08-build-strategy.md)): the core roster + `/maw`, markdown memory + automatic hand-offs ([docs/05](docs/05-memory-and-handoffs.md) template enforced by `scaffold_run.py`), the deterministic `maw-tools/`, all four domain packs with their agents/skills/committed demos, the two independent gates, and the whole-framework self-validation harness (**PASS 87/87**). The verified end-to-end example is in [`examples/README.md`](examples/README.md).

**Still design-only (Phase 4+), marked `# MAW-TODO`:**

| Area | Not yet built |
|---|---|
| ML ([docs/06](docs/06-ml-validation.md)) | CV-fold stability (a `cv` check), the full robustness suite beyond the feature-dominance proxy (input-perturbation, counterfactual / distribution-shift / recent-period probes), temporal/group leakage splitters |
| Concurrency ([docs/07 §1](docs/07-code-and-debugging.md), [docs/01](docs/01-architecture.md)) | the dependency-DAG scheduler — `refs` + `deps.md` build the coupling graph that *would* feed it, but the conductor currently runs code work sequentially; fuzzy near-duplicate detection in `dupes` |
| Patterns | the `route` / `debate` patterns (the conductor currently runs the team sequentially) |
| Front-end | visual / pixel-level regression ("does it actually render right in a browser") — needs the Chrome connector or a headless-browser dep; `ux_critic` is only an advisory aesthetic read, and `responsive` checks `@media`/viewport *presence*, not actual reflow |
| Refactoring | branch count only *approximates* cyclomatic complexity; deeper cohesion metrics |
| Workflow | a dedicated `debug` skill; Phase-5 polish (path-resolution for `maw-tools/`, retention/compaction) |

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

Built on [Claude Code](https://code.claude.com), running on a Pro/Max subscription (no API key, no per-token cost). Agents are defined as configuration (subagents, skills, conventions); deterministic checks are plain stdlib Python scripts; the multi-agent runtime is provided by Claude Code. The same configuration could later be driven by the Claude Agent SDK / API for unattended use — see [`docs/08`](docs/08-build-strategy.md).
