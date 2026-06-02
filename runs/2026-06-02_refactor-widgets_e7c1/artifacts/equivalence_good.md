# Behavior-equivalence gate — GOOD split SHIPs (tests + api + golden all identical)

## `code_checks test (split) ` -> exit 0

```json
{
  "check": "test",
  "command": "\"C:\\Users\\Biztech\\AppData\\Roaming\\uv\\python\\cpython-3.14-windows-x86_64-none\\python.exe\" test_widgets.py",
  "cwd": "examples/refactor_demo/split",
  "exit_code": 0,
  "timed_out": false,
  "passed": true,
  "duration_sec": 0.058,
  "stdout_tail": "all widgets tests passed\n",
  "stderr_tail": ""
}
```

## `api split --baseline api_before.json` -> exit 0

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

## `golden split --compare golden_before.json` -> exit 1

```json
{
  "check": "golden",
  "mode": "compare",
  "harness": "examples/refactor_demo/golden_harness.py",
  "snapshot": "runs\\2026-06-02_refactor-widgets_e7c1\\artifacts\\golden_before.json",
  "cases": 11,
  "identical": false,
  "first_difference": null,
  "passed": false,
  "note": "golden outputs DIFFER from the snapshot \u2014 behavior changed"
}
```
