#!/usr/bin/env python3
"""EXP-0205 OFFLINE GATE SELF-TEST -- no GPU, no device, no SSH.

    python3 analysis/gate_selftest.py      # exit 0 iff all pass

"If your criterion cannot return 'no', it is broken."  This file proves, before
any hardware data exists, that this experiment's gate can come out BOTH ways on
each of the traps that have actually been paid for in this corpus.  It drives
`verdicts.classify` and `verdicts.arm_stats` directly with synthetic records.

T1  WIDTH-1 ARITHMETIC (pitfall 5b).  A 1-bit field has at most ONE value that
    can differ from its own baseline, so a gate written `moved >= 2*max(disagree,1)`
    demands moved >= 2 and refuses every width-1 field BY ARITHMETIC.  Two of
    this experiment's six fields are width 1.  T1 asserts that moved=1,
    disagree=0 PROMOTES.
T2  A GPU FAULT IS NOT MOVEMENT.  An arm whose only "different" values faulted
    in both runs must score moved=0.
T3  DETECTION POWER (pitfall 5a).  An arm whose observable never varies AND
    whose control never fired must come out STILL-UNDERPOWERED -- never
    "inert".  `moved == 0` there is a tautology.
T4  INERTNESS IS REACHABLE.  With a control that DID fire and a non-cache
    field, moved=0 must come out INERT-ROBUST -- otherwise T3 would be passing
    for the wrong reason (a gate that can only ever say "underpowered").
T5  THE CACHE RULE.  For `simd_ballot.cache` / `simd_shuffle.cache`, moved=0
    with a firing generic control but NO in-dimension control must be
    UNRESOLVED-DIMENSION-NOT-EXPRESSED, and with the in-dimension control firing
    must be UNRESOLVED-INERT-IN-TESTED-DIMENSION.  Neither is ever
    `single-template-inference`, and neither is ever emitter-grade.
T6  ALIASING.  An arm whose distinct field values collapse onto identical bytes
    is REFUSED, however cleanly it "moved".
T7  MEASUREMENT FAILURES.  A MALFORMED response is excluded from agreement and
    from values_dispatched, and an arm above 1 % is refused.
T8  DISAGREEMENT.  moved=3, disagree=2 must NOT promote (3 < 2*2).

CLEAN-ROOM: pure host arithmetic over synthetic records.
"""
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "analysis"))
sys.path.insert(0, str(EXP / "harness"))
import verdicts as V             # noqa: E402

FAILS = []
CHECKS = []


def check(name, got, want):
    ok = got == want
    print("%-4s %-48s %s" % ("PASS" if ok else "FAIL", name,
                             "" if ok else "got %r want %r" % (got, want)))
    CHECKS.append(name)
    if not ok:
        FAILS.append(name)


def rec(value, outcome, vals, sec=None, tok="simd_shuffle", bytes_="00"):
    return {"value": value, "outcome": outcome, "bytes": bytes_,
            "token": {"mnemonic": tok},
            "observed": {"vals_u32": vals, "sec_u32": sec or [],
                         "gputime_ns": 5000}}


def arm(cases, base_vals, base_sec=None):
    return {"cases": {c["value"]: c for c in cases},
            "baselines": [{"role": "baseline", "note": "x:open",
                           "outcome": "ok",
                           "observed": {"vals_u32": base_vals,
                                        "sec_u32": base_sec or []}},
                          {"role": "baseline", "note": "x:close",
                           "outcome": "ok",
                           "observed": {"vals_u32": base_vals,
                                        "sec_u32": base_sec or []}}]}


BASE = [1] * 32
DIFF = [2] * 32
SBASE = [7] * 32
SDIFF = [9] * 32


def spec(carrier, field, values, width, baseline_field=0, occ=0):
    return {"carrier": carrier, "field": field, "values": values, "occ": occ,
            "baseline_field": baseline_field, "width": width}


def entry(carrier, field, values, stats):
    return ("%s#%s" % (carrier, field), spec(carrier, field, values, 1), stats)


def stats_from(cases1, cases2, base=BASE, sbase=None):
    return V.arm_stats(arm(cases1, base, sbase), arm(cases2, base, sbase))


