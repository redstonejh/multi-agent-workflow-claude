# NO-SHIP fixtures — the gates catch a fake / a regression

## `changed NO-OP (edit claimed but not applied)` -> exit 1

```json
{
  "check": "changed",
  "mode": "selector",
  "css": "examples/change_demo/noop/button.css",
  "selector": ".btn",
  "property": "background",
  "before": "#e0e0e0",
  "current": "#e0e0e0",
  "expected": "#1a73e8",
  "changed": false,
  "matches_expected": false,
  "passed": false,
  "note": "NO-OP: .btn { background } still '#e0e0e0' (== before)"
}
```

## `tokens DRIFT (off-palette #2b7de9 introduced)` -> exit 1

```json
{
  "check": "tokens",
  "css": "examples/change_demo/drift/button.css",
  "tokens": "examples/change_demo/design-tokens.json",
  "categories_checked": [
    "colors",
    "spacing",
    "fonts"
  ],
  "drift_count": 1,
  "drift": [
    {
      "category": "color",
      "selector": ".btn",
      "property": "background",
      "value": "#2b7de9"
    }
  ],
  "passed": false,
  "note": "1 off-palette value(s) \u2014 style drift"
}
```
