# Change-verification + style-drift demo

Proves that a **requested UI change was actually applied** — not just claimed —
and that the fix introduced **no style drift**. Everything is computed by
`maw-tools/web_checks.py` (`style`, `changed`, `tokens`) — pure stdlib, no browser.

The request: **"make the primary button blue (#1a73e8) and larger."**

```
change_demo/
├── design-tokens.json   # allowed colors / spacing / fonts (the palette)
├── before/button.css    # the pre-change snapshot: .btn background #e0e0e0, small
├── after/button.css     # the requested change applied: #1a73e8, larger (on-palette)
├── noop/button.css      # edit CLAIMED but not applied (still #e0e0e0)  -> NO-SHIP
└── drift/button.css     # changed, but painted off-palette #2b7de9      -> NO-SHIP
```

## (a) Happy path — the change is provably applied, no drift

```bash
# the value moved from the old to the requested value (and matches the expectation)
uv run python maw-tools/web_checks.py changed --css examples/change_demo/after/button.css \
    --selector .btn --property background --before "#e0e0e0" --expect "#1a73e8"     # exit 0

# ...and it got larger
uv run python maw-tools/web_checks.py changed --css examples/change_demo/after/button.css \
    --selector .btn --property font-size --before "0.75rem" --expect "1rem"          # exit 0

# exact before/after values, for the record
uv run python maw-tools/web_checks.py style --css examples/change_demo/before/button.css --selector .btn --property background  # #e0e0e0
uv run python maw-tools/web_checks.py style --css examples/change_demo/after/button.css  --selector .btn --property background  # #1a73e8

# no off-palette values were introduced
uv run python maw-tools/web_checks.py tokens --css examples/change_demo/after/button.css \
    --tokens examples/change_demo/design-tokens.json                                  # exit 0, drift 0
```

## (b) NO-SHIP — the gates catch a fake and a regression

```bash
# NO-OP: the agent said it made the button blue, but the file is unchanged
uv run python maw-tools/web_checks.py changed --css examples/change_demo/noop/button.css \
    --selector .btn --property background --before "#e0e0e0" --expect "#1a73e8"
# -> "changed": false, exit 1  ->  NO-SHIP (it better actually be changed)

# DRIFT: the button changed, but to an off-palette blue (#2b7de9 not in tokens)
uv run python maw-tools/web_checks.py tokens --css examples/change_demo/drift/button.css \
    --tokens examples/change_demo/design-tokens.json
# -> drift_count 1, exit 1  ->  NO-SHIP (no style drift allowed)
```

The before/after values and the RED/GREEN verdicts are pinned in
`maw-tools/selftest_all.py` (§6) and the per-tool verdicts in
`maw-tools/selftest_web_checks.py`, so this demo cannot silently drift from what
the code produces. The full worked run is committed at
`runs/2026-06-02_change-verify_6cc9/`.

## What this does NOT prove — # MAW-TODO

The `changed`/`style`/`tokens` gates verify the change **in the source**. They do
not render the page. Whether the button *visually* looks blue and larger is the
`visual_verifier`'s **advisory** job (model judgment); **full automated
screenshot-diff in the pipeline is `# MAW-TODO`** — it needs the Chrome connector
or a headless-browser dependency. The deterministic source diff stays the hard gate.
