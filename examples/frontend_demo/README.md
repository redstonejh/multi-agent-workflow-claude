# Front-end pack demo — defects caught, then fixed

A tiny static page (an "Acme" signup form) used to prove the front-end pack's
deterministic gates (`maw-tools/web_checks.py`) actually fire on real defects and
clear once the page is fixed. Everything here is computed — no browser, no npm.

```
frontend_demo/
├── before/index.html   # the defective draft — every gate RED
├── before/style.css    # low-contrast .btn (#9aa0a6 on #fff)
├── index.html          # the fixed page — every gate GREEN
├── style.css           # fixed .btn (#fff on #1558b0) + an @media breakpoint
└── assets/logo.svg     # a real asset so links/budget resolve
```

## The six planted defects (and the gate that catches each)

| # | Planted defect (in `before/`) | Gate | Computed result |
|---|---|---|---|
| 1 | low-contrast button `#9aa0a6` on `#ffffff` | `contrast` | **2.64:1** < 4.5 → FAIL |
| 2 | `<img>` with no `alt` | `a11y` | `img-alt` violation |
| 3 | heading jumps `h1` → `h3` | `a11y` | `heading-skip` violation |
| 4 | no `<meta name="viewport">` | `responsive` | viewport missing → FAIL |
| 5 | broken internal anchor `href="#main"` | `links` | no element `id="main"` → FAIL |
| 6 | over-budget inline blob | `budget` | **4742 B** > 3000 → FAIL |

(`before/` also has an unlabeled `<input>`, so the a11y count is **3**.)

## Reproduce it

```bash
# BEFORE — the gates fire (each exits non-zero)
uv run python maw-tools/web_checks.py contrast --fg "#9aa0a6" --bg "#ffffff"
uv run python maw-tools/web_checks.py a11y       --html examples/frontend_demo/before/index.html
uv run python maw-tools/web_checks.py links      --html examples/frontend_demo/before/index.html
uv run python maw-tools/web_checks.py responsive --html examples/frontend_demo/before/index.html --css examples/frontend_demo/before/style.css
uv run python maw-tools/web_checks.py budget     --html examples/frontend_demo/before/index.html --max-bytes 3000

# AFTER — the fixed page clears every gate (each exits 0)
uv run python maw-tools/web_checks.py a11y       --html examples/frontend_demo/index.html
uv run python maw-tools/web_checks.py budget     --html examples/frontend_demo/index.html --max-bytes 3000
uv run python maw-tools/web_checks.py contrast   --fg "#ffffff" --bg "#1558b0"
```

The before/after numbers are pinned in `maw-tools/selftest_all.py` (§5) and the
per-tool verdicts in `maw-tools/selftest_web_checks.py`, so this demo cannot
silently drift from what the code produces. The full worked run is committed at
`runs/2026-06-02_frontend-demo_c53d/`.

## What this demo does NOT prove — # MAW-TODO

These gates are **source-level and deterministic**. They do **not** render the
page. "Does it actually *look* right / lay out correctly in a real browser" is
visual-regression, which needs the Chrome connector or a headless-browser dep and
is **# MAW-TODO**. The `ux_critic` gives an *advisory* aesthetic read; it is not a
hard gate. The hard gates are the computed checks above.
