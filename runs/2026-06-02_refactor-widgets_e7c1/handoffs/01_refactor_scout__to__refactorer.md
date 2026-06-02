# Hand-off: refactor_scout → refactorer  (run 2026-06-02_refactor-widgets_e7c1, step 01)

## Task context
Split the bloated `widgets.py` into cohesive modules without changing behavior.

## What I did
Ran the bloat trigger and grouped the eight public functions by shared symbols.

## Output / artifacts
- `artifacts/trigger.md` — `bloat bloated/widgets.py --max-loc 80 --max-defs 5` →
  **exit 1** (loc 110 > 80, defs 9 > 5).
- Proposed split (each cluster = functions that share private helpers/constants):
  | new module | public names | shared symbol that moves with them |
  |---|---|---|
  | `text`  | slugify, shout | `_normalize_ws` |
  | `mathx` | gcd, lcm | (lcm calls gcd) |
  | `listx` | chunk, flatten | — |
  | `money` | format_cents, parse_cents | `CENTS_PER_DOLLAR` |

## Open questions / risks
No symbol crosses two clusters, so no `_common` module is needed — clean seams.
The original `widgets` MUST keep its 8-name public surface and identical `__all__`.

## Recommended next step
**Snapshot before you edit:** capture `api_before.json` + `golden_before.json` +
green tests from `bloated/`. Then make `widgets` a package re-exporting all 8 names,
move each cluster, and re-run the equivalence gate. Any api/golden/test diff → revert.
