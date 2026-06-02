# Change verification — the requested edit is provably applied

## `style BEFORE .btn background` -> exit 0

```json
{
  "check": "style",
  "css": "examples/change_demo/before/button.css",
  "selector": ".btn",
  "property": "background",
  "value": "#e0e0e0",
  "found": true,
  "expected": null,
  "passed": true,
  "note": ".btn { background } = '#e0e0e0'"
}
```

## `style AFTER  .btn background` -> exit 0

```json
{
  "check": "style",
  "css": "examples/change_demo/after/button.css",
  "selector": ".btn",
  "property": "background",
  "value": "#1a73e8",
  "found": true,
  "expected": null,
  "passed": true,
  "note": ".btn { background } = '#1a73e8'"
}
```

## `changed REAL edit (#e0e0e0 -> #1a73e8)` -> exit 0

```json
{
  "check": "changed",
  "mode": "selector",
  "css": "examples/change_demo/after/button.css",
  "selector": ".btn",
  "property": "background",
  "before": "#e0e0e0",
  "current": "#1a73e8",
  "expected": "#1a73e8",
  "changed": true,
  "matches_expected": true,
  "passed": true,
  "note": ".btn { background }: '#e0e0e0' -> '#1a73e8' (== expected '#1a73e8')"
}
```

## `changed also larger (font-size 0.75rem -> 1rem)` -> exit 0

```json
{
  "check": "changed",
  "mode": "selector",
  "css": "examples/change_demo/after/button.css",
  "selector": ".btn",
  "property": "font-size",
  "before": "0.75rem",
  "current": "1rem",
  "expected": "1rem",
  "changed": true,
  "matches_expected": true,
  "passed": true,
  "note": ".btn { font-size }: '0.75rem' -> '1rem' (== expected '1rem')"
}
```

## `style_drift_auditor: tokens AFTER (on palette)` -> exit 0

```json
{
  "check": "tokens",
  "css": "examples/change_demo/after/button.css",
  "tokens": "examples/change_demo/design-tokens.json",
  "categories_checked": [
    "colors",
    "spacing",
    "fonts"
  ],
  "drift_count": 0,
  "drift": [],
  "passed": true,
  "note": "every scanned value is in the design-token set (no drift); note: var(--x) refs + complex shorthand are not decomposed (# MAW-TODO)"
}
```
