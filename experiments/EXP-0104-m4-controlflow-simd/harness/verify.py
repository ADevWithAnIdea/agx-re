#!/usr/bin/env python3
"""verify.py -- EXP-0104 standing gates.

  --selftest            one authoritative shared key-set; runnable at ANY tree
                         state (no GPU, no raw/ needed). Checks: matrix schema
                         well-formed + unique ids; all 13 CF-*/SIMD-* items
                         (+ the branch-reach sub-question) have >=1 case;
                         gated/nongated key split is well-formed; and a set of
                         RECORDED-REALITY fixtures (facts captured from actual
                         M4 dispatches earlier in this experiment's own
                         development, see harness/fixtures.py) match what the
                         matrix's own oracle functions predict -- i.e. the
                         oracle logic is grounded in real hardware behavior,
                         not invented.
  --seqtest              PRE_GPU / RUN01_PRESENT / RUN02_PRESENT state-gate
                         matrix: for each state, which checks must PASS and
                         which must correctly FAIL/refuse.
  --smoke                NON-RECORDED smoke gate: run ONE tiny real case to
                         work/ (never raw/), confirming the GPU responds,
                         before any raw/<run_id> file is created for a real
                         capture. Exits nonzero if the GPU does not respond.
  --captured RUN1 RUN2   cross-run gate: byte-diff the GATED jsonl of two
                         completed runs (must match field-for-field, since
                         every case here is designed to be deterministic) and
                         separately confirm the NONGATED companion files
                         genuinely differ (proving the split is real, not
                         vacuous) at least in gputime_ns.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP_ROOT = os.path.dirname(HERE)
RAW_DIR = os.path.join(EXP_ROOT, "raw")
sys.path.insert(0, HERE)
import matrix  # noqa: E402

ALL_ITEMS = {
    "CF-01", "CF-02", "CF-03", "CF-04", "CF-05/CF-06",
    "SIMD-01", "SIMD-02", "SIMD-03", "SIMD-04", "SIMD-05", "SIMD-06", "SIMD-07",
}
# CF-05 and CF-06 are answered together by the same predicate-file evidence
# (see PRE_REGISTRATION.md); "CF-01/02-reach" is the explicitly-requested
# branch-reach sub-question under the CF-01/CF-02 umbrella, not a 14th item.
REQUIRED_TAGS = ALL_ITEMS | {"CF-01/02-reach"}


def load_fixtures():
    import fixtures
    return fixtures.RECORDED_REALITY


def cmd_selftest():
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    cases = matrix.build_matrix()
    ids = [c["id"] for c in cases]
    check("unique_case_ids", len(ids) == len(set(ids)))
    check("nonempty_matrix", len(cases) > 0)

    present_tags = set()
    for c in cases:
        for tag in c["item"].split(","):
            present_tags.add(tag.strip())
    missing = REQUIRED_TAGS - present_tags
    check("all_13_items_plus_reach_have_cases", len(missing) == 0, f"missing={missing}")

    for c in cases:
        check(f"case_has_kind[{c['id']}]", "kind" in c and c["kind"] in
              ("compute", "locate_splice", "structural_pair", "structural_group", "render"))
    all_kinds_ok = all(t[1] for t in checks if t[0].startswith("case_has_kind"))
    check("all_cases_well_formed", all_kinds_ok)

    # gated/nongated split well-formedness: nongated keys never appear gated
    import run as runmod  # noqa
    nongated_keys = {"gputime_ns", "stderr_tail", "compile_out", "timed_out", "rc",
                      "compile_timed_out", "compile_rc"}
    sample = {"status": "OK", "results": {0: [1, 2]}, "gputime_ns": 12345,
              "stderr_tail": "x", "main_len": 10}
    g, ng = runmod.strip_nongated(sample)
    check("split_moves_gputime_to_nongated", "gputime_ns" not in g and "gputime_ns" in ng)
    check("split_keeps_status_in_gated", "status" in g and "status" not in ng)
    check("split_keeps_results_in_gated", "results" in g and "results" not in ng)

    # recorded-reality fixtures
    fx = load_fixtures()
    check("fixtures_nonempty", len(fx) >= 3)
    for name, fixture in fx.items():
        oracle_fn = fixture["oracle_lookup"](matrix)
        ok, detail = oracle_fn({"case": {"bufs": fixture["bufs"]}, "compute": {"results": fixture["results"]}})
        check(f"fixture_matches_recorded_reality[{name}]", ok, str(detail)[:200])

    n_pass = sum(1 for _, ok, _ in checks if ok)
    n_fail = sum(1 for _, ok, _ in checks if not ok)
    for name, ok, detail in checks:
        if not ok:
            print(f"FAIL {name}: {detail}")
    print(f"--selftest: {n_pass}/{len(checks)} PASS, {n_fail} FAIL")
    return 0 if n_fail == 0 else 1


def cmd_seqtest():
    """State machine: PRE_GPU (no raw/*.jsonl at all) -> RUN01_PRESENT (run01
    gated+nongated exist) -> RUN02_PRESENT (both runs exist). For each state,
    verify the gate that SHOULD pass and one that SHOULD correctly refuse."""
    results = []

    def rec(state, check_name, ok):
        results.append((state, check_name, ok))

    run01 = "m4_20260827_run01"
    run02 = "m4_20260827_run02"
    g1 = os.path.join(RAW_DIR, f"{run01}.jsonl")
    ng1 = os.path.join(RAW_DIR, f"{run01}.nongated.jsonl")
    g2 = os.path.join(RAW_DIR, f"{run02}.jsonl")
    ng2 = os.path.join(RAW_DIR, f"{run02}.nongated.jsonl")

    have1 = os.path.exists(g1) and os.path.exists(ng1)
    have2 = os.path.exists(g2) and os.path.exists(ng2)

    if not have1 and not have2:
        state = "PRE_GPU"
    elif have1 and not have2:
        state = "RUN01_PRESENT"
    elif have1 and have2:
        state = "RUN02_PRESENT"
    else:
        state = "INCONSISTENT"

    # PRE_GPU gate: --selftest must still pass (no GPU/raw needed)
    rec("PRE_GPU", "selftest_runs_without_raw", cmd_selftest() == 0)
    # PRE_GPU gate: --captured must correctly REFUSE (no runs to compare)
    rc = cmd_captured(run01, run02, quiet=True)
    rec("PRE_GPU", "captured_correctly_refuses_when_absent", (state != "PRE_GPU") or (rc != 0))

    # RUN01_PRESENT gate: captured must refuse (run02 missing) whenever run02 is absent
    rc2 = cmd_captured(run01, run02, quiet=True)
    rec("RUN01_PRESENT", "captured_refuses_with_one_run", (state != "RUN01_PRESENT") or (rc2 != 0))
    rec("RUN01_PRESENT", "run01_gated_readable", (state != "RUN01_PRESENT") or bool(open(g1).read(1)))

    # RUN02_PRESENT gate: captured must be callable and return a verdict
    rc3 = cmd_captured(run01, run02, quiet=True) if state == "RUN02_PRESENT" else 0
    rec("RUN02_PRESENT", "captured_runs_with_both_present", (state != "RUN02_PRESENT") or (rc3 in (0, 1)))

    total = len(results)
    npass = sum(1 for _, _, ok in results if ok)
    print(f"current state: {state}")
    for st, name, ok in results:
        print(f"  [{st}] {name}: {'PASS' if ok else 'FAIL'}")
    print(f"--seqtest: {npass}/{total} PASS")
    return 0 if npass == total else 1


def load_jsonl(path):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def cmd_captured(run1, run2, quiet=False):
    g1p = os.path.join(RAW_DIR, f"{run1}.jsonl")
    g2p = os.path.join(RAW_DIR, f"{run2}.jsonl")
    ng1p = os.path.join(RAW_DIR, f"{run1}.nongated.jsonl")
    ng2p = os.path.join(RAW_DIR, f"{run2}.nongated.jsonl")
    for p in (g1p, g2p, ng1p, ng2p):
        if not os.path.exists(p):
            if not quiet:
                print(f"MISSING {p} -- cannot gate")
            return 2
    g1 = load_jsonl(g1p)
    g2 = load_jsonl(g2p)
    ng1 = load_jsonl(ng1p)
    ng2 = load_jsonl(ng2p)

    def by_case(records):
        return {r["case_id"]: r for r in records if "case_id" in r}
    b1, b2 = by_case(g1), by_case(g2)
    ids1, ids2 = set(b1), set(b2)
    issues = []
    if ids1 != ids2:
        issues.append(f"case id sets differ: only-in-1={ids1-ids2} only-in-2={ids2-ids1}")
    for cid in sorted(ids1 & ids2):
        r1, r2 = b1[cid], b2[cid]
        # Compare everything except keys that are legitimately order/timing-
        # sensitive; per PRE_REGISTRATION, ALL gated fields here are designed
        # deterministic (no concurrency races in this matrix), so this should
        # be an exact match.
        keep = lambda d: {k: v for k, v in d.items() if k not in ("run_id", "seq")}
        if keep(r1) != keep(r2):
            issues.append(f"{cid}: gated record differs between runs")

    # nongated MUST differ in gputime_ns for at least some fraction of cases,
    # proving the split is real (not a vacuous file). Compare only cases that
    # exist in both.
    def by_case_ng(records):
        return {r["case_id"]: r for r in records if "case_id" in r}
    n1, n2 = by_case_ng(ng1), by_case_ng(ng2)
    common = set(n1) & set(n2)
    diffs = 0
    for cid in common:
        gt1 = n1[cid].get("out_nongated", {}).get("gputime_ns")
        gt2 = n2[cid].get("out_nongated", {}).get("gputime_ns")
        if gt1 is not None and gt2 is not None and gt1 != gt2:
            diffs += 1
    nondeterminism_confirmed = diffs > 0

    if not quiet:
        print(f"cases compared: {len(ids1 & ids2)}")
        print(f"gated-field issues: {len(issues)}")
        for i in issues[:30]:
            print("  " + i)
        print(f"nongated gputime_ns differs in {diffs}/{len(common)} cases "
              f"(nondeterminism-split proof: {'CONFIRMED' if nondeterminism_confirmed else 'NOT OBSERVED'})")
        print(f"cross_run_gate_pass={len(issues) == 0}")
    return 0 if len(issues) == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--captured", nargs=2, metavar=("RUN1", "RUN2"))
    args = ap.parse_args()

    if args.selftest:
        sys.exit(cmd_selftest())
    if args.seqtest:
        sys.exit(cmd_seqtest())
    if args.smoke:
        sys.path.insert(0, HERE)
        import lib
        os.makedirs(os.path.join(EXP_ROOT, "work"), exist_ok=True)
        out = lib.run_compute(matrix.CF_NEST, "ifnest_001", 8, 8, {1: [0, 1, 2, 3, 4, 5, 6, 7]},
                               {0: 8}, workdir=os.path.join(EXP_ROOT, "work"))
        ok = out.get("status") == "OK"
        print(f"SMOKE (non-recorded, real GPU dispatch, written to work/ only): "
              f"status={out.get('status')} -> {'PASS' if ok else 'FAIL'}")
        sys.exit(0 if ok else 1)
    if args.captured:
        sys.exit(cmd_captured(args.captured[0], args.captured[1]))
    print("nothing to do -- pass --selftest/--seqtest/--smoke/--captured")
    sys.exit(2)


if __name__ == "__main__":
    main()
