#!/usr/bin/env python3
"""EXP-0124 runner. Executes the frozen 85-case matrix (casematrix.py) one case per
process (SAFETY: this family can fault the context / crash the calling process; the
dispatch instructions require one case per process throughout), and writes gated/
non-gated sibling records under raw/<run_id>/. A NON-RECORDED smoke case runs first
(written under work/, never raw/); if it fails, no raw/ artifact is created at all
(standing gate (c)). After the fixed matrix, optionally also runs the separate
maxCommandCount bisection (harness/icbmax_bisect.py logic, invoked here so one `run.py`
call produces one complete run_id's evidence).

Usage:
  python3 run.py --run m4_<date>_run01 --out raw/m4_<date>_run01
  python3 run.py --list
"""
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import casematrix as CM
import schema as S
import icbmax_bisect as ICBMAX

QBENCH = EXP / "work" / "bin" / "qbench"
IBENCH = EXP / "work" / "bin" / "ibench"

RUN_TIMEOUT_S = 60   # comfortably above every observed case wall time (largest
                      # observed: i_cdm_large_16m at well under 5s; generous margin
                      # for a loaded host). Crash/abort cases return almost instantly.


def sh(cmd, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(EXP))
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return -9, (e.stdout or ""), (e.stderr or "") + "\nTIMEOUT", time.time() - t0


def parse_lines(stdout):
    status = None
    device = None
    observed = {}
    ticks = {}
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line[len("STATUS "):].strip()
        elif line.startswith("DEVICE "):
            device = line[len("DEVICE "):].strip()
        elif line.startswith("OBSERVED "):
            for tok in line[len("OBSERVED "):].split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    observed[k] = v
        elif line.startswith("TICKS "):
            for tok in line[len("TICKS "):].split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    ticks[k] = v
    return status, device, observed, ticks


def coerce(v):
    """Best-effort str->int/float/bool for OBSERVED/TICKS values (all printed by our
    own harness in a fixed, known format: decimal integers, or 0/1 for booleans)."""
    if v in ("0", "1"):
        return int(v)
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def binary_for(family):
    return str(QBENCH) if family.startswith("q_") else str(IBENCH)


# Kinds whose ObjC harness already computes an explicit correctness verdict as one
# or more OBSERVED boolean fields (name ends in one of these suffixes). For these,
# PASS requires status==OK AND every such field == 1.
_VERDICT_FIELD_SUFFIXES = ("Match", "match", "Ok", "ok", "Correct", "correct",
                           "NoError", "Painted", "Used", "IsClear")

# Kinds that are purely observational/descriptive (boundary mapping, census,
# availability semantics) -- PASS whenever status is one of the case's own allowed
# statuses; there is no "correct" numeric answer to check.
_OBSERVATIONAL_KINDS = {
    "q_caps", "q_alloc_sweep", "q_alloc_mode", "q_avail", "q_reset_idempotent",
    "q_reset_reuse", "q_tick", "i_cdm_sweep", "i_cdm_zeroaxis", "i_cdm_offset",
}


def default_verdict(kind, params, status, observed):
    if params.get("expect_crash") or params.get("expect_abort"):
        # Handled entirely by the crash-path branch in run_case(); should not
        # reach here (status is None/absent on a real crash).
        return "PASS" if status is None else "FAIL"
    if kind == "i_icbb_trial" and not params.get("barrier", True):
        # Matches EXP-0098's h_sync convention exactly: a single unbarriered trial's
        # race outcome is genuinely nondeterministic GPU-scheduling behavior, not a
        # pass/fail correctness question -- the FAMILY-level race rate (computed in
        # RESULTS.md across all 16 trials x 2 runs) is the promoted claim, not any
        # one trial. The barriered case (H-I5's positive claim) IS judged PASS/FAIL.
        return "N/A" if status == "OK" else "FAIL"
    if kind in _OBSERVATIONAL_KINDS:
        return "PASS" if status in ("OK", "ALLOC_REJECTED") else "FAIL"
    if status != "OK":
        return "FAIL"
    for k, v in observed.items():
        if any(k.endswith(suf) for suf in _VERDICT_FIELD_SUFFIXES):
            if coerce(v) not in (1, True):
                return "FAIL"
    return "PASS"


def run_case(case):
    fam = case["family"]; kind = case["kind"]; p = case["params"]
    binn = binary_for(fam)
    cmd = [binn, kind, json.dumps(p)]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)

    if p.get("expect_crash") or p.get("expect_abort"):
        crashed = rc not in (0, 1)
        gated = {"case_id": case["id"], "family": fam, "kind": kind, "params": p,
                 "status": "HARNESS_CRASH" if crashed else "OK",
                 "verdict": "PASS" if crashed else "FAIL",
                 "observed": {"crashedAsExpected": int(crashed)}}
        ngated = {"case_id": case["id"], "wall_ms": round(wall*1000, 3), "pid": os.getpid(),
                  "raw_tail": (out[-300:] + err[-300:]), "raw_ticks": {}}
        return gated, ngated

    status, device, observed, ticks = parse_lines(out)
    if status is None:
        status = "HANG" if rc == -9 else "HARNESS_CRASH"
    observed_c = {k: coerce(v) for k, v in observed.items()}
    verdict = default_verdict(kind, p, status, observed_c)
    gated = {"case_id": case["id"], "family": fam, "kind": kind, "params": p,
             "status": status, "verdict": verdict, "observed": observed_c}
    ok, msg = S.validate_gated(gated)
    if not ok:
        raise RuntimeError(f"schema violation for {case['id']}: {msg}")
    ngated = {"case_id": case["id"], "wall_ms": round(wall*1000, 3), "pid": os.getpid(),
              "raw_tail": (out[-300:] + err[-300:]), "raw_ticks": {k: coerce(v) for k, v in ticks.items()}}
    return gated, ngated


