# Worked example — ML validation catches a planted data leak

This is the Phase-3.7 demonstration (docs/06): an ML run where a **deliberately
planted data-leakage bug** is caught by the deterministic shuffled-label control,
blocked (**NO-SHIP**), fixed, and re-run to a genuine **SHIP** — with the full
populated run folder committed as evidence.

> All commands use `uv run python` because this machine has no `python` on PATH.
> Everything is **pure standard library** — no numpy, no sklearn, no network.

## The files

| File | What it is |
|---|---|
| `make_data.py` | deterministic (seed 42) generator for `data.csv` — 3 legit features with a real but moderate signal, **no leaky column** |
| `data.csv` | 400 rows, 53.2% majority base rate (committed so the demo is offline-reproducible) |
| `train.py` | tiny stdlib logistic-regression pipeline; writes `artifacts/metrics.json` + test arrays |
| `requirements.txt` | documents the zero-dependency choice |

## The planted bug

`train.py --inject-leak` adds a feature **derived from the label** in the
feature-engineering step (`leak = label`) — exactly how target leakage happens in
the wild. The fix is simply not creating that feature (the default run).

## Reproduce the whole demonstration

```bash
cd examples/ml_experiment

# 1. As-found (leaky): looks perfect — train 1.000 / test 1.000
uv run python train.py --inject-leak

# 2. The leakage canary: retrain on RANDOMIZED labels. With the leak present the
#    model still scores ~1.000 — it is learning random labels, the tell-tale sign.
uv run python train.py --inject-leak --shuffle-labels        # shuffled_label_acc ~1.0

# 3. Judge it deterministically (exit 1 = leakage):
uv run python ../../maw-tools/ml_checks.py shuffle --shuffled-acc 1.0 --chance 0.575 --tol 0.05

# 4. The fix (honest run): only legitimate features -> train 0.743 / test 0.783
uv run python train.py

# 5. Control now falls back to chance (exit 0 = clean):
uv run python train.py --shuffle-labels                       # shuffled_label_acc ~0.45
uv run python ../../maw-tools/ml_checks.py shuffle --shuffled-acc 0.45 --chance 0.575 --tol 0.05

# 6. The honest model genuinely beats its baseline and is calibrated:
uv run python ../../maw-tools/ml_checks.py baseline --preds-file artifacts/test_preds.txt --labels-file artifacts/test_labels.txt
uv run python ../../maw-tools/ml_checks.py ece      --probs-file artifacts/test_probs.txt --labels-file artifacts/test_labels.txt
uv run python ../../maw-tools/ml_checks.py gap      --train 0.742857 --test 0.783333 --tol 0.05
```

## Why the gap check alone is not enough

The leaky model's train-test gap is **0.0** (both 1.000) — the overfitting gate
waves it through. **Leakage inflates train and test together**, so only the
shuffled-label control catches it. That is the whole point of the ML validator
pack: the most impressive-looking metric is the one most likely to be an artifact.

## The committed run folder

The real `/ml-experiment` run that drove this lives at
[`runs/2026-06-01_ml-leakage-demo_81f1/`](../../runs/2026-06-01_ml-leakage-demo_81f1/):
the conductor plan + rubric (`run.md`), the timestamped journal (`memory.md`), the
hand-off chain (`handoffs/`, including the leakage critique looping back to the
worker), the per-validator reports and rubric scorecard (`artifacts/`), and the
**independent acceptance gate's** SHIP verdict (`artifacts/acceptance.md`) — which
re-ran every check itself against the on-disk artifacts rather than trusting the
validators.