def main():
    # ---------------------------------------------------------------- T1
    c = [rec(0, "ok", BASE), rec(1, "wrong_value", DIFF)]
    st = stats_from(c, [rec(0, "ok", BASE), rec(1, "wrong_value", DIFF)])
    check("T1a width-1: moved counted", (st["moved"], st["disagree"]), (1, 0))
    st.update({"encodings_confined_to_field": True,
               "distinct_encodings_expected": 2,
               "measurement_failure_pct": 0.0, "baselines_ok": True})
    e = [entry("sh_bc", "dir", [0, 1], st)]
    ctl = {("sh_bc", 0): {"fired": True}}
    lab, vd, _ = V.classify("simd_shuffle.dir", e, ctl, {})
    check("T1b width-1 field PROMOTES", (lab, vd), ("hardware-run", "LIVE"))

    # ---------------------------------------------------------------- T2
    c1 = [rec(0, "ok", BASE), rec(1, "fault", DIFF)]
    st2 = stats_from(c1, list(c1))
    check("T2 a fault is NOT movement", st2["moved"], 0)

    # ---------------------------------------------------------------- T3
    flat = [rec(v, "ok", BASE) for v in range(4)]
    st3 = stats_from(flat, list(flat))
    st3.update({"encodings_confined_to_field": True,
                "distinct_encodings_expected": 4,
                "measurement_failure_pct": 0.0, "baselines_ok": True})
    e3 = [entry("sh_bc", "dir", [0, 1, 2, 3], st3)]
    lab, vd, _ = V.classify("simd_shuffle.dir", e3, {("sh_bc", 0): {"fired": False}}, {})
    check("T3 no detection power -> CARRIER-UNDECIDABLE",
          (lab, vd), ("untested", "CARRIER-UNDECIDABLE"))

    # ---------------------------------------------------------------- T4
    lab, vd, _ = V.classify("simd_shuffle.dir", e3, {("sh_bc", 0): {"fired": True}}, {})
    check("T4 inertness IS reachable",
          (lab, vd), ("single-template-inference", "INERT-ROBUST"))

    # ---------------------------------------------------------------- T5
    e5 = [entry("sh_reuse", "cache", [0, 1, 2, 3], st3)]
    lab, vd, _ = V.classify("simd_shuffle.cache", e5,
                            {("sh_reuse", 0): {"fired": True}}, {})
    check("T5a cache, no in-dimension control -> UNRESOLVED",
          (lab, vd), ("untested", "UNRESOLVED-DIMENSION-NOT-EXPRESSED"))
    lab, vd, _ = V.classify("simd_shuffle.cache", e5,
                            {("sh_reuse", 0): {"fired": True}},
                            {("sh_reuse", 0): {"fired": True}})
    check("T5b cache, in-dimension control fired -> UNRESOLVED (not inert)",
          (lab, vd), ("untested", "UNRESOLVED-INERT-IN-TESTED-DIMENSION"))

    # in-dimension control detection: sec must move, vals need not
    cs = [rec(0, "ok", BASE, SBASE), rec(1, "ok", BASE, SDIFF)]
    st5 = stats_from(cs, list(cs), BASE, SBASE)
    check("T5c sec_moved detected independently of vals",
          (st5["moved"], st5["sec_moved"]), (0, 1))

    # ---------------------------------------------------------------- T6
    st6 = dict(st)
    st6["encodings_confined_to_field"] = False
    e6 = [entry("sh_bc", "dir", [0, 1], st6)]
    lab, vd, _ = V.classify("simd_shuffle.dir", e6, ctl, {})
    check("T6 aliased encodings are REFUSED",
          (lab, vd), ("untested", "REFUSED-ALIASED"))

    # ---------------------------------------------------------------- T7
    cm1 = [rec(0, "ok", BASE), rec(1, "measurement_failure", None)]
    cm2 = [rec(0, "ok", BASE), rec(1, "ok", DIFF)]
    st7 = stats_from(cm1, cm2)
    check("T7a MALFORMED excluded from values_dispatched",
          (st7["values_dispatched"], st7["measurement_failures"]), (1, 1))
    st7.update({"encodings_confined_to_field": True,
                "distinct_encodings_expected": 2, "baselines_ok": True})
    lab, vd, _ = V.classify("simd_shuffle.dir", [entry("sh_bc", "dir", [0, 1], st7)],
                            ctl, {})
    check("T7b >1 % measurement failures REFUSED",
          (lab, vd), ("untested", "REFUSED-MEASUREMENT-FAILURES"))

    # ---------------------------------------------------------------- T8
    ca = [rec(0, "ok", BASE)] + [rec(v, "ok", DIFF) for v in (1, 2, 3)] + \
         [rec(v, "ok", DIFF) for v in (4, 5)]
    cb = [rec(0, "ok", BASE)] + [rec(v, "ok", DIFF) for v in (1, 2, 3)] + \
         [rec(v, "silent_zero", [0] * 32) for v in (4, 5)]
    st8 = stats_from(ca, cb)
    st8.update({"encodings_confined_to_field": True,
                "distinct_encodings_expected": 6,
                "measurement_failure_pct": 0.0, "baselines_ok": True})
    check("T8a moved/disagree counted", (st8["moved"], st8["disagree"]), (5, 2))
    st8["moved"] = 3                      # force the boundary: 3 < 2*2
    lab, vd, _ = V.classify("simd_shuffle.dir",
                            [entry("sh_bc", "dir", list(range(6)), st8)], ctl, {})
    check("T8b moved(3) < 2*disagree(2) does NOT promote",
          (lab, vd), ("single-template-inference", "INERT-ROBUST"))

    print("\n%d/%d checks passed" % (len(CHECKS) - len(FAILS), len(CHECKS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
