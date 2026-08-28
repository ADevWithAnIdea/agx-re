#!/usr/bin/env python3
"""Standing-gate verifier for EXP-0120.

  python3 verify.py --selftest
  python3 verify.py --seqtest --run01 <id> --run02 <id>
  python3 verify.py --captured --run01 <id> --run02 <id>

--selftest never touches raw/; it exercises the parsing/comparison logic
against small fixtures drawn from real (pre-freeze, work/pilot_*) log
excerpts, per CAPTURE_CONTRACT.json's "fixtures from RECORDED REALITY" rule.

--seqtest checks the on-disk state machine PRE_GPU -> RUN01_PRESENT ->
RUN02_PRESENT without inspecting record contents.

--captured is the byte-exact reproducibility gate: for every Sweep B / Sweep C
case, the (size) multiset and selector-CALL histogram must be identical
between run01 and run02 (GPU VA / CPU address fields are excluded from this
comparison by construction -- analyze.py never emits them into the gated
fields it uses here). Sweep A (timing) and Sweep D (limits) are reported for
context but are NOT part of the pass/fail gate (see PRE_REGISTRATION.md and
CAPTURE_CONTRACT.json "gate" section for why).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from iotrace_parse import parse_iotrace_log
from analyze import linreg


def selftest():
    ok = True

    # --- linreg on exact synthetic linear data ---
    xs = [0, 1, 2, 3, 4]
    ys = [1.0, 3.0, 5.0, 7.0, 9.0]  # y = 1 + 2x
    fit = linreg(xs, ys)
    if not (abs(fit["intercept_ms"] - 1.0) < 1e-9 and abs(fit["slope_ms_per_tri"] - 2.0) < 1e-9
            and abs(fit["r2"] - 1.0) < 1e-9):
        print("FAIL linreg exact-fit", fit)
        ok = False
    else:
        print("PASS linreg exact-fit")

    # --- linreg degenerate (single point) returns None, not a crash ---
    if linreg([1], [1.0]) is not None:
        print("FAIL linreg degenerate should return None")
        ok = False
    else:
        print("PASS linreg degenerate")

    # --- parse_iotrace_log against a REAL captured fixture (recorded reality) ---
    fixture = os.path.join(HERE, "fixtures", "pilot2_excerpt.log")
    if not os.path.exists(fixture):
        print(f"FAIL missing fixture {fixture}")
        ok = False
    else:
        r = parse_iotrace_log(fixture)
        # Ground truth established by independent `grep -c`/`awk` against the
        # same real log during pre-freeze calibration (work/pilot2.log,
        # N=1000, accumulate mode, G17P_DUMP_BEFORE_COMMIT=1): 47 sel=9
        # CALLs total, 45 BODUMP handle lines, 4 CALLs of any selector after
        # the pre-commit dump point but ZERO of them are sel=9 (verified via
        # `tail -n +<BODUMP-begin-line> pilot2.log | grep ^CALL | grep -c
        # 'sel=9(0x9)'` => 0, while the unfiltered CALL count after that
        # point is 4: two sel=15, one sel=17(0x11) "completion/notify", one
        # sel=8 "create queue" -- i.e. no *new resource registration* happens
        # after encode-time, though a few non-sel9 calls do).
        n_sel9_after = sum(
            1 for m in __import__("re").finditer(r"^CALL.*sel=9\(0x9\)", open(fixture).read(), __import__("re").M)
        )
        checks = [
            (r["sel9_calls"] == 47, f"sel9_calls={r['sel9_calls']} want 47"),
            (r["n_bo"] == 45, f"n_bo={r['n_bo']} want 45"),
            (r["calls_after_first_bodump"] == 4, f"calls_after_first_bodump={r['calls_after_first_bodump']} want 4"),
            (r["had_bodump"] is True, "had_bodump should be True"),
            (all(sz > 0 for sz in r["size_multiset"]) and max(r["size_multiset"]) < 0x1000000,
             "sanity: multiset entries look like plausible BO sizes, not raw VAs"),
        ]
        for cond, msg in checks:
            if not cond:
                print(f"FAIL fixture parse: {msg}")
                ok = False
        if all(c for c, _ in checks):
            print("PASS parse_iotrace_log against recorded fixture")

    # --- multiset/histogram invariance detection: same vs different ---
    same_a = {"size_multiset": [1, 2, 3]}
    same_b = {"size_multiset": [1, 2, 3]}
    diff_c = {"size_multiset": [1, 2, 4]}
    if json.dumps(same_a["size_multiset"]) != json.dumps(same_b["size_multiset"]):
        print("FAIL invariance-detection same-case")
        ok = False
    elif json.dumps(same_a["size_multiset"]) == json.dumps(diff_c["size_multiset"]):
        print("FAIL invariance-detection should-differ-case")
        ok = False
    else:
        print("PASS invariance-detection same/different discrimination")

    return ok


def seqtest(run01, run02):
    ok = True
    contract_path = os.path.join(EXP_ROOT, "CAPTURE_CONTRACT.json")
    if not os.path.exists(contract_path):
        print("FAIL PRE_GPU: CAPTURE_CONTRACT.json missing")
        return False
    with open(contract_path) as f:
        contract = json.load(f)
    print(f"PASS PRE_GPU: contract present, frozen_at_utc={contract['frozen_at_utc']}")

    run01_dir = os.path.join(EXP_ROOT, "raw", run01)
    run01_complete = os.path.join(run01_dir, "COMPLETE")
    if not os.path.exists(run01_complete):
        print(f"FAIL RUN01_PRESENT: {run01_complete} missing")
        return False
    with open(os.path.join(run01_dir, "manifest.json")) as f:
        m1 = json.load(f)
    if m1["contract_frozen_at_utc"] != contract["frozen_at_utc"]:
        print("FAIL RUN01_PRESENT: run01 manifest contract timestamp does not match current contract")
        ok = False
    else:
        print("PASS RUN01_PRESENT")

    run02_dir = os.path.join(EXP_ROOT, "raw", run02)
    run02_complete = os.path.join(run02_dir, "COMPLETE")
    if not os.path.exists(run02_complete):
        print(f"FAIL RUN02_PRESENT: {run02_complete} missing")
        return False
    with open(os.path.join(run02_dir, "manifest.json")) as f:
        m2 = json.load(f)
    if m2["contract_frozen_at_utc"] != contract["frozen_at_utc"]:
        print("FAIL RUN02_PRESENT: run02 manifest contract timestamp does not match current contract")
        ok = False
    elif m2["started_utc"] < m1["started_utc"]:
        print("FAIL RUN02_PRESENT: run02 started before run01 (ordering violated)")
        ok = False
    else:
        print("PASS RUN02_PRESENT")

    return ok


def captured(run01, run02):
    p1 = os.path.join(HERE, f"{run01}.json")
    p2 = os.path.join(HERE, f"{run02}.json")
    for p in (p1, p2):
        if not os.path.exists(p):
            print(f"FAIL missing analysis output {p} (run analyze.py first)")
            return False
    with open(p1) as f:
        a1 = json.load(f)
    with open(p2) as f:
        a2 = json.load(f)

    ok = True
    for sw in ("B", "C"):
        s1 = {c["case_id"]: c for c in a1[f"sweep_{sw}"]["cases"]}
        s2 = {c["case_id"]: c for c in a2[f"sweep_{sw}"]["cases"]}
        if set(s1) != set(s2):
            print(f"FAIL sweep {sw}: case_id sets differ between runs: {set(s1) ^ set(s2)}")
            ok = False
            continue
        n_match = 0
        for cid in sorted(s1):
            c1, c2 = s1[cid], s2[cid]
            m1_ = c1.get("size_multiset")
            m2_ = c2.get("size_multiset")
            h1_ = c1.get("selector_histogram")
            h2_ = c2.get("selector_histogram")
            l1_ = c1.get("large_region_multiset_excluding_own_buffers")
            l2_ = c2.get("large_region_multiset_excluding_own_buffers")
            if m1_ == m2_ and h1_ == h2_ and l1_ == l2_:
                n_match += 1
            else:
                print(f"FAIL sweep {sw} case {cid}: mismatch")
                if m1_ != m2_:
                    print(f"   size_multiset run01={m1_}")
                    print(f"   size_multiset run02={m2_}")
                if h1_ != h2_:
                    print(f"   selector_histogram run01={h1_}")
                    print(f"   selector_histogram run02={h2_}")
                ok = False
        print(f"sweep {sw}: {n_match}/{len(s1)} cases byte-exact reproduced (gated: size_multiset + selector_histogram, VA/CPU excluded)")

    if ok:
        print("PASS --captured: all Sweep B/C cases byte-exact reproduced across run01/run02")
    else:
        print("FAIL --captured")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--captured", action="store_true")
    ap.add_argument("--run01")
    ap.add_argument("--run02")
    args = ap.parse_args()

    overall = True
    if args.selftest:
        overall &= selftest()
    if args.seqtest:
        if not (args.run01 and args.run02):
            print("--seqtest requires --run01/--run02")
            sys.exit(2)
        overall &= seqtest(args.run01, args.run02)
    if args.captured:
        if not (args.run01 and args.run02):
            print("--captured requires --run01/--run02")
            sys.exit(2)
        overall &= captured(args.run01, args.run02)

    if not (args.selftest or args.seqtest or args.captured):
        ap.print_help()
        sys.exit(2)

    print("OVERALL:", "PASS" if overall else "FAIL")
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
