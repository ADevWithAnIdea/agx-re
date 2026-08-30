#!/usr/bin/env python3
"""EXP-0180 -- the MEASURED hardware length rule for byte0 == 0x10, and the two exact
fault walls. Reads the LEN arm of both gated runs; writes analysis/length_rule.json.

Method: four 2-byte `mov_imm` markers are placed at the instruction's byte +6. The number
that SURVIVE reads the hardware's instruction length directly -- 4 -> 6B, 3 -> 8B, 2 -> 10B,
1 -> 12B, 0 -> 14B. Five distinguishable outcomes, host-computable, no interpretation.
Zero point (the chain with no instruction in front of it) must give 4.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent


def load(run):
    return [json.loads(l) for l in open(str(EXP / "raw" / run / "sweep.jsonl"))]


def main(runs):
    tab, flt, zero = defaultdict(set), set(), {}
    n = 0
    for run in runs:
        for r in load(run):
            if r["arm"] != "LEN":
                continue
            if r["field"] == "__falsifier_F4_zero_point":
                zero[run] = r.get("hw_markers")
                continue
            n += 1
            b = bytes.fromhex(r["bytes"])
            k = (b[2] & 7, b[4] & 3)
            if r["outcome"] == "fault":
                flt.add((b[2], b[4]))
            elif r.get("hw_markers") is not None:
                tab[k].add(6 + 2 * (4 - r["hw_markers"]))
    rule = {}
    amb = {}
    for k, v in tab.items():
        if len(v) == 1:
            rule["%d,%d" % k] = list(v)[0]
        else:
            amb["%d,%d" % k] = sorted(v)
    fb2 = sorted({b2 for b2, _ in flt})
    out = {
        "measured_length_by_opsel_and_byte4_mod4": rule,
        "cells_with_more_than_one_observed_length": amb,
        "cases": n, "runs": runs, "zero_point_markers": zero,
        "fault_wall": {
            "rule": "fault <=> (byte+2 >> 3) >= 16 AND (byte+2 & 7) in {4,5}",
            "holds_with_zero_counterexamples": all((b2 >> 3) >= 16 and (b2 & 7) in (4, 5)
                                                   for b2 in fb2),
            "n_faulting_cases": len(flt), "faulting_byte2_values": fb2},
        "db_json_rule": "6, or 8 if (byte+2 & 0x02)   [length_rule.byte0_table['0x10']]",
        "isadb_code_rule": "(6 + 2*(b4&3)) if (b4&3) else 8, when byte+2 & 2; else 6 + 2*(b4&3)",
        "bound": ("bytes +6.. are the marker chain in every case, so a length dependence on "
                  "byte +6 or later is UNTESTED. Within bytes 0..5 the rule is exact: no "
                  "(opsel, byte+4 & 3) cell shows more than one length."),
    }
    # score both committed models against the measurement
    def db_pred(op, m):
        return 8 if ((op & 2)) else 6

    def isadb_pred(op, m):
        if op & 2:
            return (6 + 2 * m) if m else 8
        return 6 + 2 * m
    for name, fn in (("db_json_rule", db_pred), ("isadb_code_rule", isadb_pred)):
        wrong = [k for k in sorted(rule) if rule[k] != fn(*map(int, k.split(",")))]
        out[name + "_wrong_cells"] = {"n": len(wrong), "of": len(rule), "cells": wrong}
    (EXP / "analysis" / "length_rule.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("MEASURED LENGTH, byte0==0x10   (opsel = byte+2 & 7, m = byte+4 & 3)")
    print("opsel |  m=0  m=1  m=2  m=3")
    for op in range(8):
        print("  %d   | %s" % (op, "  ".join("%4s" % rule.get("%d,%d" % (op, m), "-")
                                             for m in range(4))))
    print("\nambiguous cells:", amb or "NONE")
    print("zero point:", zero)
    print("fault wall:", json.dumps(out["fault_wall"]["rule"]),
          "holds:", out["fault_wall"]["holds_with_zero_counterexamples"],
          "n=%d" % out["fault_wall"]["n_faulting_cases"])
    print("db.json rule wrong in %d/%d cells; isadb code rule wrong in %d/%d cells"
          % (out["db_json_rule_wrong_cells"]["n"], len(rule),
             out["isadb_code_rule_wrong_cells"]["n"], len(rule)))
    print("  isadb wrong cells (opsel,m):", out["isadb_code_rule_wrong_cells"]["cells"])


if __name__ == "__main__":
    main(sys.argv[1:] or ["g17p_run02", "g17p_run03"])
