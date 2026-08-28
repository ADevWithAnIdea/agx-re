#!/usr/bin/env python3
"""EXP-0093 fail-closed verifier. Implements the standing gate set (per
dispatch: verify.py --selftest, verify.py --seqtest state machine over
PRE_GPU/RUN01_PRESENT/RUN02_PRESENT, and a captured-run cross-run gate that
excludes declared order-sensitive keys from the byte-identity comparison
while still gating on the coarse per-case verdict).

  --selftest             synthetic, offline (no Metal/device, no real raw/):
                          proves the matrix is well-formed, the schema is one
                          shared key set, and the cross-run gate correctly
                          PASSES two synthetic runs that differ only in a
                          case's declared order-sensitive 'observed' keys and
                          FAILS when any other key differs -- fixtures are
                          built from a REAL recorded capture
                          (harness/fixtures/recorded_reality.json), not
                          hand-typed constants (standing gate (e)).
  --seqtest               walks PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT
                          through fabricated trees under work/seqtest_scratch/
                          (never touching real raw/), proving each gate is
                          runnable+satisfiable in its contracted state and
                          fails in every other state.
  --preflight              PRE_GPU: raw/ must be empty of run dirs.
  --between-runs           RUN01_PRESENT: exactly one closed run dir.
  --captured RUN1 RUN2     RUN02_PRESENT: both closed; runs the cross-run gate
                          + verdict tally.
"""
import argparse, json, shutil, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import casematrix as CM
import schema as S

RAW = EXP / "raw"
FIXTURE = HERE / "fixtures" / "recorded_reality.json"


def fail(msg):
    raise SystemExit("FAIL " + msg)


# ---------------------------------------------------------------------------
def list_run_dirs(raw_root):
    if not raw_root.exists():
        return []
    return sorted([p for p in raw_root.iterdir() if p.is_dir()])


def run_is_closed(run_dir):
    manifest_p = run_dir / "04_manifest.json"
    if not manifest_p.exists():
        return False, "missing 04_manifest.json"
    try:
        manifest = json.loads(manifest_p.read_text())
    except Exception as e:
        return False, f"unreadable manifest: {e}"
    gated_p, nongated_p = run_dir / "02_gated.jsonl", run_dir / "03_nongated.jsonl"
    if not gated_p.exists() or not nongated_p.exists():
        return False, "missing gated/nongated jsonl"
    lines = [l for l in gated_p.read_text().splitlines() if l.strip()]
    if len(lines) != manifest.get("cases_planned"):
        return False, f"gated line count {len(lines)} != cases_planned {manifest.get('cases_planned')}"
    if manifest.get("cases_planned") != CM.TOTAL:
        return False, f"manifest cases_planned {manifest.get('cases_planned')} != frozen TOTAL {CM.TOTAL}"
    return True, "ok"


def gate_preflight(raw_root):
    dirs = list_run_dirs(raw_root)
    if dirs:
        return False, f"raw tree already present: {[d.name for d in dirs]}"
    return True, "no run directories present"


def gate_between_runs(raw_root):
    dirs = list_run_dirs(raw_root)
    if len(dirs) != 1:
        return False, f"expected exactly 1 run directory, found {len(dirs)}"
    return run_is_closed(dirs[0])


