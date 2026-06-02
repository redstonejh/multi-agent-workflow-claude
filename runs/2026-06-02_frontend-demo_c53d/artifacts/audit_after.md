# Audit AFTER — fixed page (every gate green)

## `contrast --fg #ffffff --bg #1558b0 (button)` -> exit 0

```json
{
  "check": "contrast",
  "fg": "#ffffff",
  "bg": "#1558b0",
  "ratio": 6.8747,
  "threshold": 4.5,
  "large_text": false,
  "passed": true,
  "note": "contrast 6.87:1 meets WCAG AA (normal >=4.5)"
}
```

## `a11y index.html` -> exit 0

```json
{
  "check": "a11y",
  "html": "examples/frontend_demo/index.html",
  "violation_count": 0,
  "violations": [],
  "passed": true,
  "note": "no accessibility violations found (deterministic subset)"
}
```

## `links index.html` -> exit 0

```json
{
  "check": "links",
  "html": "examples/frontend_demo/index.html",
  "checked": 4,
  "external_skipped": 0,
  "broken_count": 0,
  "broken": [],
  "passed": true,
  "note": "all internal links/anchors/assets resolve"
}
```

## `responsive index.html` -> exit 0

```json
{
  "check": "responsive",
  "html": "examples/frontend_demo/index.html",
  "has_viewport_meta": true,
  "media_query_count": 1,
  "css_scanned": [
    "examples/frontend_demo/style.css"
  ],
  "passed": true,
  "note": "viewport meta present and >=1 @media query found (presence check only \u2014 true layout/visual correctness needs a browser, # MAW-TODO)"
}
```

## `markup index.html` -> exit 0

```json
{
  "check": "markup",
  "html": "examples/frontend_demo/index.html",
  "problem_count": 0,
  "problems": [],
  "passed": true,
  "note": "well-formed: tags balanced, ids unique (optional-tag implied close handled leniently)"
}
```

## `budget index.html --max-bytes 3000` -> exit 0

```json
{
  "check": "budget",
  "html": "examples/frontend_demo/index.html",
  "html_bytes": 819,
  "asset_bytes": 1019,
  "total_bytes": 1838,
  "element_count": 21,
  "request_count": 2,
  "assets": [
    {
      "url": "style.css",
      "bytes": 732
    },
    {
      "url": "assets/logo.svg",
      "bytes": 287
    }
  ],
  "max_bytes": 3000,
  "max_elements": null,
  "max_requests": null,
  "passed": true,
  "note": "within budget"
}
```