def run_smoke():
    """NON-RECORDED smoke gate: one trivial real GPU dispatch via each binary,
    checked BEFORE any raw/ directory is created (standing gate (c))."""
    receipt = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    rc1, out1, err1, w1 = sh([str(QBENCH), "q_caps", "{}"], 20)
    rc2, out2, err2, w2 = sh([str(IBENCH), "i_cdm_axisproof", "{}"], 20)
    ok = (rc1 == 0 and "STATUS OK" in out1) and (rc2 == 0 and "STATUS OK" in out2)
    receipt.update({"qbench_rc": rc1, "qbench_ok": "STATUS OK" in out1,
                     "ibench_rc": rc2, "ibench_ok": "STATUS OK" in out2,
                     "qbench_tail": out1[-300:], "ibench_tail": out2[-300:]})
    return ok, receipt


def git_revision():
    try:
        rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              cwd=str(EXP)).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                                cwd=str(EXP)).stdout.strip() != ""
        return rev, dirty
    except Exception:
        return None, None


def sha256_file(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def authored_files():
    return ["harness/schema.py", "harness/casematrix.py", "harness/run.py",
            "harness/verify.py", "harness/icbmax_bisect.py",
            "harness/qbench.m", "harness/ibench.m",
            "kernels/q_common.metal", "kernels/i_common.metal"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--out")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--skip-icbmax", action="store_true",
                     help="skip the maxCommandCount bisection (debug/dry-run only)")
    args = ap.parse_args()

    if args.list:
        for c in CM.MATRIX:
            print(c["id"], c["family"], c["kind"])
        print(f"TOTAL {CM.TOTAL}")
        return

    if not args.run or not args.out:
        print("need --run and --out (or --list)", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out)
    if out_dir.exists():
        print(f"FAIL: raw dir already exists: {out_dir}", file=sys.stderr)
        sys.exit(2)

    work_dir = EXP / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    smoke_ok, smoke_receipt = run_smoke()
    (work_dir / f"{args.run}_smoke.json").write_text(json.dumps(smoke_receipt, indent=2))
    if not smoke_ok:
        print("FAIL: smoke gate failed, no raw/ artifact written", file=sys.stderr)
        sys.exit(1)
    print("SMOKE OK")

    rev, dirty = git_revision()
    inputs = {
        "run_id": args.run,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_revision_pinned": rev,
        "git_dirty_tracked": dirty,
        "authored_file_hashes": {f: sha256_file(EXP / f) for f in authored_files()},
        "total_cases": CM.TOTAL,
    }
    out_dir.mkdir(parents=True)
    (out_dir / "00_inputs.json").write_text(json.dumps(inputs, indent=2))

    gated_f = open(out_dir / "02_gated.jsonl", "a")
    nongated_f = open(out_dir / "03_nongated.jsonl", "a")
    counts = {"PASS": 0, "FAIL": 0, "TIMEOUT": 0, "N/A": 0}
    for i, case in enumerate(CM.MATRIX):
        try:
            gated, ngated = run_case(case)
        except Exception as e:
            gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
                      "params": case["params"], "status": "HARNESS_CRASH", "verdict": "FAIL",
                      "observed": {}}
            ngated = {"case_id": case["id"], "wall_ms": None, "pid": os.getpid(),
                      "raw_tail": repr(e)[:400], "raw_ticks": {}}
        ok, msg = S.validate_gated(gated)
        if not ok:
            raise RuntimeError(f"schema violation for case {case['id']}: {msg}")
        ok2, msg2 = S.validate_nongated(ngated)
        if not ok2:
            raise RuntimeError(f"schema violation (nongated) for case {case['id']}: {msg2}")
        gated_f.write(json.dumps(gated, sort_keys=True) + "\n"); gated_f.flush()
        nongated_f.write(json.dumps(ngated, sort_keys=True) + "\n"); nongated_f.flush()
        counts[gated["verdict"]] = counts.get(gated["verdict"], 0) + 1
        print(f"[{i+1}/{CM.TOTAL}] {case['id']}: status={gated['status']} verdict={gated['verdict']}")
    gated_f.close(); nongated_f.close()

    icbmax_summary = None
    if not args.skip_icbmax:
        print("Starting maxCommandCount bisection...")
        icbmax_summary = ICBMAX.run_bisection(out_dir / "05_icbmax_bisect.jsonl", IBENCH)
        print("Bisection converged:", icbmax_summary)

    manifest = {"run_id": args.run, "cases_planned": CM.TOTAL,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "verdict_counts": counts, "icbmax_bisection": icbmax_summary}
    (out_dir / "04_manifest.json").write_text(json.dumps(manifest, indent=2))
    print("DONE", counts)


if __name__ == "__main__":
    main()
