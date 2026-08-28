#!/usr/bin/env python3
"""EXP-0111 fail-closed verifier. Implements the dispatch's standing gate set
(pattern follows EXP-0091's verify.py):

  (a) --selftest   ONE authoritative shared key-set (schema.py), imported here and by
                    run.py, never restated. Fabricates synthetic captures (no Metal, no
                    device, no Apple binary) built from the FIELD SHAPES this
                    experiment's own pilot run actually produced (work/trial/*.json),
                    and proves: clean shapes pass; each broken shape fails for the right
                    reason; two synthetic captures with byte-identical *.gated.json but
                    different *.nongated.json (timing/pid) PASS the cross-run gate; a
                    semantic *.gated.json difference FAILS it. Never touches raw/.
                    Runnable in every tree state.
  (b) --seqtest     Walks PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT and proves every
                    contracted gate is runnable AND satisfiable exactly where the
                    contract invokes it, and FAILS in every state it should not run.
  (c) --smoke       Non-recorded smoke check runnable BEFORE any raw/ artifact exists:
                    builds the harness binaries and runs one throwaway case to a
                    work/scratch temp directory (never raw/, never compared across runs,
                    never outside the repo).
  --crossrun R1 R2  The real two-run gate: every case_id present in R1 is present in R2
                    with byte-identical JSON-serialized *.gated.json content (and vice
                    versa); *.nongated.json is read for sanity (must parse) but never
                    compared.

No case ever compares live git HEAD; see PRE_REGISTRATION.md / CAPTURE_CONTRACT.json.
All scratch/temp I/O stays inside work/scratch/ in this experiment directory -- never
/tmp, never anywhere outside the repo.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import schema as S

SCRATCH = HERE / "work" / "scratch"
FAIL = []


def check(cond, label, record=True):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {label}")
    if not cond and record:
        FAIL.append(label)
    return cond


def validate_gated(rec):
    if set(rec.keys()) != S.GATED_KEYS:
        return False, f"key set mismatch: {sorted(rec.keys())} != {sorted(S.GATED_KEYS)}"
    if rec["kind"] not in ("gpu_render", "compile_scan", "compile_attempt"):
        return False, f"bad kind {rec['kind']!r}"
    if rec["group"] not in S.GROUPS:
        return False, f"bad group {rec['group']!r}"
    result = rec["result"]
    if rec["kind"] == "gpu_render":
        if set(result.keys()) != S.GPU_RESULT_KEYS:
            return False, f"gpu result key mismatch: {sorted(result.keys())}"
    elif rec["kind"] == "compile_scan":
        if set(result.keys()) != S.SCAN_RESULT_KEYS:
            return False, f"scan result key mismatch: {sorted(result.keys())}"
    else:
        if set(result.keys()) != S.ATTEMPT_RESULT_KEYS:
            return False, f"attempt result key mismatch: {sorted(result.keys())}"
    blob = json.dumps(rec)
    for leaky in ("gputime_ns", "wall_ms", '"pid"', "started_at"):
        if leaky in blob:
            return False, f"nondeterministic-looking field leaked into gated record: {leaky}"
    return True, "ok"


def validate_nongated(rec):
    if set(rec.keys()) != S.NONGATED_KEYS:
        return False, f"key set mismatch: {sorted(rec.keys())} != {sorted(S.NONGATED_KEYS)}"
    return True, "ok"


def load_pilot_shapes():
    trial = HERE / "work" / "trial"
    gpu_shape, scan_shape, attempt_shape = None, None, None
    if trial.exists():
        for f in sorted(trial.glob("*.gated.json")):
            rec = json.loads(f.read_text())
            if rec["kind"] == "gpu_render" and gpu_shape is None:
                gpu_shape = rec
            if rec["kind"] == "compile_scan" and scan_shape is None:
                scan_shape = rec
            if rec["kind"] == "compile_attempt" and attempt_shape is None:
                attempt_shape = rec
    if gpu_shape is None:
        gpu_shape = {
            "case_id": "fallback_gpu", "group": "poscoord", "kind": "gpu_render",
            "params": {"n": 1}, "status": "OK",
            "result": {"device": "Apple M4", "pipeline_source": "compiled",
                       "size": [1, 1, 1], "pixels": {"0": [{"x": 0, "y": 0, "bgra": "ffffffff"}]},
                       "depth": None, "occlusion": None, "buffers": {}, "error": None},
        }
    if scan_shape is None:
        scan_shape = {
            "case_id": "fallback_scan", "group": "deriv_scalar", "kind": "compile_scan",
            "params": {"kernel": "x"}, "status": "SCANNED",
            "result": {"frag_main_hex": "00", "frag_main_len": 1, "tokenize_clean": True,
                       "tokenize_leftover": 0, "counts": {"total": 0}},
        }
    if attempt_shape is None:
        attempt_shape = {
            "case_id": "fallback_attempt", "group": "dynidx_out", "kind": "compile_attempt",
            "params": {"kernel": "x"}, "status": "REJECTED",
            "result": {"compiled": False, "error_text": "synthetic fallback"},
        }
    return gpu_shape, scan_shape, attempt_shape


def selftest():
    ok = True
    gpu_shape, scan_shape, attempt_shape = load_pilot_shapes()
    ok &= check(validate_gated(gpu_shape)[0], "selftest: pilot-shaped gpu_render record validates")
    ok &= check(validate_gated(scan_shape)[0], "selftest: pilot-shaped compile_scan record validates")
    ok &= check(validate_gated(attempt_shape)[0], "selftest: pilot-shaped compile_attempt record validates")

    missing_key = dict(gpu_shape); del missing_key["status"]
    ok &= check(not validate_gated(missing_key)[0], "selftest: missing key -> FAIL")

    extra_key = dict(gpu_shape); extra_key["extra_field"] = 1
    ok &= check(not validate_gated(extra_key)[0], "selftest: extra key -> FAIL")

    leaked_timing = json.loads(json.dumps(gpu_shape))
    leaked_timing["result"] = dict(leaked_timing["result"])
    leaked_timing["result"]["gputime_ns"] = 123
    ok &= check(not validate_gated(leaked_timing)[0],
                "selftest: timing field leaked into gated record -> FAIL")

    bad_kind = dict(gpu_shape); bad_kind["kind"] = "not_a_kind"
    ok &= check(not validate_gated(bad_kind)[0], "selftest: bad kind -> FAIL")

    nongated_shape = {"case_id": "x", "gputime_ns": 100, "wall_ms": 1.0, "pid": 999,
                       "started_at": None}
    ok &= check(validate_nongated(nongated_shape)[0], "selftest: nongated record validates")
    ok &= check(not validate_nongated({"case_id": "x"})[0],
                "selftest: incomplete nongated record -> FAIL")

    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(SCRATCH)) as td:
        r1 = Path(td) / "synthrun01"; r2 = Path(td) / "synthrun02"
        r1.mkdir(); r2.mkdir()
        rec = dict(gpu_shape); rec["case_id"] = "synth_case"
        (r1 / "synth_case.gated.json").write_text(json.dumps(rec, sort_keys=True))
        (r2 / "synth_case.gated.json").write_text(json.dumps(rec, sort_keys=True))
        (r1 / "synth_case.nongated.json").write_text(json.dumps(
            {"case_id": "synth_case", "gputime_ns": 111, "wall_ms": 1.1, "pid": 1001,
             "started_at": None}))
        (r2 / "synth_case.nongated.json").write_text(json.dumps(
            {"case_id": "synth_case", "gputime_ns": 222, "wall_ms": 2.2, "pid": 2002,
             "started_at": None}))
        same, diffs = crossrun_compare(r1, r2)
        ok &= check(same, "selftest: identical gated + different timing/pid -> cross-run PASS")

        rec2 = json.loads(json.dumps(rec))
        rec2["status"] = "DIFFERENT_STATUS"
        (r2 / "synth_case.gated.json").write_text(json.dumps(rec2, sort_keys=True))
        same2, diffs2 = crossrun_compare(r1, r2)
        ok &= check(not same2, "selftest: semantic gated.json difference -> cross-run FAIL")

    return ok


def crossrun_compare(dir1: Path, dir2: Path):
    g1 = {p.stem.replace(".gated", ""): p for p in dir1.glob("*.gated.json")}
    g2 = {p.stem.replace(".gated", ""): p for p in dir2.glob("*.gated.json")}
    diffs = []
    if set(g1) != set(g2):
        diffs.append(f"case_id set differs: only_in_1={sorted(set(g1)-set(g2))} "
                      f"only_in_2={sorted(set(g2)-set(g1))}")
        return False, diffs
    for cid in sorted(g1):
        r1 = json.loads(g1[cid].read_text())
        r2 = json.loads(g2[cid].read_text())
        ok1, why1 = validate_gated(r1)
        ok2, why2 = validate_gated(r2)
        if not ok1:
            diffs.append(f"{cid}: run1 record invalid: {why1}")
        if not ok2:
            diffs.append(f"{cid}: run2 record invalid: {why2}")
        if r1 != r2:
            diffs.append(f"{cid}: gated content differs")
        n1 = dir1 / f"{cid}.nongated.json"
        n2 = dir2 / f"{cid}.nongated.json"
        for n in (n1, n2):
            if not n.exists():
                diffs.append(f"{cid}: missing nongated sibling {n}")
                continue
            okn, whyn = validate_nongated(json.loads(n.read_text()))
            if not okn:
                diffs.append(f"{cid}: nongated sibling invalid: {whyn}")
    return (len(diffs) == 0), diffs


def smoke(run_id_dirs_that_must_not_exist, record=True):
    for d in run_id_dirs_that_must_not_exist:
        if d.exists():
            check(False, f"smoke: precondition violated -- {d} already exists "
                          f"(smoke must run BEFORE any raw/ artifact)", record=record)
            return False
    fsrun = HERE / "work" / "bin" / "fsrun"
    ok = check(fsrun.exists() and os.access(fsrun, os.X_OK), "smoke: fsrun binary built+executable",
               record=record)
    if not ok:
        return False
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(SCRATCH)) as td:
        out = subprocess.run([str(fsrun), "--source", str(HERE / "kernels" / "poscoord_scan.metal"),
                               "--vertex", "v_main", "--fragment", "f_main",
                               "--width", "1", "--height", "1"],
                              capture_output=True, text=True, timeout=30, cwd=td)
        ok &= check("STATUS OK" in out.stdout, "smoke: one throwaway dispatch returns STATUS OK",
                    record=record)
        ok &= check(not (Path(td) / "raw").exists(), "smoke: throwaway dispatch wrote nothing to raw/",
                    record=record)
    return ok


def seqtest():
    ok = True
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(SCRATCH)) as td:
        base = Path(td)
        run01 = base / "raw" / "run01"
        run02 = base / "raw" / "run02"

        ok &= check(smoke([run01, run02]), "seqtest[PRE_GPU]: smoke gate runnable+satisfiable")
        same, diffs = crossrun_compare(run01, run02) if run01.exists() and run02.exists() else (False, ["dirs absent"])
        ok &= check(not same, "seqtest[PRE_GPU]: cross-run gate correctly UNSATISFIABLE (no captures yet)")

        run01.mkdir(parents=True)
        gpu_shape, scan_shape, attempt_shape = load_pilot_shapes()
        rec = dict(gpu_shape); rec["case_id"] = "seq_case"
        (run01 / "seq_case.gated.json").write_text(json.dumps(rec, sort_keys=True))
        (run01 / "seq_case.nongated.json").write_text(json.dumps(
            {"case_id": "seq_case", "gputime_ns": 1, "wall_ms": 1.0, "pid": 1, "started_at": None}))
        ok &= check(not smoke([run01, run02], record=False),
                     "seqtest[RUN01_PRESENT]: smoke correctly refuses (run01 now exists)")
        same, diffs = crossrun_compare(run01, run02) if run02.exists() else (False, ["run02 absent"])
        ok &= check(not same, "seqtest[RUN01_PRESENT]: cross-run gate correctly UNSATISFIABLE (run02 missing)")

        run02.mkdir(parents=True)
        (run02 / "seq_case.gated.json").write_text(json.dumps(rec, sort_keys=True))
        (run02 / "seq_case.nongated.json").write_text(json.dumps(
            {"case_id": "seq_case", "gputime_ns": 2, "wall_ms": 2.0, "pid": 2, "started_at": None}))
        same, diffs = crossrun_compare(run01, run02)
        ok &= check(same, "seqtest[RUN02_PRESENT]: cross-run gate runnable AND satisfiable")
        ok &= check(not smoke([run01, run02], record=False),
                     "seqtest[RUN02_PRESENT]: smoke correctly refuses (both runs exist)")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--crossrun", nargs=2, metavar=("RUN1_DIR", "RUN2_DIR"))
    args = ap.parse_args()

    ran = False
    ok = True
    if args.selftest:
        ran = True
        ok &= selftest()
    if args.seqtest:
        ran = True
        ok &= seqtest()
    if args.smoke:
        ran = True
        run01 = HERE / "raw" / "run01"
        run02 = HERE / "raw" / "run02"
        ok &= smoke([run01, run02])
    if args.crossrun:
        ran = True
        d1, d2 = Path(args.crossrun[0]), Path(args.crossrun[1])
        same, diffs = crossrun_compare(d1, d2)
        ok &= check(same, f"crossrun: {d1.name} vs {d2.name} byte-identical gated records")
        for d in diffs:
            print("  DIFF:", d)

    if not ran:
        ap.print_help()
        return 2

    print()
    if FAIL:
        print(f"RESULT: FAIL ({len(FAIL)} failing checks)")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
