# Behavior-equivalence gate — BAD split is caught -> NO-SHIP + revert

## `code_checks test (bad_split) — tests still pass!` -> exit 0

```json
{
  "check": "test",
  "command": "\"C:\\Users\\Biztech\\AppData\\Roaming\\uv\\python\\cpython-3.14-windows-x86_64-none\\python.exe\" test_widgets.py",
  "cwd": "examples/refactor_demo/bad_split",
  "exit_code": 0,
  "timed_out": false,
  "passed": true,
  "duration_sec": 0.052,
  "stdout_tail": "all widgets tests passed\n",
  "stderr_tail": ""
}
```

## `api bad_split --baseline — surface identical (api can't see it)` -> exit 0

```json
{
  "check": "api",
  "module": "widgets",
  "mode": "compare",
  "baseline": "runs\\2026-06-02_refactor-widgets_e7c1\\artifacts\\api_before.json",
  "added": [],
  "removed": [],
  "changed": [],
  "baseline_sha256": "1d9a706a57b8e2d6fcd685f09499ad3136c54201773f505bce3c4b1d52a0fca6",
  "current_sha256": "1d9a706a57b8e2d6fcd685f09499ad3136c54201773f505bce3c4b1d52a0fca6",
  "passed": true,
  "note": "public API surface is byte-identical to the baseline"
}
```

## `golden bad_split --compare — DIFFERS -> NO-SHIP` -> exit 1

```json
{
  "check": "golden",
  "mode": "compare",
  "harness": "examples/refactor_demo/golden_harness.py",
  "snapshot": "runs\\2026-06-02_refactor-widgets_e7c1\\artifacts\\golden_before.json",
  "cases": 11,
  "identical": false,
  "first_difference": {
    "case": "format_cents_neg",
    "snapshot": "-$0.07",
    "current": "-$0.7"
  },
  "passed": false,
  "note": "golden outputs DIFFER from the snapshot \u2014 behavior changed"
}
```
