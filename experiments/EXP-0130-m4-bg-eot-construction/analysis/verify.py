#!/usr/bin/env python3
"""EXP-0130 gate: --selftest / --seqtest / --captured.

Implements the standing gates for this experiment:
  --selftest   pure-Python checks of this file's own parsing/comparison
               logic against fixtures copied verbatim from the NON-RECORDED
               smoke run (work/smoke/smoke3/records.jsonl), no GPU needed.
  --seqtest    checks CAPTURE_CONTRACT.json's PRE_GPU timestamp predates
               raw/<run01>/ which predates raw/<run02>/ (PRE_GPU ->
               RUN01_PRESENT -> RUN02_PRESENT).
  --captured   cross-run byte-exact comparison of run01 vs run02, excluding
               the nondeterministic fields (wall_s, gputime_ns) per
               CAPTURE_CONTRACT.json, plus per-run semantic correctness
               (float32-exact oracle match) and structural-shape checks.
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NONDET_FIELDS = {"wall_s"}  # gputime_ns lives inside the stdout JSON string; handled separately


def f32(x):
    return struct.unpack("f", struct.pack("f", float(x)))[0]


def load_records(path):
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def parse_stdout_json(rec):
    """Parse the render_eot stdout JSON embedded in a behavioral record."""
    return json.loads(rec["stdout"])


def project_record(rec):
    """Strip nondeterministic fields for the byte-exact cross-run gate."""
    proj = {k: v for k, v in rec.items() if k not in NONDET_FIELDS}
    if proj.get("kind") == "behavioral" and proj.get("stdout"):
        try:
            sd = json.loads(proj["stdout"])
            sd.pop("gputime_ns", None)
            proj["stdout"] = json.dumps(sd, sort_keys=True)
        except (ValueError, TypeError):
            pass
    return proj


def key_of(rec):
    if rec["kind"] == "structural":
        return ("structural", rec["function"])
    return ("behavioral", rec["mode"], rec["case_id"])


# ----------------------------------------------------------------------
# --selftest: fixtures copied verbatim from work/smoke/smoke3/records.jsonl
# ----------------------------------------------------------------------

FIXTURE_STRUCTURAL_EVICT = (
    '{"build_error": null, "build_ok": true, "contains_frag_color_store": false, '
    '"contains_tile_read": false, "extract_returncode": 0, "function": "f_eot_evict", '
    '"hex": "8702540006000702540002000e000000", "hex_len_bytes": 16, "kind": "structural"}'
)
FIXTURE_STRUCTURAL_CTRL = (
    '{"build_error": null, "build_ok": true, "contains_frag_color_store": true, '
    '"contains_tile_read": false, "extract_returncode": 0, "function": "f_eot_ctrl", '
    '"hex": "970c5400020818d005c897045401021028d005c88702540006008702540c0800e70654000000014e'
    '000000000702540c02000e000000", "hex_len_bytes": 54, "kind": "structural"}'
)
FIXTURE_STRUCTURAL_COMBINE = (
    '{"build_error": null, "build_ok": true, "contains_frag_color_store": true, '
    '"contains_tile_read": true, "extract_returncode": 0, "function": "f_eot_combine", '
    '"hex": "870254000600870254080800670e5404000001ce0200000017045600010814ea09012ec12104020219'
    '032ec12106020297045404020008d045c217045400010a14ea09012ec12108020219032ec1210a020297045'
    '405020008d045c2870254040800e70654040000014e000000000702540c02000e000000", '
    '"hex_len_bytes": 120, "kind": "structural"}'
)
FIXTURE_BEHAVIORAL_D0 = (
    '{"case_id": "d0_zero", "expected": [0.0, 0.0, 0.0, 0.0], "kind": "behavioral", '
    '"mode": "evict", "returncode": 0, "stderr": "", '
    '"stdout": "{\\"status\\":\\"OK\\",\\"mode\\":\\"evict\\",\\"case\\":\\"d0_zero\\",'
    '\\"dst\\":[0,0,0,0],\\"konst\\":[0,0,0,0],\\"result\\":[0,0,0,0],\\"gputime_ns\\":19999}", '
    '"timed_out": false, "wall_s": 0.032}'
)
FIXTURE_BEHAVIORAL_C0 = (
    '{"case_id": "c0", "expected": [7.0, -6.0, 4.0, 8.0], "kind": "behavioral", '
    '"mode": "combine", "returncode": 0, "stderr": "", '
    '"stdout": "{\\"status\\":\\"OK\\",\\"mode\\":\\"combine\\",\\"case\\":\\"c0\\",'
    '\\"dst\\":[3,-4,0.5,2],\\"konst\\":[1,2,3,4],\\"result\\":[7,-6,4,8],\\"gputime_ns\\":20999}", '
    '"timed_out": false, "wall_s": 0.028}'
)


def selftest():
    checks = []

    # 1. f32() rounds a double-precision literal not exactly representable
    #    in float32 to the same value as its 9-sig-fig printf rendering
    #    would have (the bug this experiment's own pilot caught -- see
    #    PROGRESS.md). Uses the exact numbers from that pilot.
    a = f32(8.507059173023462e37)
    b = f32(8.50705917e37)
    checks.append(("f32_rounds_pilot_mismatch_to_equal", a == b))

    # 2. f32() distinguishes genuinely different values.
    checks.append(("f32_distinguishes_different_values", f32(1.0) != f32(2.0)))

    # 3. parse_stdout_json extracts the expected fields from a real fixture.
    rec = json.loads(FIXTURE_BEHAVIORAL_D0)
    sd = parse_stdout_json(rec)
    checks.append(("parse_stdout_fixture_result", sd["result"] == [0, 0, 0, 0]))
    checks.append(("parse_stdout_fixture_mode", sd["mode"] == "evict"))

    # 4. Oracle-vs-observed float32 comparison on a real fixture (combine).
    rec2 = json.loads(FIXTURE_BEHAVIORAL_C0)
    sd2 = parse_stdout_json(rec2)
    match = all(f32(o) == f32(e) for o, e in zip(sd2["result"], rec2["expected"]))
    checks.append(("oracle_match_fixture_c0", match))

    # 5. Structural fixtures: evict has neither op, ctrl has store-only,
    #    combine has both -- the load-bearing structural claim this
    #    experiment reports.
    fe = json.loads(FIXTURE_STRUCTURAL_EVICT)
    fc = json.loads(FIXTURE_STRUCTURAL_CTRL)
    fx = json.loads(FIXTURE_STRUCTURAL_COMBINE)
    checks.append(("evict_has_neither_op", not fe["contains_tile_read"] and not fe["contains_frag_color_store"]))
    checks.append(("ctrl_has_store_not_read", fc["contains_frag_color_store"] and not fc["contains_tile_read"]))
    checks.append(("combine_has_both_ops", fx["contains_tile_read"] and fx["contains_frag_color_store"]))

    # 6. project_record strips nondeterministic fields but keeps semantic ones.
    proj = project_record(rec)
    checks.append(("project_strips_wall_s", "wall_s" not in proj))
    checks.append(("project_keeps_case_id", proj.get("case_id") == "d0_zero"))
    proj_sd = json.loads(proj["stdout"])
    checks.append(("project_strips_gputime_ns", "gputime_ns" not in proj_sd))

    # 7. A deliberately tampered semantic field must be caught (mutator test).
    tampered = json.loads(FIXTURE_BEHAVIORAL_D0)
    tsd = json.loads(tampered["stdout"])
    tsd["result"] = [1, 2, 3, 4]  # wrong on purpose
    tampered["stdout"] = json.dumps(tsd)
    tampered_match = all(
        f32(o) == f32(e) for o, e in zip(json.loads(tampered["stdout"])["result"], tampered["expected"])
    )
    checks.append(("mutator_catches_tampered_result", tampered_match is False))

    # 8. key_of groups records consistently for cross-run alignment.
    checks.append(("key_of_structural", key_of(fe) == ("structural", "f_eot_evict")))
    checks.append(("key_of_behavioral", key_of(rec) == ("behavioral", "evict", "d0_zero")))

    ok = all(v for _, v in checks)
    for name, v in checks:
        print(f"  [{'PASS' if v else 'FAIL'}] {name}")
    print(f"--selftest: {'PASS' if ok else 'FAIL'} ({sum(v for _,v in checks)}/{len(checks)})")
    return ok


# ----------------------------------------------------------------------
# --seqtest: PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT
# ----------------------------------------------------------------------

def seqtest(run01, run02):
    checks = []
    contract_path = os.path.join(ROOT, "CAPTURE_CONTRACT.json")
    checks.append(("contract_exists", os.path.exists(contract_path)))
    if not os.path.exists(contract_path):
        print("  [FAIL] contract_exists"); return False
    contract = json.load(open(contract_path))
    pre_gpu_ts = contract.get("pre_gpu_timestamp_utc")
    checks.append(("pre_gpu_timestamp_present", bool(pre_gpu_ts)))

    run01_dir = os.path.join(ROOT, "raw", run01)
    run02_dir = os.path.join(ROOT, "raw", run02)
    checks.append(("run01_dir_exists", os.path.isdir(run01_dir)))
    checks.append(("run02_dir_exists", os.path.isdir(run02_dir)))

    if os.path.isdir(run01_dir) and os.path.isdir(run02_dir):
        m1 = os.path.getmtime(os.path.join(run01_dir, "records.jsonl"))
        m2 = os.path.getmtime(os.path.join(run02_dir, "records.jsonl"))
        checks.append(("run01_records_predate_run02", m1 <= m2))

        import datetime
        pre_gpu_epoch = datetime.datetime.strptime(
            pre_gpu_ts, "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=datetime.timezone.utc).timestamp()
        checks.append(("pre_gpu_predates_run01", pre_gpu_epoch <= m1))

    ok = all(v for _, v in checks)
    for name, v in checks:
        print(f"  [{'PASS' if v else 'FAIL'}] {name}")
    print(f"--seqtest: {'PASS' if ok else 'FAIL'} ({sum(v for _,v in checks)}/{len(checks)})")
    return ok


# ----------------------------------------------------------------------
# --captured: cross-run byte-exact + semantic correctness
# ----------------------------------------------------------------------

def captured(run01, run02):
    r1 = load_records(os.path.join(ROOT, "raw", run01, "records.jsonl"))
    r2 = load_records(os.path.join(ROOT, "raw", run02, "records.jsonl"))

    checks = []
    checks.append(("run01_count_23", len(r1) == 23))
    checks.append(("run02_count_23", len(r2) == 23))

    m1 = {key_of(r): project_record(r) for r in r1}
    m2 = {key_of(r): project_record(r) for r in r2}
    checks.append(("same_key_set", set(m1) == set(m2)))

    mismatches = []
    for k in sorted(set(m1) & set(m2)):
        if m1[k] != m2[k]:
            mismatches.append(k)
    checks.append(("byte_exact_cross_run", len(mismatches) == 0))
    if mismatches:
        print("  mismatched keys:", mismatches)

    # Semantic correctness: every behavioral case matches its oracle at
    # float32 precision, in BOTH runs independently.
    sem_fail = []
    for run_name, recs in [(run01, r1), (run02, r2)]:
        for rec in recs:
            if rec["kind"] != "behavioral":
                continue
            if rec["timed_out"] or rec["returncode"] != 0:
                sem_fail.append((run_name, rec["mode"], rec["case_id"], "non-OK status"))
                continue
            sd = parse_stdout_json(rec)
            ok = all(f32(o) == f32(e) for o, e in zip(sd["result"], rec["expected"]))
            if not ok:
                sem_fail.append((run_name, rec["mode"], rec["case_id"], (sd["result"], rec["expected"])))
    checks.append(("all_behavioral_cases_match_oracle_both_runs", len(sem_fail) == 0))
    if sem_fail:
        for f in sem_fail:
            print("  semantic mismatch:", f)

    # Structural claim: evict has neither op; ctrl has store-only; combine
    # has both -- in BOTH runs.
    struct_fail = []
    for run_name, recs in [(run01, r1), (run02, r2)]:
        by_fn = {r["function"]: r for r in recs if r["kind"] == "structural"}
        e, c, x = by_fn["f_eot_evict"], by_fn["f_eot_ctrl"], by_fn["f_eot_combine"]
        if e["contains_tile_read"] or e["contains_frag_color_store"]:
            struct_fail.append((run_name, "evict should have neither op"))
        if c["contains_tile_read"] or not c["contains_frag_color_store"]:
            struct_fail.append((run_name, "ctrl should have store-only"))
        if not (x["contains_tile_read"] and x["contains_frag_color_store"]):
            struct_fail.append((run_name, "combine should have both ops"))
    checks.append(("structural_claim_holds_both_runs", len(struct_fail) == 0))
    if struct_fail:
        for f in struct_fail:
            print("  structural failure:", f)

    # Paired-control claim: ctrl's result is invariant across all 8 dst
    # sweep values, in both runs, while evict's/combine's result visibly
    # tracks dst (i.e. is NOT constant across the sweep).
    for run_name, recs in [(run01, r1), (run02, r2)]:
        ctrl_results = set()
        evict_results = set()
        for rec in recs:
            if rec["kind"] != "behavioral":
                continue
            sd = parse_stdout_json(rec)
            key = tuple(f32(v) for v in sd["result"])
            if rec["mode"] == "ctrl":
                ctrl_results.add(key)
            elif rec["mode"] == "evict":
                evict_results.add(key)
        checks.append((f"{run_name}_ctrl_result_constant_across_dst_sweep", len(ctrl_results) == 1))
        checks.append((f"{run_name}_evict_result_varies_across_dst_sweep", len(evict_results) == 8))

    ok = all(v for _, v in checks)
    for name, v in checks:
        print(f"  [{'PASS' if v else 'FAIL'}] {name}")
    print(f"--captured: {'PASS' if ok else 'FAIL'} ({sum(v for _,v in checks)}/{len(checks)})")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--captured", action="store_true")
    ap.add_argument("--run01", default="m4_20260828_run01")
    ap.add_argument("--run02", default="m4_20260828_run02")
    args = ap.parse_args()

    if not (args.selftest or args.seqtest or args.captured):
        print("nothing to do; pass --selftest, --seqtest, and/or --captured")
        sys.exit(2)

    ok = True
    if args.selftest:
        print("== --selftest =="); ok = selftest() and ok
    if args.seqtest:
        print("== --seqtest =="); ok = seqtest(args.run01, args.run02) and ok
    if args.captured:
        print("== --captured =="); ok = captured(args.run01, args.run02) and ok

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
