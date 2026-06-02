# Refactoring pack demo — split a bloated module, prove behavior is preserved

Detects a bloated file, splits it into cohesive modules, and gates the split on a
deterministic **before/after equivalence** check. Pure stdlib (`ast`, `inspect`).

```
refactor_demo/
├── golden_harness.py     # golden() — calls every function over fixed inputs
├── bloated/              # the trigger: one 110-LOC file, 8 functions, 4 clusters
│   ├── widgets.py
│   └── test_widgets.py
├── split/                # the GOOD refactor: cohesive package, public API preserved
│   ├── widgets/{__init__,text,mathx,listx,money}.py
│   └── test_widgets.py
└── bad_split/            # the BAD refactor: format_cents silently changed behavior
    ├── widgets/…         # (money.py dropped the cents zero-pad)
    └── test_widgets.py
```

## (a) Happy path — detect bloat, split, equivalence holds → SHIP

```bash
# trigger: the bloated module is over budget
uv run python maw-tools/refactor_checks.py bloat examples/refactor_demo/bloated/widgets.py --max-loc 80 --max-defs 5   # exit 1

# snapshot the pre-refactor public surface + behavior
uv run python maw-tools/refactor_checks.py api    --module widgets --src-dir examples/refactor_demo/bloated > /tmp/api_before.json
uv run python maw-tools/refactor_checks.py golden --harness examples/refactor_demo/golden_harness.py --src-dir examples/refactor_demo/bloated --snapshot /tmp/gold.json

# after the split: bloat clears, and the surface + behavior are identical
uv run python maw-tools/refactor_checks.py bloat  --root examples/refactor_demo/split/widgets --max-loc 80 --max-defs 5   # exit 0
uv run python maw-tools/refactor_checks.py api    --module widgets --src-dir examples/refactor_demo/split --baseline /tmp/api_before.json   # exit 0, identical
uv run python maw-tools/refactor_checks.py golden --harness examples/refactor_demo/golden_harness.py --src-dir examples/refactor_demo/split --compare /tmp/gold.json   # exit 0, byte-identical
```

## (b) Bad refactor — behavior changed → NO-SHIP + revert

`bad_split/` looks like a clean split and **the test suite still passes** (it doesn't
assert sub-dollar amounts), and the **API surface is identical** (signatures
unchanged). But `golden` exercises `format_cents(5)`/`format_cents(-7)`:

```bash
uv run python maw-tools/code_checks.py     test   --cmd "python test_widgets.py" --cwd examples/refactor_demo/bad_split        # exit 0 — tests pass
uv run python maw-tools/refactor_checks.py api    --module widgets --src-dir examples/refactor_demo/bad_split --baseline /tmp/api_before.json   # exit 0 — surface identical
uv run python maw-tools/refactor_checks.py golden --harness examples/refactor_demo/golden_harness.py --src-dir examples/refactor_demo/bad_split --compare /tmp/gold.json
# -> exit 1: format_cents_neg "-$0.07" -> "-$0.7"  ->  NO-SHIP, revert the refactor
```

**That contrast is the whole point:** `golden` is the behavioral truth — it catches a
regression that both the test suite *and* the API surface miss. A refactor SHIPs only
if **all three** hold: tests identical, api unchanged, golden byte-identical.

The before/after numbers and the RED/GREEN verdicts are pinned in
`maw-tools/selftest_all.py` (§8) and the per-tool verdicts in
`maw-tools/selftest_refactor_checks.py`. The full worked run is committed at
`runs/2026-06-02_refactor-widgets_e7c1/`.

## # MAW-TODO
`branch_count` approximates cyclomatic complexity (it counts branch-ish AST nodes),
not the exact McCabe number; split-boundary cohesion is shared-symbol grouping, not
full call-graph community detection. Those deeper metrics are not built. The
equivalence gate (tests + api + golden) is the hard, real guarantee.
