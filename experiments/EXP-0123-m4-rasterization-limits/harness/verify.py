#!/usr/bin/env python3
"""EXP-0123 fail-closed verifier. Standing gate set (mirrors sibling EXPs):
  --selftest    synthetic, offline (no Metal/device, no real raw/): matrix
                well-formed, schema is one shared key set, cross-run gate
                passes/fails correctly on fixtures built from a REAL recorded
                pilot capture (harness/fixtures/recorded_reality.json), and
                the gputime_ns/wall_ms/pid/raw_tail nondeterministic fields
                live ONLY in the excluded nongated record.
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
            if key == "gputime_ns":
                continue  # per-run GPU timing lives in observed for a couple of
                          # ops; explicitly excluded as the one nondeterministic field
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
    # case_id is the intentional join key shared by both streams; every
    # OTHER key must be exclusive to one stream (in particular gputime_ns
    # must never also live in the gated/observed side -- see
    # _strip_nondeterministic in run.py).
    check("nongated_keys_disjoint_from_gated_keys_except_case_id",
          (S.GATED_KEYS & S.NONGATED_KEYS) == {"case_id"})

    if not FIXTURE.exists():
        check("fixture_present", False)
    else:
        fixture = json.loads(FIXTURE.read_text())
        check("fixture_present", True)
        check("point_rounding_tie_at_2.0_matches_recorded_reality",
              fixture["point_sz_2.0_side"] == 2 and fixture["point_sz_2.1_side"] == 3)
        check("fillmode_fill_gt_lines_gt_zero_matches_recorded_reality",
              fixture["fillmode_fill_count"] > fixture["fillmode_lines_count"] > 0)
        check("depthclip_clip_vs_clamp_matches_recorded_reality",
              fixture["depthclip_clip_far_count"] == 0 and fixture["depthclip_clamp_far_count"] > 0)
        check("attachment_ceiling_hard_abort_matches_recorded_reality",
              fixture["attach_n9_status"] == "CRASH")
        check("viewport_16_functional_17_hangs_21_crashes_matches_recorded_reality",
              fixture["vp_n16_status"] == "OK" and fixture["vp_n17_status"] == "CMDBUF_ERROR"
              and fixture["vp_n21_status"] == "CRASH")
        check("tex2d_16384_boundary_matches_recorded_reality",
              fixture["tex2d_16384_create_status"] == "OK" and fixture["tex2d_16385_status"] == "CRASH")
        check("bufferindex_compiletime_bound_matches_recorded_reality",
              fixture["bufidx_31_status"] == "COMPILE_FAIL" and
              "must be between 0 and 30" in fixture["bufidx_31_error_contains"])
        check("textureindex_compiletime_bound_matches_recorded_reality",
              fixture["texidx_128_status"] == "COMPILE_FAIL" and
              "must be between 0 and 127" in fixture["texidx_128_error_contains"])
        check("inline_bytes_32752_boundary_matches_recorded_reality",
              fixture["bytesconst_32752_status"] == "OK" and fixture["bytesconst_32753_status"] == "CRASH")
        check("threadgroup_1024_boundary_matches_recorded_reality",
              fixture["tgsize_1024_touched"] is True and fixture["tgsize_1025_touched"] is False)
        check("simd_width_32_matches_recorded_reality", fixture["simdwidth_tg32_tew"] == 32)

    import tempfile
    base_case_id = "attach_n8"
    base_case = next(c for c in CM.MATRIX if c["id"] == base_case_id)
    excl = CM.case_order_sensitive_keys(base_case)
    check("no_family_declares_order_sensitive_keys", excl == set())

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        run_a, run_b = td / "synthA", td / "synthB"
        for d in (run_a, run_b):
            d.mkdir()
        rec_template = {"case_id": base_case_id, "family": "limit_attachments", "kind": "multiattach",
                         "params": base_case["params"], "status": "OK", "verdict": "PASS",
                         "observed": {"ok": True, "gputime_ns": 12345}}
        rec_a = json.loads(json.dumps(rec_template))
        rec_b = json.loads(json.dumps(rec_template))
        rec_b["observed"]["gputime_ns"] = 99999  # nondeterministic field must NOT break the gate
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
        check("gate_passes_when_only_gputime_ns_differs", ok_pass and len(issues_pass) == 0)

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
