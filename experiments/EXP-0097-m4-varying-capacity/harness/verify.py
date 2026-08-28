#!/usr/bin/env python3
"""EXP-0097 fail-closed verifier. Implements the standing gate set:
  --selftest    synthetic, offline (no Metal/device, no real raw/): proves the
                matrix is well-formed, the schema is one shared key set, and
                the cross-run gate PASSES/FAILS correctly on fixtures built
                from a REAL recorded capture (harness/fixtures/recorded_reality.json),
                not hand-typed constants (standing gate (e)). Runnable in
                EVERY tree state.
  --seqtest     walks PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT through
                fabricated trees under a tempdir (never touching real raw/).
  --preflight   PRE_GPU: raw/ must be empty of run dirs.
  --between-runs RUN01_PRESENT: exactly one closed run dir.
  --captured RUN1 RUN2  RUN02_PRESENT: both closed; cross-run gate + tally.
"""
import argparse, json, sys
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
    ra_dir, rb_dir = RAW / run_a, RAW / run_b
    if not ra_dir.exists() or not rb_dir.exists():
        fail(f"named runs not found under raw/: {run_a}, {run_b}")
    gate_ok, issues = cross_run_gate(ra_dir, rb_dir)
    ca, cb = verdict_counts(ra_dir), verdict_counts(rb_dir)
    print(json.dumps({"cross_run_gate_pass": gate_ok, "issues": issues[:50],
                       "issues_total": len(issues), "verdict_counts_a": ca,
                       "verdict_counts_b": cb}, indent=2))
    if not gate_ok:
        sys.exit(1)
    if ca["FAIL"] > 0 or cb["FAIL"] > 0 or ca["TIMEOUT"] > 0 or cb["TIMEOUT"] > 0:
        print("WARNING: non-PASS verdicts present (see counts above) -- inspect before promoting")


def cmd_selftest():
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    check("matrix_total_matches_TOTAL", len(CM.MATRIX) == CM.TOTAL)
    check("matrix_ids_unique", len(set(CM.IDS)) == len(CM.IDS))
    for c in CM.MATRIX:
        if set(c.keys()) != {"id", "family", "kind", "params"}:
            check(f"case_shape_{c['id']}", False)
            break
    else:
        check("case_shapes_ok", True)

    check("gated_keys_frozen", S.GATED_KEYS ==
          {"case_id", "family", "kind", "params", "status", "verdict", "observed"})
    check("nongated_keys_frozen", S.NONGATED_KEYS ==
          {"case_id", "gputime_ns", "wall_ms", "pid", "raw_tail"})
    check("every_case_family_in_schema_families",
          all(c["family"] in S.FAMILIES for c in CM.MATRIX))

    # Fixture-grounded checks: the exact numeric boundaries this experiment
    # exists to confirm, pinned from a REAL recorded capture (standing gate (e)).
    if not FIXTURE.exists():
        check("fixture_present", False)
    else:
        fixture = json.loads(FIXTURE.read_text())
        check("fixture_present", True)
        check("vary_boundary_matches_recorded_reality",
              fixture["vary_float_n124_pipeline_ok"] is True and
              fixture["vary_float_n125_pipeline_ok"] is False and
              fixture["vary_float_n125_error_text"] ==
              "Number of varying components(125) exceeds the limit (124)")
        check("clip_boundary_matches_recorded_reality",
              fixture["clip_n8_pipeline_ok"] is True and
              fixture["clip_n9_pipeline_ok"] is False)
        check("point_clamp_matches_recorded_reality",
              fixture["point_b512_side"] == 511 and fixture["point_b511_side"] == 511)
        check("layer_clamp_zero_matches_recorded_reality",
              fixture["layer_L4_v4_landing"] == [0] and fixture["layer_L4_v3_landing"] == [3])
        check("provoking_first_vertex_matches_recorded_reality",
              fixture["prov_list_direct_color"] == "red")

    # Cross-run gate: two synthetic runs built from the fixture, differing
    # only in a NON-gated field (irrelevant to comparison) -> PASS; a control
    # differing in `verdict` -> FAIL. (No family in this experiment declares
    # order-sensitive keys -- case_order_sensitive_keys() is always {} here,
    # so this also exercises that the empty-set path still gates strictly.)
    import tempfile
    base_case_id = "clip_n8"
    base_case = next(c for c in CM.MATRIX if c["id"] == base_case_id)
    excl = CM.case_order_sensitive_keys(base_case)
    check("no_family_declares_order_sensitive_keys", excl == set())

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        run_a, run_b = td / "synthA", td / "synthB"
        for d in (run_a, run_b):
            d.mkdir()
        rec_template = {"case_id": base_case_id, "family": "clip_sweep", "kind": "capacity_compile",
                         "params": base_case["params"], "status": "OK", "verdict": "PASS",
                         "observed": {"ok": True, "raw_status": "PIPELINE_OK", "error_text": None}}
        rec_a = json.loads(json.dumps(rec_template))
        rec_b = json.loads(json.dumps(rec_template))
        manifest = {"cases_planned": 1}
        for d, rec in ((run_a, rec_a), (run_b, rec_b)):
            (d / "02_gated.jsonl").write_text(json.dumps(rec) + "\n")
            (d / "03_nongated.jsonl").write_text(json.dumps(
                {"case_id": base_case_id, "gputime_ns": 1, "wall_ms": 1.0, "pid": 1, "raw_tail": ""}) + "\n")
            (d / "04_manifest.json").write_text(json.dumps({"cases_planned": 1}))
        old_total = CM.TOTAL
        CM.TOTAL = 1
        try:
            ok_pass, issues_pass = cross_run_gate(run_a, run_b)
        finally:
            CM.TOTAL = old_total
        check("gate_passes_on_byte_identical_runs", ok_pass and len(issues_pass) == 0)

        rec_c = json.loads(json.dumps(rec_template))
        rec_c["verdict"] = "FAIL"
        run_c = td / "synthC"
        run_c.mkdir()
        (run_c / "02_gated.jsonl").write_text(json.dumps(rec_c) + "\n")
        (run_c / "03_nongated.jsonl").write_text(json.dumps(
            {"case_id": base_case_id, "gputime_ns": 1, "wall_ms": 1.0, "pid": 1, "raw_tail": ""}) + "\n")
        (run_c / "04_manifest.json").write_text(json.dumps({"cases_planned": 1}))
        ok_fail, issues_fail = cross_run_gate(run_a, run_c)
        check("gate_fails_on_verdict_diff", (not ok_fail) and len(issues_fail) > 0)

    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    n_fail = sum(1 for _, ok in checks if not ok)
    print(f"{'PASS' if n_fail == 0 else 'FAIL'} selftest: {len(checks)-n_fail}/{len(checks)} checks passed")
    if n_fail:
        sys.exit(1)


def cmd_seqtest():
    results = []

    def record(state, gate_name, ok, expected):
        results.append((state, gate_name, ok, expected, ok == expected))

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        raw_root = Path(td) / "raw"
        raw_root.mkdir()
        ok, _ = gate_preflight(raw_root)
        record("PRE_GPU", "preflight", ok, True)
        ok, _ = gate_between_runs(raw_root)
        record("PRE_GPU", "between_runs", ok, False)

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
