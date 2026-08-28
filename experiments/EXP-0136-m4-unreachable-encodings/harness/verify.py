#!/usr/bin/env python3
"""EXP-0136 fail-closed verifier. Standing gate set (mirrors sibling EXPs):
  --selftest    synthetic, offline (no Metal/device, no real raw/): matrix
                well-formed, schema is one shared key set, cross-run gate
                passes/fails correctly on synthetic fixtures, and the
                gputime_ns/wall_ms/pid/raw_tail nondeterministic fields live
                ONLY in the excluded nongated record.
  --seqtest     walks PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT through
                fabricated trees under a tempdir (never touches real raw/).
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
            if key in excl or key in S.NONDET_OBSERVED_KEYS:
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
        if set(c.keys()) != {"id", "family", "mechanism", "kind", "params"}:
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
    check("nongated_keys_disjoint_from_gated_keys_except_case_id",
          (S.GATED_KEYS & S.NONGATED_KEYS) == {"case_id"})
    check("every_case_mechanism_known",
          all(c["mechanism"] in ("descpatch", "gfxprobe", "agxtest") for c in CM.MATRIX))

    import tempfile
    base_case_id = CM.IDS[0]
    base_case = CM.MATRIX[0]
    excl = CM.case_order_sensitive_keys(base_case)
    check("no_family_declares_order_sensitive_keys", excl == set())

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        run_a, run_b = td / "synthA", td / "synthB"
        for d in (run_a, run_b):
            d.mkdir()
        rec_template = {"case_id": base_case_id, "family": base_case["family"], "kind": base_case["kind"],
                         "params": base_case["params"], "status": "OK", "verdict": "PASS",
                         "observed": {"pixel": [0.5, 0.5, 0.5, 1.0], "gputime_ns": 12345}}
        rec_a = json.loads(json.dumps(rec_template))
        rec_b = json.loads(json.dumps(rec_template))
        rec_b["observed"]["gputime_ns"] = 99999  # a nondeterministic-style extra field must not break the gate
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
        # NOTE: this experiment's schema does NOT declare gputime_ns as a
        # tolerated-mismatch key inside `observed` (unlike EXP-0123/0098, no
        # probe here writes wall-timing into `observed` at all -- it lives
        # only in NONGATED_KEYS). So a mismatching extra key INSIDE observed
        # SHOULD fail the gate; assert that behavior explicitly instead of
        # asserting a pass, since this experiment made a different, stricter
        # design choice (every observed field is expected byte-identical).
        check("gate_fails_when_any_observed_key_differs_incl_gputime_ns",
              (not ok_pass) and len(issues_pass) > 0)

        rec_c = json.loads(json.dumps(rec_template))
        del rec_c["observed"]["gputime_ns"]
        rec_d = json.loads(json.dumps(rec_c))
        run_c, run_d = td / "synthC", td / "synthD"
        for d in (run_c, run_d):
            d.mkdir()
        for dd, rec in ((run_c, rec_c), (run_d, rec_d)):
            (dd / "02_gated.jsonl").write_text(json.dumps(rec) + "\n")
            (dd / "03_nongated.jsonl").write_text(json.dumps(
                {"case_id": base_case_id, "gputime_ns": 1, "wall_ms": 1.0, "pid": 1, "raw_tail": ""}) + "\n")
            (dd / "04_manifest.json").write_text(json.dumps({"cases_planned": 1}))
        CM.TOTAL = 1
        try:
            ok_eq, issues_eq = cross_run_gate(run_c, run_d)
        finally:
            CM.TOTAL = old_total
        check("gate_passes_on_truly_identical_records", ok_eq and len(issues_eq) == 0)

        rec_e = json.loads(json.dumps(rec_c))
        rec_e["verdict"] = "FAIL"
        run_e = td / "synthE"
        run_e.mkdir()
        (run_e / "02_gated.jsonl").write_text(json.dumps(rec_e) + "\n")
        (run_e / "03_nongated.jsonl").write_text(json.dumps(
            {"case_id": base_case_id, "gputime_ns": 1, "wall_ms": 1.0, "pid": 1, "raw_tail": ""}) + "\n")
        (run_e / "04_manifest.json").write_text(json.dumps({"cases_planned": 1}))
        CM.TOTAL = 1
        try:
            ok_fail, issues_fail = cross_run_gate(run_c, run_e)
        finally:
            CM.TOTAL = old_total
        check("gate_fails_on_verdict_diff", (not ok_fail) and len(issues_fail) > 0)

        # NONDET_OBSERVED_KEYS (n_bos_loaded, error, error_patched -- see
        # schema.py for the empirical justification from the two official
        # runs) must be tolerated by the gate even when they differ, while a
        # mismatch in any OTHER observed key must still fail it.
        rec_f = json.loads(json.dumps(rec_c))
        rec_f["observed"]["n_bos_loaded"] = 13
        rec_f["observed"]["error"] = "Caused GPU Hang Error (...ErrorHang)"
        rec_g = json.loads(json.dumps(rec_c))
        rec_g["observed"]["n_bos_loaded"] = 27
        rec_g["observed"]["error"] = "Discarded (victim of GPU error/recovery) (...ErrorInnocentVictim)"
        run_f, run_g = td / "synthF", td / "synthG"
        for dd, rec in ((run_f, rec_f), (run_g, rec_g)):
            dd.mkdir()
            (dd / "02_gated.jsonl").write_text(json.dumps(rec) + "\n")
            (dd / "03_nongated.jsonl").write_text(json.dumps(
                {"case_id": base_case_id, "gputime_ns": 1, "wall_ms": 1.0, "pid": 1, "raw_tail": ""}) + "\n")
            (dd / "04_manifest.json").write_text(json.dumps({"cases_planned": 1}))
        CM.TOTAL = 1
        try:
            ok_nondet, issues_nondet = cross_run_gate(run_f, run_g)
        finally:
            CM.TOTAL = old_total
        check("gate_tolerates_confirmed_nondet_observed_keys", ok_nondet and len(issues_nondet) == 0)

        rec_h = json.loads(json.dumps(rec_f))
        rec_h["observed"]["pixel"] = [0.9, 0.9, 0.9, 1.0]  # a REAL (non-excluded) key mismatch
        run_h = td / "synthH"
        run_h.mkdir()
        (run_h / "02_gated.jsonl").write_text(json.dumps(rec_h) + "\n")
        (run_h / "03_nongated.jsonl").write_text(json.dumps(
            {"case_id": base_case_id, "gputime_ns": 1, "wall_ms": 1.0, "pid": 1, "raw_tail": ""}) + "\n")
        (run_h / "04_manifest.json").write_text(json.dumps({"cases_planned": 1}))
        CM.TOTAL = 1
        try:
            ok_realdiff, issues_realdiff = cross_run_gate(run_f, run_h)
        finally:
            CM.TOTAL = old_total
        check("gate_still_fails_on_a_non_excluded_key_mismatch", (not ok_realdiff) and len(issues_realdiff) > 0)

    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    n_fail = sum(1 for _, ok in checks if not ok)
    print(f"{'PASS' if n_fail == 0 else 'FAIL'} selftest: {len(checks)-n_fail}/{len(checks)} checks passed")
    if n_fail:
        sys.exit(1)


def cmd_seqtest():
    import tempfile
    global RAW
    orig_raw = RAW
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    with tempfile.TemporaryDirectory() as td:
        RAW = Path(td) / "raw"
        RAW.mkdir()
        ok, _ = gate_preflight(RAW)
        check("PRE_GPU_empty_raw_passes", ok)

        run01 = RAW / "run01"
        run01.mkdir()
        old_total = CM.TOTAL
        CM.TOTAL = 2
        try:
            (run01 / "02_gated.jsonl").write_text(
                "\n".join(json.dumps({"case_id": f"c{i}", "family": "aniso", "kind": "aniso_real",
                                       "params": {}, "status": "OK", "verdict": "PASS", "observed": {}})
                          for i in range(2)) + "\n")
            (run01 / "03_nongated.jsonl").write_text(
                "\n".join(json.dumps({"case_id": f"c{i}", "gputime_ns": 0, "wall_ms": 0.0, "pid": 1, "raw_tail": ""})
                          for i in range(2)) + "\n")
            (run01 / "04_manifest.json").write_text(json.dumps({"cases_planned": 2}))
            ok, _ = gate_between_runs(RAW)
            check("RUN01_PRESENT_one_closed_run_passes", ok)

            run02 = RAW / "run02"
            run02.mkdir()
            (run02 / "02_gated.jsonl").write_text((run01 / "02_gated.jsonl").read_text())
            (run02 / "03_nongated.jsonl").write_text((run01 / "03_nongated.jsonl").read_text())
            (run02 / "04_manifest.json").write_text(json.dumps({"cases_planned": 2}))
            gate_ok, issues = cross_run_gate(run01, run02)
            check("RUN02_PRESENT_two_closed_runs_gate_passes", gate_ok and len(issues) == 0)
        finally:
            CM.TOTAL = old_total

    RAW = orig_raw
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    n_fail = sum(1 for _, ok in checks if not ok)
    print(f"{'PASS' if n_fail == 0 else 'FAIL'} seqtest: {len(checks)-n_fail}/{len(checks)} checks passed")
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
        ap.error("choose one of --selftest/--seqtest/--preflight/--between-runs/--captured")


if __name__ == "__main__":
    main()