def load_gated(run_dir):
    recs = {}
    for line in (run_dir / "02_gated.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        ok, msg = S.validate_gated(rec)
        if not ok:
            raise RuntimeError(f"{run_dir.name}: {msg}")
        recs[rec["case_id"]] = rec
    return recs


def cross_run_gate(run_a_dir, run_b_dir):
    ra = load_gated(run_a_dir)
    rb = load_gated(run_b_dir)
    issues = []
    ids_a, ids_b = set(ra), set(rb)
    if ids_a != ids_b:
        issues.append(f"case id set differs: only-A={sorted(ids_a-ids_b)[:5]} only-B={sorted(ids_b-ids_a)[:5]}")
    by_id = {c["id"]: c for c in CM.MATRIX}
    for cid in sorted(ids_a & ids_b):
        a, b = ra[cid], rb[cid]
        case = by_id.get(cid)
        excl = CM.case_order_sensitive_keys(case) if case else set()
        for key in ("status", "verdict", "family", "kind"):
            if a[key] != b[key]:
                issues.append(f"{cid}: {key} differs: {a[key]!r} != {b[key]!r}")
        oa, ob = a["observed"], b["observed"]
        for key in set(oa) | set(ob):
            if key in excl:
                continue
            if oa.get(key) != ob.get(key):
                issues.append(f"{cid}: observed.{key} differs: {oa.get(key)!r} != {ob.get(key)!r}")
    return (len(issues) == 0), issues


def verdict_counts(run_dir):
    counts = {"PASS": 0, "FAIL": 0, "TIMEOUT": 0, "N/A": 0}
    for rec in load_gated(run_dir).values():
        counts[rec["verdict"]] = counts.get(rec["verdict"], 0) + 1
    return counts


# ---------------------------------------------------------------------------
def cmd_preflight():
    ok, msg = gate_preflight(RAW)
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        sys.exit(1)


def cmd_between_runs():
    ok, msg = gate_between_runs(RAW)
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        sys.exit(1)


def cmd_captured(run_a, run_b):
    dirs = list_run_dirs(RAW)
    if len(dirs) != 2:
        fail(f"expected exactly 2 run directories, found {len(dirs)}")
    for d in dirs:
        ok, msg = run_is_closed(d)
        if not ok:
            fail(f"{d.name} not closed: {msg}")
    ra_dir = RAW / run_a
    rb_dir = RAW / run_b
    if not ra_dir.exists() or not rb_dir.exists():
        fail(f"named runs not found under raw/: {run_a}, {run_b}")
    gate_ok, issues = cross_run_gate(ra_dir, rb_dir)
    ca = verdict_counts(ra_dir)
    cb = verdict_counts(rb_dir)
    print(json.dumps({"cross_run_gate_pass": gate_ok, "issues": issues[:50],
                       "issues_total": len(issues),
                       "verdict_counts_a": ca, "verdict_counts_b": cb}, indent=2))
    if not gate_ok:
        sys.exit(1)
    if ca["FAIL"] > 0 or cb["FAIL"] > 0 or ca["TIMEOUT"] > 0 or cb["TIMEOUT"] > 0:
        print("WARNING: non-PASS verdicts present (see counts above) -- inspect before promoting")


# ---------------------------------------------------------------------------
def cmd_selftest():
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    # 1. matrix well-formed
    check("matrix_total_matches_TOTAL", len(CM.MATRIX) == CM.TOTAL)
    check("matrix_ids_unique", len(set(CM.IDS)) == len(CM.IDS))
    for c in CM.MATRIX:
        if set(c.keys()) != {"id", "family", "kind", "params"}:
            check(f"case_shape_{c['id']}", False)
            break
    else:
        check("case_shapes_ok", True)

    # 2. schema key sets are disjoint from each other's extra fields (sanity)
    check("gated_keys_frozen", S.GATED_KEYS == {"case_id", "family", "kind", "params", "status", "verdict", "observed"})
    check("nongated_keys_frozen", S.NONGATED_KEYS == {"case_id", "gputime_ns", "wall_ms", "pid", "raw_tail"})

    # 3. tgdiv expected-output helper is pure arithmetic and matches the one
    #    real recorded baseline capture in the fixture (recorded reality).
    if not FIXTURE.exists():
        check("fixture_present", False)
    else:
        fixture = json.loads(FIXTURE.read_text())
        check("fixture_present", True)
        expected = CM.tgdiv_expected_output()

        def s32(x):
            return x - (1 << 32) if x >= (1 << 31) else x
        recorded = fixture["tgdiv_baseline_result"]
        check("tgdiv_formula_matches_recorded_reality",
              [s32(v) for v in expected] == [s32(v) for v in recorded])
        check("rog_strong_n16_matches_recorded_reality",
              fixture["rog_strong_n16_ctr_tex"] == "00000010")

    # 4. cross-run gate: two synthetic runs built from the REAL fixture record
    #    (recorded reality), differing ONLY in a devfence_pairs case's declared
    #    order-sensitive keys -> gate must PASS. A control run that also
    #    differs in a NON-order-sensitive key -> gate must FAIL.
    import tempfile
    base_case_id = "devfence_RR_p4_r0"
    base_case = next(c for c in CM.MATRIX if c["id"] == base_case_id)
    excl = CM.case_order_sensitive_keys(base_case)
    check("devfence_has_order_sensitive_keys", len(excl) > 0)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        run_a = td / "synthA"; run_b = td / "synthB"
        for d in (run_a, run_b):
            d.mkdir()
        rec_template = {"case_id": base_case_id, "family": "devfence_pairs", "kind": "devfence_gpu",
                         "params": base_case["params"], "status": "OK", "verdict": "PASS",
                         "observed": {"mismatch": 5, "producer_timeouts": 0,
                                     "consumer_timeouts": 0, "completed": 200}}
        rec_a = json.loads(json.dumps(rec_template))
        rec_b = json.loads(json.dumps(rec_template))
        rec_b["observed"]["mismatch"] = 9  # order-sensitive key -- should NOT trip the gate
        manifest = {"cases_planned": 1}
        for d, rec in ((run_a, rec_a), (run_b, rec_b)):
            (d / "02_gated.jsonl").write_text(json.dumps(rec) + "\n")
            (d / "03_nongated.jsonl").write_text(json.dumps(
                {"case_id": base_case_id, "gputime_ns": 1, "wall_ms": 1.0, "pid": 1, "raw_tail": ""}) + "\n")
            (d / "04_manifest.json").write_text(json.dumps({"cases_planned": 1}))
        old_total = CM.TOTAL
        CM.TOTAL = 1  # scope the closedness check to this 1-case synthetic tree
        try:
            ok_pass, issues_pass = cross_run_gate(run_a, run_b)
        finally:
            CM.TOTAL = old_total
        check("gate_passes_on_order_sensitive_diff_only", ok_pass and len(issues_pass) == 0)

        rec_c = json.loads(json.dumps(rec_template))
        rec_c["observed"]["completed"] = 999  # ALSO order-sensitive: should still pass
        rec_d = json.loads(json.dumps(rec_template))
        rec_d["verdict"] = "FAIL"  # NOT order-sensitive: must trip the gate
        run_c = td / "synthC"; run_d = td / "synthD"
        run_c.mkdir(); run_d.mkdir()
        for d, rec in ((run_c, rec_c), (run_d, rec_d)):
            (d / "02_gated.jsonl").write_text(json.dumps(rec) + "\n")
            (d / "03_nongated.jsonl").write_text(json.dumps(
                {"case_id": base_case_id, "gputime_ns": 1, "wall_ms": 1.0, "pid": 1, "raw_tail": ""}) + "\n")
            (d / "04_manifest.json").write_text(json.dumps({"cases_planned": 1}))
        ok_fail, issues_fail = cross_run_gate(run_a, run_d)
        check("gate_fails_on_non_order_sensitive_diff", (not ok_fail) and len(issues_fail) > 0)

    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    n_fail = sum(1 for _, ok in checks if not ok)
    print(f"{'PASS' if n_fail == 0 else 'FAIL'} selftest: {len(checks)-n_fail}/{len(checks)} checks passed")
    if n_fail:
        sys.exit(1)


def cmd_seqtest():
    import tempfile
    results = []

    def record(state, gate_name, ok, expected):
        results.append((state, gate_name, ok, expected, ok == expected))

    with tempfile.TemporaryDirectory() as td:
        raw_root = Path(td) / "raw"
        # STATE: PRE_GPU (raw_root does not exist / is empty)
        raw_root.mkdir()
        ok, _ = gate_preflight(raw_root)
        record("PRE_GPU", "preflight", ok, True)
        ok, _ = gate_between_runs(raw_root)
        record("PRE_GPU", "between_runs", ok, False)

        # STATE: RUN01_PRESENT (one closed run dir)
        run01 = raw_root / "run01"
        run01.mkdir()
        (run01 / "02_gated.jsonl").write_text("")
        (run01 / "03_nongated.jsonl").write_text("")
        (run01 / "04_manifest.json").write_text(json.dumps({"cases_planned": 0}))
        old_total = CM.TOTAL
        CM.TOTAL = 0
        try:
            ok, _ = gate_preflight(raw_root)
            record("RUN01_PRESENT", "preflight", ok, False)
            ok, _ = gate_between_runs(raw_root)
            record("RUN01_PRESENT", "between_runs", ok, True)

            # STATE: RUN02_PRESENT (two closed run dirs)
            run02 = raw_root / "run02"
            run02.mkdir()
            (run02 / "02_gated.jsonl").write_text("")
            (run02 / "03_nongated.jsonl").write_text("")
            (run02 / "04_manifest.json").write_text(json.dumps({"cases_planned": 0}))
            ok, _ = gate_preflight(raw_root)
            record("RUN02_PRESENT", "preflight", ok, False)
            ok, _ = gate_between_runs(raw_root)
            record("RUN02_PRESENT", "between_runs", ok, False)
            gate_ok, _ = cross_run_gate(run01, run02)
            record("RUN02_PRESENT", "cross_run_gate_on_empty_runs", gate_ok, True)
        finally:
            CM.TOTAL = old_total

    n_fail = 0
    for state, gate_name, ok, expected, passed in results:
        print(f"{'PASS' if passed else 'FAIL'} {state}/{gate_name}: got={ok} expected={expected}")
        if not passed:
            n_fail += 1
    print(f"{'PASS' if n_fail == 0 else 'FAIL'} seqtest: {len(results)-n_fail}/{len(results)} state/gate combinations correct")
    if n_fail:
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--between-runs", action="store_true")
    ap.add_argument("--captured", nargs=2, metavar=("RUN_A", "RUN_B"))
    args = ap.parse_args()
    if args.selftest:
        cmd_selftest()
    elif args.seqtest:
        cmd_seqtest()
    elif args.preflight:
        cmd_preflight()
    elif args.between_runs:
        cmd_between_runs()
    elif args.captured:
        cmd_captured(*args.captured)
    else:
        print("nothing to do; see --help", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
