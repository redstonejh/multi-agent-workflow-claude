# Audit BEFORE — defective page (the gates fire)

## `contrast --fg #9aa0a6 --bg #ffffff (button)` -> exit 1

```json
{
  "check": "contrast",
  "fg": "#9aa0a6",
  "bg": "#ffffff",
  "ratio": 2.6405,
  "threshold": 4.5,
  "large_text": false,
  "passed": false,
  "note": "contrast 2.64:1 below WCAG AA threshold 4.5 \u2014 text hard to read"
}
```

## `a11y before/index.html` -> exit 1

```json
{
  "check": "a11y",
  "html": "examples/frontend_demo/before/index.html",
  "violation_count": 3,
  "violations": [
    {
      "rule": "img-alt",
      "detail": "<img src='../assets/logo.svg'> has no alt attribute"
    },
    {
      "rule": "control-label",
      "line": 29,
      "detail": "<input> has no accessible label"
    },
    {
      "rule": "heading-skip",
      "detail": "heading jumps from h1 to h3"
    }
  ],
  "passed": false,
  "note": "3 accessibility violation(s) \u2014 see list (deterministic subset; manual review still advised)"
}
```

## `links before/index.html` -> exit 1

```json
{
  "check": "links",
  "html": "examples/frontend_demo/before/index.html",
  "checked": 3,
  "external_skipped": 0,
  "broken_count": 1,
  "broken": [
    {
      "kind": "a",
      "ref": "#main",
      "detail": "no element with id='main'"
    }
  ],
  "passed": false,
  "note": "1 broken internal reference(s)"
}
```

## `responsive before/index.html` -> exit 1

```json
{
  "check": "responsive",
  "html": "examples/frontend_demo/before/index.html",
  "has_viewport_meta": false,
  "media_query_count": 0,
  "css_scanned": [
    "examples/frontend_demo/before/style.css"
  ],
  "passed": false,
  "note": "no <meta name=viewport> \u2014 page won't adapt on mobile; no @media query found \u2014 no responsive breakpoints"
}
```

## `budget before/index.html --max-bytes 3000` -> exit 1

```json
{
  "check": "budget",
  "html": "examples/frontend_demo/before/index.html",
  "html_bytes": 4121,
  "asset_bytes": 621,
  "total_bytes": 4742,
  "element_count": 17,
  "request_count": 2,
  "assets": [
    {
      "url": "style.css",
      "bytes": 334
    },
    {
      "url": "../assets/logo.svg",
      "bytes": 287
    }
  ],
  "max_bytes": 3000,
  "max_elements": null,
  "max_requests": null,
  "passed": false,
  "note": "total 4742 bytes > budget 3000"
}
```
