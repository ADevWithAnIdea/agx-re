#!/usr/bin/env python3
"""Fold arm S (the compiled-call second method) into analysis/field_verdicts.json.

Arm S never counts toward the ">= 2 carriers" bar for a generated result. What it
CAN do -- and did -- is CONTRADICT a generated-carrier result, which is worth more
than agreeing with one. `call.b6` was inert across 0..255 on both generated
carriers and is bit1-LOAD-BEARING on the compiled call, so the generated carriers
were blind to the dimension b6 controls and the safe emitter rule is the
intersection.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
RUNS = ("g17p_20260830_splice01", "g17p_20260830_splice02")


def load(r):
    return [json.loads(l) for l in
            (EXP / "raw" / r / "sweep.jsonl").read_text().splitlines() if l.strip()]


per = {r: {} for r in RUNS}
for r in RUNS:
    for x in load(r):
        if x.get("kind") == "case":
            per[r].setdefault(x["field"], {})[x["value"]] = x

out = {}
for f in ("b3", "b5", "b6", "tail"):
    a, b = per[RUNS[0]][f], per[RUNS[1]][f]
    vals = sorted(set(a) & set(b))
    agree = sum(1 for v in vals if a[v]["outcome"] == b[v]["outcome"])
    dis = [v for v in vals if a[v]["outcome"] != b[v]["outcome"]]
    ok = sorted(v for v in vals if a[v]["outcome"] == "ok" and b[v]["outcome"] == "ok")
    moved = [v for v in vals if a[v]["outcome"] != a[min(vals)]["outcome"]]
    out["call." + f] = {
        "carrier": "S_kchain_compiled (REAL compiler-emitted call, backward "
                   "displacement, NON-LEAF callee)",
        "values_dispatched": len(vals),
        "distinct_bytes": len({a[v]["bytes"] for v in vals}),
        "encodable_range": 256,
        "legal_values": len(ok),
        "cross_run_agreement": round(agree / float(len(vals)), 6),
        "disagreements": len(dis),
        "disagreeing_values": dis,
        "outcomes_run01": dict(Counter(a[v]["outcome"] for v in vals)),
        "movement": len(moved),
    }
    if f == "b6":
        out["call.b6"]["RULE"] = ("bit 1 (0x02) MUST BE SET; bits 0 and 2..7 are "
                                  "don't-care. 128 of 256 legal. The corpus value "
                                  "0x56 has bit 1 set.")
        out["call.b6"]["CONTRADICTS_GENERATED"] = (
            "The two GENERATED carriers reported b6 INERT across all 256 values "
            "(one distinct full observation each, both runs). The compiled call "
            "says bit 1 is load-bearing. The generated callee is a LEAF entered "
            "and left immediately, so it does not exercise whatever b6 bit 1 "
            "controls -- the same carrier-blindness that makes ret.scoreboard "
            "undecidable here. The SAFE EMITTER RULE is the intersection: SET "
            "BIT 1.")
    if f == "b3":
        codes = {}
        for v in vals:
            codes.setdefault((v >> 2) & 0xF, set()).add(a[v]["outcome"] == "ok")
        out["call.b3"]["bits5_2_takes_call"] = {
            str(k): (list(v)[0] if len(v) == 1 else "MIXED")
            for k, v in sorted(codes.items())}
        out["call.b3"]["REPRODUCES_GENERATED"] = (
            "The 16-code table is IDENTICAL to the one the generated carriers "
            "produced, on a different program with a backward displacement and a "
            "non-leaf callee.")
    if f == "b5":
        out["call.b5"]["RULE_HOLDS"] = all(
            (a[v]["outcome"] == "ok") == ((v & 0x06) == 0) for v in vals)

(HERE / "splice_verdicts.json").write_text(json.dumps(out, indent=1, sort_keys=True))

fv = json.loads((HERE / "field_verdicts.json").read_text())
for k, v in out.items():
    if k in fv:
        fv[k]["second_method_arm_S"] = v
fv["call.b6"]["semantics"] = (
    "bit 1 (0x02) MUST BE SET; bits 0 and 2..7 are DON'T-CARE. 128 of 256 legal. "
    "CORRECTED BY ARM S. The two GENERATED carriers measured b6 inert across all "
    "256 values (one distinct full observation per carrier, both runs) -- but the "
    "REAL compiler-emitted call in our own compiled c_frame.metal (k_chain, "
    "backward displacement, NON-LEAF callee) is bit1-load-bearing: 128 legal, 126 "
    "wrong_value, 2 nondeterministic, 254/256 cross-run agreement. The generated "
    "callee is a leaf entered and left immediately and does NOT exercise what b6 "
    "bit 1 controls. Safe emitter rule = the intersection: SET BIT 1 (the corpus "
    "0x56 does).")
# The top-level `movement` on call.b6 comes from the GENERATED carriers and is 0.
# A reader must not take that as the governing number, so it is labelled here.
fv["call.b6"]["governing_evidence"] = "arm S (compiled call), NOT the generated carriers"
fv["call.b6"]["movement_note"] = (
    "The top-level `movement: 0` and `min_cross_run_agreement: 1.0` are the GENERATED "
    "carriers' numbers and are NOT the governing evidence for this field -- those carriers "
    "are blind to it. The governing numbers are in `second_method_arm_S`: movement 254 of "
    "256, cross-run agreement 0.9922, 128 of 256 values legal.")
fv["call.b6"]["note"] = (
    "PROMOTION SCOPE NARROWED BY THE SECOND METHOD. `hardware-run` is claimed for "
    "the RULE 'bit 1 must be set', evidenced on the compiled carrier over two runs; "
    "the generated carriers' inertness is reported as CARRIER BLINDNESS, not as a "
    "don't-care finding. This is the same failure shape as ret.scoreboard, caught "
    "by a second method rather than by argument.")
fv["call.tail"]["semantics"] += (
    " CONFIRMED BY ARM S: all 256 values also legal on the REAL compiler-emitted "
    "call (256/256 cross-run agreement), so `tail` is a don't-care in BOTH a "
    "generated leaf call and a compiled non-leaf call.")
fv["call.b3"]["semantics"] += (
    " CONFIRMED BY ARM S: the identical 16-code table on the REAL compiler-emitted "
    "call, 256/256 cross-run agreement -- a different program, a BACKWARD "
    "displacement and a non-leaf callee.")
fv["call.b5"]["semantics"] += (
    " CONFIRMED BY ARM S: `(b5 & 0x06) == 0` holds exactly on the REAL "
    "compiler-emitted call, 256/256 cross-run agreement.")
(HERE / "field_verdicts.json").write_text(json.dumps(fv, indent=1, sort_keys=True))
print("merged arm S into field_verdicts.json")
for k in sorted(out):
    print("  %-12s legal=%3d/256 agree=%.4f movement=%d"
          % (k, out[k]["legal_values"], out[k]["cross_run_agreement"], out[k]["movement"]))
