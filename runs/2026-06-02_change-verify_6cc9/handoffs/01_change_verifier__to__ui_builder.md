# Hand-off: change_verifier → ui_builder  (run 2026-06-02_change-verify_6cc9, step 01)

## Task context
Make the primary button blue (#1a73e8) and larger — and the change must be provable.

## What I did
Snapshotted the BEFORE state so the change is verifiable, before any edit:
`style before/button.css .btn { background }` = **#e0e0e0**, `font-size` = **0.75rem**.

## Output / artifacts
- `artifacts/change_report.md` — the recorded before-values + the exact requested change.
- Requested change (the gate I will enforce next):
  - `.btn { background }`: `#e0e0e0` -> **#1a73e8**
  - `.btn` larger: `font-size` `0.75rem` -> **1rem** (and bump padding)

## Open questions / risks
Use only colors/spacing/fonts in `examples/change_demo/design-tokens.json` — the
`style_drift_auditor` will fail the run on any off-palette value (e.g. a stray blue).

## Recommended next step
Edit `examples/change_demo/after/button.css` to apply both changes, then hand back
so I can run `changed` (it must report `changed: true` and match the expected value).
