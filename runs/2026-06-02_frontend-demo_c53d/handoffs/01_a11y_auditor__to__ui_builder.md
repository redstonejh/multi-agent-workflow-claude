# Hand-off: a11y_auditor → ui_builder  (run 2026-06-02_frontend-demo_c53d, step 01)

## Task context
Ship an accessible Acme signup page that clears every deterministic front-end gate.

## What I did
Ran the deterministic gates on the first draft (preserved at
`examples/frontend_demo/before/`). Full JSON in `artifacts/audit_before.md`.

## Output / artifacts
- `artifacts/audit_before.md` — raw `web_checks.py` output, all RED:
  - **contrast** `.btn` `#9aa0a6` on `#ffffff` = **2.64:1** (needs >= 4.5)
  - **a11y** = **3**: `img-alt` (logo), `control-label` (email input), `heading-skip` (h1->h3)
  - **links** broken `#main` anchor (no element with that id)
  - **responsive** no `<meta name="viewport">`
  - **budget** 4742 B > 3000 B (an inline analytics blob)

## Open questions / risks
The contrast tool takes hex pairs — pick a button background that *computes* >= 4.5
against white text, don't eyeball it.

## Recommended next step
Fix each: add `alt`, wrap the input in a `<label>`, demote h3->h2, add the viewport
meta, drop the inline blob, add a real `#main` target + an `@media` breakpoint, and
recolor `.btn` to white on `#1558b0`. Then ask the auditors to re-run.
