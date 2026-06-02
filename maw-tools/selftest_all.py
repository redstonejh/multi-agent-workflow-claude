#!/usr/bin/env python3
"""selftest_all.py - run the whole framework against itself and assert VALUES.

The per-tool self-tests (`selftest_checks.py`, `selftest_ml_checks.py`) prove the
checks' verdicts and exit codes are correct. This harness goes one level up: it
runs the framework end to end and asserts the *documented numbers actually
reproduce* - the train/test accuracies, the leakage-control signal, the baseline
gain, the calibration error - and then **dogfoods** by re-deriving the numbers the
committed run folder claims and asserting they still match reality. So neither the
worked example nor its write-up can silently drift from what the code produces.

Pure standard library. Run:  uv run python maw-tools/selftest_all.py
Exit 0 only if every assertion holds; non-zero otherwise.

If a documented number stops reproducing, the failure line prints BOTH the
expected and the real value - update the constant below only after confirming the
change is a legitimate model/seed change, not a regression.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAWTOOLS = ROOT / "maw-tools"
CHECKS = MAWTOOLS / "checks.py"
ML_CHECKS = MAWTOOLS / "ml_checks.py"
CODE_CHECKS = MAWTOOLS / "code_checks.py"
WEB_CHECKS = MAWTOOLS / "web_checks.py"
PLAN_CHECK = MAWTOOLS / "plan_check.py"
SELFTEST_CHECKS = MAWTOOLS / "selftest_checks.py"
SELFTEST_ML = MAWTOOLS / "selftest_ml_checks.py"
SELFTEST_CODE = MAWTOOLS / "selftest_code_checks.py"
SELFTEST_WEB = MAWTOOLS / "selftest_web_checks.py"
SELFTEST_PLAN = MAWTOOLS / "selftest_plan_check.py"
SAMPLE_APP = ROOT / "examples" / "sample_app"
TRAIN = ROOT / "examples" / "ml_experiment" / "train.py"
DATA = ROOT / "examples" / "ml_experiment" / "data.csv"
DEMO = ROOT / "examples" / "coupling_demo"          # code-work pack demo
EXPECT_DEDUPE_REFS = 4                               # refs sites for dedupe_orders
RUN_DIR = ROOT / "runs" / "2026-06-01_ml-leakage-demo_81f1"

# --- Front-end pack demo (examples/frontend_demo): before -> after. The byte    ---
# --- counts are pinned, so .gitattributes forces LF for that dir (no CRLF drift)---
FE_DEMO = ROOT / "examples" / "frontend_demo"
FE_BEFORE = FE_DEMO / "before" / "index.html"
FE_BEFORE_CSS = FE_DEMO / "before" / "style.css"
FE_AFTER = FE_DEMO / "index.html"
FE_AFTER_CSS = FE_DEMO / "style.css"
EXPECT_CONTRAST_BAD   = 2.6405   # WCAG ratio of #9aa0a6 text on #ffffff (fails 4.5)
EXPECT_CONTRAST_FIXED = 6.8747   # WCAG ratio of #ffffff text on #1558b0 (passes)
EXPECT_A11Y_BEFORE    = 3        # img-alt + control-label + heading-skip
EXPECT_A11Y_AFTER     = 0        # all fixed
EXPECT_BYTES_BEFORE   = 4742     # over-budget (inline blob) — fails the 3000 budget
EXPECT_BYTES_AFTER    = 1838     # under the 3000-byte budget after the fix
FE_BUDGET             = 3000     # the page byte budget the demo is checked against

# --- Change-verification + style-drift demo (examples/change_demo) ---
CHG_DEMO = ROOT / "examples" / "change_demo"
CHG_TOKENS = CHG_DEMO / "design-tokens.json"
CHG_BEFORE = CHG_DEMO / "before" / "button.css"
CHG_AFTER = CHG_DEMO / "after" / "button.css"
CHG_NOOP = CHG_DEMO / "noop" / "button.css"     # edit claimed but not applied
CHG_DRIFT = CHG_DEMO / "drift" / "button.css"   # changed, but off-palette color
EXPECT_STYLE_BEFORE = "#e0e0e0"   # .btn background before the requested change
EXPECT_STYLE_AFTER  = "#1a73e8"   # .btn background after ("make it blue #1a73e8")

# --- Pre-execution plan gate demo (runs/.../plan-gate): v1 rejected -> v2 accepted ---
PLAN_RUN = ROOT / "runs" / "2026-06-02_plan-gate_10b8"
PLAN_V1 = PLAN_RUN / "artifacts" / "plan_v1.json"   # ML plan missing leakage_auditor
PLAN_V2 = PLAN_RUN / "artifacts" / "plan_v2.json"   # corrected plan
PLAN_MISSING_ROLE = "leakage_auditor"               # the required role v1 omits

# --- Expected values (seeded -> exact-ish). If the model/seed legitimately      ---
# --- changes, this block is the ONE place to update. Each has a one-line why.   ---
TOL = 0.005                # float tolerance for the seeded-but-exact-ish numbers
EXPECT_LEAKY_TRAIN    = 1.0       # leaky pipeline memorizes via the planted `leak`
EXPECT_LEAKY_TEST     = 1.0       # leak inflates test too -> perfect, zero gap
EXPECT_LEAKY_SHUFFLE  = 1.0       # control on shuffled labels still ~1.0 -> leak signal
EXPECT_HONEST_TRAIN   = 0.742857  # seed-7 stdlib logreg on x1,x2,x3 (train)
EXPECT_HONEST_TEST    = 0.783333  # seed-7 stdlib logreg on x1,x2,x3 (held-out)
EXPECT_HONEST_SHUFFLE = 0.45      # honest control collapses to ~chance
EXPECT_CHANCE_REAL    = 0.541667  # majority base rate, real test split
EXPECT_CHANCE_CONTROL = 0.575     # majority base rate, shuffled test split
EXPECT_GAIN           = 0.241667  # honest model acc - majority baseline
EXPECT_ECE            = 0.063505  # calibration error, honest model
ECE_MAX               = 0.10      # calibration gate tolerance (docs/06)
GAP_TOL               = 0.05      # overfitting gate tolerance
SHUFFLE_TOL           = 0.05      # leakage gate tolerance
BASELINE_ITERS        = 2000      # bootstrap/permutation iters (matches the committed run)
BASELINE_SEED         = 0         # baseline RNG seed (matches the committed run)
# --- the six newer validators (Phase 3.7 completion) ---
EXPECT_HONEST_F1      = 0.759259  # F1 of the honest model on the held-out split
EXPECT_DATA_SHA256    = "8ad4393ac0946c1e116703dca2732e11a796c6fdb0be24b74276880882fe9fb4"  # sha256 of data.csv
EXPECT_DATA_MAJORITY  = 0.5325    # majority-class fraction in data.csv (213/400)
EXPECT_ROBUST_MAXCORR = 0.36065   # max |feature-label corr| in data.csv (no dominance)
EXPECT_VAR_MEAN       = 0.756667  # mean held-out acc over VARIANCE_SEEDS
VARIANCE_SEEDS        = [1, 2, 3, 7, 11]   # seeds swept for the multi-seed variance check

results: list[tuple[bool, str]] = []


def record(ok: bool, msg: str) -> None:
    results.append((bool(ok), msg))
    print(f"  {'[ok]' if ok else '[XX]'} {msg}")


def section(title: str) -> None:
    print(f"\n{title}")


def close(actual, expected, label: str, tol: float = TOL) -> bool:
    try:
        ok = abs(float(actual) - float(expected)) <= tol
    except (TypeError, ValueError):
        ok = False
    record(ok, f"{label}: got {actual}, expect {expected} +/-{tol}")
    return ok


def run(*args, cwd=None) -> tuple[int, str, str]:
    """Run `python <args>` with the SAME interpreter running this harness."""
    proc = subprocess.run(
        [sys.executable, *[str(a) for a in args]],
        capture_output=True, text=True, cwd=str(cwd) if cwd else None,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_json(*args) -> tuple[int, dict | None]:
    code, out, _ = run(*args)
    try:
        return code, json.loads(out)
    except json.JSONDecodeError:
        return code, None


def train(mode_args: list[str], artifacts_dir: Path) -> dict:
    code, data = run_json(TRAIN, "--artifacts-dir", artifacts_dir, *mode_args)
    if code != 0 or data is None:
        record(False, f"train.py {' '.join(mode_args) or '(honest)'} ran (exit {code})")
        return {}
    return data


def floats(text: str, pattern: str) -> list[float] | None:
    m = re.search(pattern, text)
    return [float(g) for g in m.groups()] if m else None


# --------------------------------------------------------------------------- #
# 1. The existing per-tool self-tests must pass (verdicts + exit codes)
# --------------------------------------------------------------------------- #

def part_selftests() -> None:
    section("1. Per-tool self-tests (must pass)")
    code, out, _ = run(SELFTEST_CHECKS)
    record(code == 0 and "4/4" in out and "ALL PASS" in out,
           f"selftest_checks.py -> exit {code}, 4/4 (want exit 0)")
    code, out, _ = run(SELFTEST_ML)
    record(code == 0 and "21/21" in out and "ALL PASS" in out,
           f"selftest_ml_checks.py -> exit {code}, 21/21 (want exit 0)")
    code, out, _ = run(SELFTEST_CODE)
    record(code == 0 and "10/10" in out and "ALL PASS" in out,
           f"selftest_code_checks.py -> exit {code}, 10/10 (want exit 0)")
    code, out, _ = run(SELFTEST_WEB)
    record(code == 0 and "27/27" in out and "ALL PASS" in out,
           f"selftest_web_checks.py -> exit {code}, 27/27 (want exit 0)")
    code, out, _ = run(SELFTEST_PLAN)
    record(code == 0 and "16/16" in out and "ALL PASS" in out,
           f"selftest_plan_check.py -> exit {code}, 16/16 (want exit 0)")


# --------------------------------------------------------------------------- #
# 2. Reproduce the code example through the framework's test gate
# --------------------------------------------------------------------------- #

def part_code_sample() -> None:
    section("2. Code example (examples/sample_app) through checks.py test")
    cmd = f'"{sys.executable}" test_textutil.py'
    code, data = run_json(CHECKS, "test", "--cmd", cmd, "--cwd", SAMPLE_APP)
    passed = bool(data and data.get("passed") is True and data.get("exit_code") == 0)
    record(code == 0 and passed,
           f"test_textutil.py via gate -> gate-exit {code}, passed={data and data.get('passed')}, "
           f"inner-exit {data and data.get('exit_code')} (want passed=true, exit 0)")


# --------------------------------------------------------------------------- #
# 3. Reproduce the ML example and pin the documented numbers
# --------------------------------------------------------------------------- #

def part_ml_example(tmp: Path) -> dict:
    section("3. ML example (examples/ml_experiment) - reproduce documented numbers")
    art = tmp / "fresh"
    art.mkdir()

    # --- leaky run: perfect + zero gap; the gap gate is fooled, shuffle catches it
    leaky = train(["--inject-leak"], art)
    close(leaky.get("train_acc"), EXPECT_LEAKY_TRAIN, "leaky train_acc")
    close(leaky.get("test_acc"), EXPECT_LEAKY_TEST, "leaky test_acc")

    leaky_ctrl = train(["--inject-leak", "--shuffle-labels"], art)
    close(leaky_ctrl.get("shuffled_label_acc"), EXPECT_LEAKY_SHUFFLE, "leaky shuffled_label_acc")
    close(leaky_ctrl.get("chance_level"), EXPECT_CHANCE_CONTROL, "control chance_level")
    # the leak gate must FIRE on the leaky control (exit 1)
    code, _ = run_json(ML_CHECKS, "shuffle",
                       "--shuffled-acc", leaky_ctrl.get("shuffled_label_acc", -1),
                       "--chance", leaky_ctrl.get("chance_level", -1),
                       "--tol", SHUFFLE_TOL)
    record(code == 1, f"ml_checks shuffle on leaky control -> exit {code} (want 1: leak gate fires)")

    # --- honest run: believable accuracy, all gates pass
    honest = train([], art)  # writes test_preds/labels/probs.txt into `art`
    close(honest.get("train_acc"), EXPECT_HONEST_TRAIN, "honest train_acc")
    close(honest.get("test_acc"), EXPECT_HONEST_TEST, "honest test_acc")

    code, _ = run_json(ML_CHECKS, "gap",
                       "--train", honest.get("train_acc", 0), "--test", honest.get("test_acc", 0),
                       "--tol", GAP_TOL)
    record(code == 0, f"ml_checks gap on honest model -> exit {code} (want 0: no overfitting)")

    honest_ctrl = train(["--shuffle-labels"], art)
    close(honest_ctrl.get("shuffled_label_acc"), EXPECT_HONEST_SHUFFLE, "honest shuffled_label_acc")
    code, _ = run_json(ML_CHECKS, "shuffle",
                       "--shuffled-acc", honest_ctrl.get("shuffled_label_acc", -1),
                       "--chance", honest_ctrl.get("chance_level", -1),
                       "--tol", SHUFFLE_TOL)
    record(code == 0, f"ml_checks shuffle on honest control -> exit {code} (want 0: clean)")

    # honest run wrote the arrays; baseline + ece read them back
    preds = art / "test_preds.txt"
    labels = art / "test_labels.txt"
    probs = art / "test_probs.txt"
    code, base = run_json(ML_CHECKS, "baseline", "--preds-file", preds, "--labels-file", labels,
                          "--iters", BASELINE_ITERS, "--seed", BASELINE_SEED)
    if base:
        close(base.get("gain"), EXPECT_GAIN, "baseline gain")
        ci_low = (base.get("gain_ci") or [None])[0]
        record(code == 0 and ci_low is not None and ci_low > 0,
               f"baseline gain CI excludes 0 -> exit {code}, ci_low={ci_low} (want exit 0, ci_low>0)")
    else:
        record(False, "baseline check produced no JSON")

    code, ece = run_json(ML_CHECKS, "ece", "--probs-file", probs, "--labels-file", labels,
                         "--bins", 10, "--tol", ECE_MAX)
    if ece:
        close(ece.get("ece"), EXPECT_ECE, "ece value")
        record(code == 0 and ece.get("ece", 1) <= ECE_MAX,
               f"ece within tolerance -> exit {code}, ece={ece.get('ece')} (want exit 0, <={ECE_MAX})")
    else:
        record(False, "ece check produced no JSON")

    # --- the six newer validators (Phase 3.7 completion), exercised on a fresh
    # honest run in its OWN dir so the claim-to-evidence arrays above stay intact ---
    section("3b. ML example - the six newer validators")
    nv = tmp / "validators"
    nv.mkdir()
    train([], nv)  # fresh honest run -> nv/test_*.txt + nv/metrics.json (seed 7)
    nv_preds, nv_labels = nv / "test_preds.txt", nv / "test_labels.txt"
    nv_probs, nv_metrics = nv / "test_probs.txt", nv / "metrics.json"

    code, met = run_json(ML_CHECKS, "metrics", "--preds-file", nv_preds, "--labels-file", nv_labels)
    if met:
        close(met.get("f1"), EXPECT_HONEST_F1, "metric_validator: F1")
        record(code == 0 and met.get("passed") is True,
               f"metric_validator: acc {met.get('accuracy')} > base {met.get('majority_base_rate')} "
               f"-> exit {code} (want 0)")
    else:
        record(False, "metrics check produced no JSON")

    # calibration_checker reuses ece (already asserted above); re-run for completeness
    code, cal = run_json(ML_CHECKS, "ece", "--probs-file", nv_probs, "--labels-file", nv_labels,
                         "--bins", 10, "--tol", ECE_MAX)
    record(bool(cal) and code == 0 and cal.get("passed") is True,
           f"calibration_checker (ece): ece={cal and cal.get('ece')} -> exit {code} (want 0)")

    code, dq = run_json(ML_CHECKS, "dataquality", "--data", DATA)
    if dq:
        close(dq.get("majority_fraction"), EXPECT_DATA_MAJORITY, "data_quality_auditor: majority fraction")
        record(code == 0 and dq.get("duplicate_rows") == 0 and dq.get("missing_cells") == 0,
               f"data_quality_auditor: dupes={dq.get('duplicate_rows')}, "
               f"missing={dq.get('missing_cells')} -> exit {code} (want 0)")
    else:
        record(False, "dataquality check produced no JSON")

    code, rob = run_json(ML_CHECKS, "robustness", "--data", DATA)
    if rob:
        close(rob.get("max_abs_corr"), EXPECT_ROBUST_MAXCORR, "robustness_tester: max |corr|")
        record(code == 0 and rob.get("passed") is True,
               f"robustness_tester: dominant={rob.get('dominant_feature')} "
               f"|corr|={rob.get('max_abs_corr')} -> exit {code} (want 0)")
    else:
        record(False, "robustness check produced no JSON")

    code, rep = run_json(ML_CHECKS, "repro", "--data", DATA, "--metrics", nv_metrics,
                         "--expect-sha", EXPECT_DATA_SHA256)
    if rep:
        record(rep.get("data_sha256") == EXPECT_DATA_SHA256,
               f"reproducibility_checker: data sha256 == pinned ({EXPECT_DATA_SHA256[:12]}...)")
        record(code == 0 and rep.get("has_seed") is True and rep.get("seed") == 7,
               f"reproducibility_checker: seed={rep.get('seed')}, "
               f"sha_matches={rep.get('sha_matches')} -> exit {code} (want 0)")
    else:
        record(False, "repro check produced no JSON")

    # variance_auditor: sweep seeds into a separate dir, test stability + real gain
    var_art = tmp / "variance"
    var_art.mkdir()
    accs = []
    for s in VARIANCE_SEEDS:
        r = train(["--seed", str(s)], var_art)
        if r:
            accs.append(r.get("test_acc"))
    code, var = run_json(ML_CHECKS, "variance", *[str(a) for a in accs],
                         "--baseline", EXPECT_CHANCE_REAL, "--max-std", "0.05")
    if var:
        close(var.get("mean"), EXPECT_VAR_MEAN, "variance_auditor: mean over seeds")
        record(code == 0 and var.get("passed") is True,
               f"variance_auditor: mean {var.get('mean')} std {var.get('std')} "
               f"gain {var.get('gain_over_baseline')} -> exit {code} (want 0)")
    else:
        record(False, "variance check produced no JSON")

    # hand the freshly-produced arrays to the claim-to-evidence stage
    return {"preds": preds.read_text(encoding="utf-8").split(),
            "labels": labels.read_text(encoding="utf-8").split(),
            "probs": probs.read_text(encoding="utf-8").split(),
            "honest": honest, "leaky": leaky, "leaky_ctrl": leaky_ctrl, "honest_ctrl": honest_ctrl}


# --------------------------------------------------------------------------- #
# 3c. Code-work pack: the coupling demo (hidden dep + bug/RCA docs)
# --------------------------------------------------------------------------- #

def part_code_pack() -> None:
    section("3c. Code-work pack (examples/coupling_demo)")
    dup_case = ("o=[{'id':3},{'id':1},{'id':3},{'id':1},{'id':2}]; "
                "from pipeline import process; print([x['id'] for x in process(o%s)])")

    # regression test is RED on the buggy path (no pre-sort): duplicates survive
    code, out, _ = run("-c", dup_case % ", apply_sort=False", cwd=DEMO)
    record(code == 0 and out.strip() == "[3, 1, 3, 1, 2]",
           f"BUG-002 reproduces RED (apply_sort=False) -> {out.strip()} (want [3, 1, 3, 1, 2])")
    # ...and GREEN after the fix (default sorts first): all duplicates removed
    code, out, _ = run("-c", dup_case % "", cwd=DEMO)
    record(code == 0 and out.strip() == "[1, 2, 3]",
           f"BUG-002 fixed GREEN (default) -> {out.strip()} (want [1, 2, 3])")

    # the committed regression test passes through the code_checks test gate
    code, data = run_json(CODE_CHECKS, "test", "--cmd", f'"{sys.executable}" test_orders.py',
                          "--cwd", DEMO)
    record(code == 0 and bool(data) and data.get("passed") is True,
           f"test_orders.py via code_checks gate -> exit {code}, passed={data and data.get('passed')}")

    # refs computes the blast radius of the coupled symbol
    code, data = run_json(CODE_CHECKS, "refs", "--symbol", "dedupe_orders",
                          "--root", DEMO, "--expect", EXPECT_DEDUPE_REFS)
    record(code == 0 and bool(data) and data.get("ref_count") == EXPECT_DEDUPE_REFS,
           f"refs dedupe_orders -> {data and data.get('ref_count')} sites (want {EXPECT_DEDUPE_REFS})")

    # the demo tree compiles (no syntax / null-byte corruption)
    code, _ = run_json(CODE_CHECKS, "syntax", "--root", DEMO)
    record(code == 0, f"code_checks syntax on demo -> exit {code} (want 0)")

    # the coupling is captured in BOTH places, linked by the D01 id
    deps = (DEMO / "deps.md").read_text(encoding="utf-8")
    record("## D01" in deps and "dedupe_orders" in deps, "deps.md has the D01 entry")
    orders_src = (DEMO / "orders.py").read_text(encoding="utf-8")
    pipeline_src = (DEMO / "pipeline.py").read_text(encoding="utf-8")
    record("# MAW-DEP[D01]" in orders_src, "inline # MAW-DEP[D01] marker in orders.py")
    record("# MAW-DEP[D01]" in pipeline_src, "inline # MAW-DEP[D01] marker in pipeline.py")

    # the bug/RCA documentation system produced its artifacts
    record((ROOT / "bugs" / "BUG-002-unsorted-dedupe.md").exists(), "bugs/BUG-002 report exists")
    record((ROOT / "bugs" / "RCA-BUG-002-unsorted-dedupe.md").exists(), "bugs/RCA-BUG-002 exists")


# --------------------------------------------------------------------------- #
# 4. Claim-to-evidence: the committed run folder must still match reality
# --------------------------------------------------------------------------- #

def part_claim_to_evidence(fresh: dict) -> None:
    section("4. Claim-to-evidence - committed run folder vs fresh recomputation")
    if not RUN_DIR.is_dir():
        record(False, f"run folder missing: {RUN_DIR}")
        return

    def load(name: str) -> dict:
        try:
            return json.loads((RUN_DIR / "artifacts" / name).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            record(False, f"could not read committed artifacts/{name}")
            return {}

    # (a) committed metrics JSON == freshly recomputed metrics
    c_leaky = load("iter1_leaky_metrics.json")
    c_leaky_ctrl = load("iter1_leaky_control.json")
    c_honest = load("iter2_honest_metrics.json")
    c_honest_ctrl = load("iter2_honest_control.json")
    f = fresh
    close(c_leaky.get("test_acc"), f["leaky"].get("test_acc"), "committed leaky test_acc == fresh")
    close(c_leaky_ctrl.get("shuffled_label_acc"), f["leaky_ctrl"].get("shuffled_label_acc"),
          "committed leaky control == fresh")
    close(c_honest.get("train_acc"), f["honest"].get("train_acc"), "committed honest train_acc == fresh")
    close(c_honest.get("test_acc"), f["honest"].get("test_acc"), "committed honest test_acc == fresh")
    close(c_honest_ctrl.get("shuffled_label_acc"), f["honest_ctrl"].get("shuffled_label_acc"),
          "committed honest control == fresh")

    # (b) committed arrays reproduce bit-for-bit from a fresh honest run
    for key in ("preds", "labels", "probs"):
        committed = (RUN_DIR / "artifacts" / f"test_{key}.txt").read_text(encoding="utf-8").split()
        fresh_vals = f[key]
        same = len(committed) == len(fresh_vals) and all(
            abs(float(a) - float(b)) <= 1e-6 for a, b in zip(committed, fresh_vals))
        record(same, f"committed test_{key}.txt reproduces from fresh honest run "
                     f"({len(committed)} values)")

    # (c) the prose in run.md must match the recomputed numbers (no write-up drift)
    text = (RUN_DIR / "run.md").read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text).replace("*", "")
    honest_test = float(f["honest"]["test_acc"])
    honest_train = float(f["honest"]["train_acc"])

    pair = floats(flat, r"train ([\d.]+) / test ([\d.]+)")  # first hit = leaky 1.000/1.000
    record(pair is not None and abs(pair[0] - 1.0) <= TOL and abs(pair[1] - 1.0) <= TOL,
           f"run.md prose 'train X / test Y' leaky claim = {pair} (want ~[1.0, 1.0])")

    controls = re.findall(r"([\d.]+) vs ([\d.]+) chance", flat)
    got_leaky = controls and abs(float(controls[0][0]) - 1.0) <= TOL \
        and abs(float(controls[0][1]) - EXPECT_CHANCE_CONTROL) <= TOL
    got_honest = len(controls) > 1 and abs(float(controls[1][0]) - EXPECT_HONEST_SHUFFLE) <= TOL \
        and abs(float(controls[1][1]) - EXPECT_CHANCE_CONTROL) <= TOL
    record(bool(got_leaky), f"run.md prose leaky control claim = {controls[0] if controls else None} "
                            f"(want ~['1.0','0.575'])")
    record(bool(got_honest), f"run.md prose honest control claim = "
                             f"{controls[1] if len(controls) > 1 else None} (want ~['0.45','0.575'])")

    gap_claim = floats(flat, r"gap (-?[\d.]+)")
    record(gap_claim is not None and abs(gap_claim[0] - (honest_train - honest_test)) <= TOL,
           f"run.md prose gap claim = {gap_claim} (want ~{round(honest_train - honest_test, 3)})")

    base_claim = floats(flat, r"model ([\d.]+) vs majority ([\d.]+), gain \+?([\d.]+)")
    record(base_claim is not None
           and abs(base_claim[0] - honest_test) <= TOL
           and abs(base_claim[2] - EXPECT_GAIN) <= TOL,
           f"run.md prose baseline claim = {base_claim} (want ~[{round(honest_test,3)}, 0.542, 0.242])")

    ece_claim = floats(flat, r"ECE ([\d.]+)")
    record(ece_claim is not None and abs(ece_claim[0] - EXPECT_ECE) <= TOL,
           f"run.md prose ECE claim = {ece_claim} (want ~{EXPECT_ECE})")


# --------------------------------------------------------------------------- #
# 5. Front-end pack: the planted demo goes from RED (defects) to GREEN (fixed)
# --------------------------------------------------------------------------- #

def part_frontend_pack() -> None:
    section("5. Front-end pack (examples/frontend_demo) - before RED -> after GREEN")
    if not FE_BEFORE.is_file() or not FE_AFTER.is_file():
        record(False, f"frontend demo missing: {FE_DEMO}")
        return

    # contrast: the planted low-contrast pair is a fixed WCAG number; the fix clears it
    code, data = run_json(WEB_CHECKS, "contrast", "--fg", "#9aa0a6", "--bg", "#ffffff")
    if data:
        close(data.get("ratio"), EXPECT_CONTRAST_BAD, "contrast bad pair (#9aa0a6/#fff)")
        record(code == 1 and data.get("passed") is False,
               f"contrast bad pair fails AA -> exit {code} (want 1)")
    else:
        record(False, "contrast bad pair produced no JSON")
    code, data = run_json(WEB_CHECKS, "contrast", "--fg", "#ffffff", "--bg", "#1558b0")
    if data:
        close(data.get("ratio"), EXPECT_CONTRAST_FIXED, "contrast fixed pair (#fff/#1558b0)")
        record(code == 0 and data.get("passed") is True,
               f"contrast fixed pair passes AA -> exit {code} (want 0)")
    else:
        record(False, "contrast fixed pair produced no JSON")

    # a11y: violation count before vs after the fix
    code, data = run_json(WEB_CHECKS, "a11y", "--html", FE_BEFORE)
    record(bool(data) and code == 1 and data.get("violation_count") == EXPECT_A11Y_BEFORE,
           f"a11y BEFORE: {data and data.get('violation_count')} violations -> exit {code} "
           f"(want {EXPECT_A11Y_BEFORE}, fail)")
    code, data = run_json(WEB_CHECKS, "a11y", "--html", FE_AFTER)
    record(bool(data) and code == 0 and data.get("violation_count") == EXPECT_A11Y_AFTER,
           f"a11y AFTER: {data and data.get('violation_count')} violations -> exit {code} "
           f"(want {EXPECT_A11Y_AFTER}, pass)")

    # budget: the over-budget inline blob fails; the fixed page fits. Byte counts pinned.
    code, data = run_json(WEB_CHECKS, "budget", "--html", FE_BEFORE, "--max-bytes", FE_BUDGET)
    if data:
        record(data.get("total_bytes") == EXPECT_BYTES_BEFORE,
               f"budget BEFORE total_bytes={data.get('total_bytes')} (want {EXPECT_BYTES_BEFORE})")
        record(code == 1 and data.get("passed") is False,
               f"budget BEFORE over {FE_BUDGET}B -> exit {code} (want 1)")
    else:
        record(False, "budget BEFORE produced no JSON")
    code, data = run_json(WEB_CHECKS, "budget", "--html", FE_AFTER, "--max-bytes", FE_BUDGET)
    if data:
        record(data.get("total_bytes") == EXPECT_BYTES_AFTER,
               f"budget AFTER total_bytes={data.get('total_bytes')} (want {EXPECT_BYTES_AFTER})")
        record(code == 0 and data.get("passed") is True,
               f"budget AFTER within {FE_BUDGET}B -> exit {code} (want 0)")
    else:
        record(False, "budget AFTER produced no JSON")

    # links + responsive: defective page fails each gate, fixed page clears them
    code, _ = run_json(WEB_CHECKS, "links", "--html", FE_BEFORE)
    record(code == 1, f"links BEFORE (broken #anchor) -> exit {code} (want 1)")
    code, _ = run_json(WEB_CHECKS, "links", "--html", FE_AFTER)
    record(code == 0, f"links AFTER (all resolve) -> exit {code} (want 0)")
    code, _ = run_json(WEB_CHECKS, "responsive", "--html", FE_BEFORE, "--css", FE_BEFORE_CSS)
    record(code == 1, f"responsive BEFORE (no viewport) -> exit {code} (want 1)")
    code, _ = run_json(WEB_CHECKS, "responsive", "--html", FE_AFTER, "--css", FE_AFTER_CSS)
    record(code == 0, f"responsive AFTER (viewport + @media) -> exit {code} (want 0)")


# --------------------------------------------------------------------------- #
# 6. Change-verification + style-drift: a requested UI change is PROVABLY applied
# --------------------------------------------------------------------------- #

def part_change_verify() -> None:
    section("6. Change-verification + style-drift (examples/change_demo)")
    if not CHG_AFTER.is_file():
        record(False, f"change demo missing: {CHG_DEMO}")
        return

    # style: the exact before/after resolved values are pinned
    code, data = run_json(WEB_CHECKS, "style", "--css", CHG_BEFORE,
                          "--selector", ".btn", "--property", "background")
    record(bool(data) and data.get("value") == EXPECT_STYLE_BEFORE,
           f"style BEFORE .btn background = {data and data.get('value')} "
           f"(want {EXPECT_STYLE_BEFORE})")
    code, data = run_json(WEB_CHECKS, "style", "--css", CHG_AFTER,
                          "--selector", ".btn", "--property", "background")
    record(bool(data) and data.get("value") == EXPECT_STYLE_AFTER,
           f"style AFTER .btn background = {data and data.get('value')} "
           f"(want {EXPECT_STYLE_AFTER})")

    # changed: GREEN on the real edit (#e0e0e0 -> #1a73e8, matches expected)
    code, data = run_json(WEB_CHECKS, "changed", "--css", CHG_AFTER, "--selector", ".btn",
                          "--property", "background", "--before", EXPECT_STYLE_BEFORE,
                          "--expect", EXPECT_STYLE_AFTER)
    record(code == 0 and bool(data) and data.get("passed") is True,
           f"changed REAL edit -> exit {code}, passed={data and data.get('passed')} (want 0/True)")
    # changed: RED on the no-op (claimed but not applied)
    code, data = run_json(WEB_CHECKS, "changed", "--css", CHG_NOOP, "--selector", ".btn",
                          "--property", "background", "--before", EXPECT_STYLE_BEFORE,
                          "--expect", EXPECT_STYLE_AFTER)
    record(code == 1 and bool(data) and data.get("passed") is False
           and data.get("changed") is False,
           f"changed NO-OP -> exit {code}, changed={data and data.get('changed')} (want 1/False)")

    # tokens: GREEN on the on-palette fix, RED on the off-palette drift
    code, data = run_json(WEB_CHECKS, "tokens", "--css", CHG_AFTER, "--tokens", CHG_TOKENS)
    record(code == 0 and bool(data) and data.get("drift_count") == 0,
           f"tokens AFTER (on palette) -> exit {code}, drift={data and data.get('drift_count')} (want 0/0)")
    code, data = run_json(WEB_CHECKS, "tokens", "--css", CHG_DRIFT, "--tokens", CHG_TOKENS)
    record(code == 1 and bool(data) and data.get("drift_count") >= 1,
           f"tokens DRIFT (off palette) -> exit {code}, drift={data and data.get('drift_count')} (want 1/>=1)")


# --------------------------------------------------------------------------- #
# 7. Pre-execution plan gate: the conductor's bad plan is caught before running
# --------------------------------------------------------------------------- #

def part_plan_gate() -> None:
    section("7. Pre-execution plan gate (examples plan-gate run) - v1 RED -> v2 GREEN")
    if not PLAN_V1.is_file() or not PLAN_V2.is_file():
        record(False, f"plan-gate demo missing: {PLAN_RUN}")
        return

    # v1: an ML plan that omits the leakage_auditor must be REJECTED, naming the role
    code, data = run_json(PLAN_CHECK, "--plan", PLAN_V1)
    viol = " ".join(data.get("violations", [])) if data else ""
    record(code == 1 and bool(data) and data.get("passed") is False
           and PLAN_MISSING_ROLE in viol,
           f"plan v1 (ML, no {PLAN_MISSING_ROLE}) -> exit {code}, "
           f"violations={data and data.get('violation_count')} (want 1/REJECT naming it)")
    # the required-role rule must be the thing that fired
    record(bool(data) and any(PLAN_MISSING_ROLE in v and "requires role" in v
                              for v in (data.get("violations") or [])),
           f"plan v1 rejection is the ml required-role rule firing on {PLAN_MISSING_ROLE}")

    # v2: the corrected plan (leakage_auditor added) must be ACCEPTED
    code, data = run_json(PLAN_CHECK, "--plan", PLAN_V2)
    record(code == 0 and bool(data) and data.get("passed") is True
           and data.get("violation_count") == 0,
           f"plan v2 (corrected) -> exit {code}, "
           f"violations={data and data.get('violation_count')} (want 0/ACCEPT)")
    # and v2 actually contains the previously-missing role
    record(bool(data) and PLAN_MISSING_ROLE in (data.get("roles") or []),
           f"plan v2 now includes {PLAN_MISSING_ROLE}")


# --------------------------------------------------------------------------- #

def main() -> int:
    print("=" * 70)
    print("selftest_all.py - framework self-validation (asserts VALUES)")
    print("=" * 70)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        part_selftests()
        part_code_sample()
        fresh = part_ml_example(tmp)
        part_code_pack()
        if fresh:
            part_claim_to_evidence(fresh)
        else:
            record(False, "ML example did not produce arrays - skipped claim-to-evidence")
        part_frontend_pack()
        part_change_verify()
        part_plan_gate()

    passed = sum(1 for ok, _ in results if ok)
    total = len(results)
    print("\n" + "=" * 70)
    print(f"{'PASS' if passed == total else 'FAIL'} {passed}/{total} assertions held")
    print("=" * 70)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
