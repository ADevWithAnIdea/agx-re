#!/usr/bin/env python3
"""EXP-0146: build analysis/field_verdicts.json (FIELD-SWEEP-PROTOCOL §5).

Inputs: the two gated runs (run01, run03), the adjudication pass (run04) whose 5x serial
result OVERRIDES the gated pair for every case it covers, and an authored semantics table
(this file's SEMANTICS dict -- the interpretation, which is mine and is stated separately
from the observation).

  python3 analysis/verdicts.py
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import loadruns as L  # noqa: E402

GATE_A, GATE_B, ADJ = "run01", "run03", "run04"
EVID = ["EXP-0146"]
TARGET = "M4"


def compact(vals):
    vals = sorted(v for v in vals if isinstance(v, int))
    out = []
    for v in vals:
        if out and v == out[-1][1] + 1:
            out[-1][1] = v
        else:
            out.append([v, v])
    return ", ".join("0x%x" % a if a == b else "0x%x-0x%x" % (a, b) for a, b in out)


def build():
    A, B = L.load(GATE_A), L.load(GATE_B)
    try:
        C = L.load(ADJ)
    except FileNotFoundError:
        C = {"_order": []}
    widths = L.field_widths()

    per = collections.defaultdict(dict)      # (instr,carrier,field) -> value -> outcome
    unstable = collections.defaultdict(list)
    adjudicated = collections.defaultdict(int)
    for k in A["_order"]:
        if k not in B:
            continue
        instr, carrier, field, valjson = k
        v = json.loads(valjson)
        ra, rb = A[k], B[k]
        if k in C:                                     # adjudicated: run04 wins
            rc = C[k]
            per[(instr, carrier, field)][valjson] = rc["outcome"]
            adjudicated[(instr, carrier, field)] += 1
            if not rc["observed"].get("stable", True):
                unstable[(instr, carrier, field)].append(v)
        elif ra["outcome"] == rb["outcome"] and (L.words(ra) == L.words(rb)):
            per[(instr, carrier, field)][valjson] = ra["outcome"]
        else:
            per[(instr, carrier, field)][valjson] = "UNRESOLVED"
            unstable[(instr, carrier, field)].append(v)

    # which (instr,carrier) pairs are PROVEN LIVE: some field of that instruction, in that
    # carrier, demonstrably changed the output
    live = set()
    for (instr, carrier, field), vals in per.items():
        if any(o not in ("ok", "UNRESOLVED") for o in vals.values()):
            live.add((instr, carrier))

    out = {}
    for (instr, carrier, field), vals in sorted(per.items()):
        if instr.startswith("_"):
            continue
        w = widths.get(instr, {}).get(field)
        n = len(vals)
        dense = (w is not None and n == (1 << w))
        byte_probe = field.startswith("byte+")
        if byte_probe:
            dense = (n == 256)
        oc = collections.Counter(vals.values())
        ok_vals = [json.loads(k) for k, o in vals.items() if o == "ok"]
        unres = oc.get("UNRESOLVED", 0)
        key = "%s.%s@%s" % (instr, field, carrier)
        rng = "%d values tested%s" % (n, " (full %d-bit dense)" % w if dense and w else
                                       (" (all 256 byte values)" if dense else ""))
        rng += "; ok at {%s}" % (compact(ok_vals) if ok_vals and len(ok_vals) < 40
                                  else ("%d values" % len(ok_vals)))
        out[key] = {
            "instr": instr, "field": field, "carrier": carrier, "db_width": w,
            "values_tested": n, "full_dense": dense,
            "outcomes": dict(oc), "unresolved": unres,
            "adjudicated_cases": adjudicated.get((instr, carrier, field), 0),
            "instruction_proven_live_in_carrier": (instr, carrier) in live,
            "range": rng, "target": TARGET, "evidence": EVID,
            "ok_values": sorted(ok_vals) if all(isinstance(x, int) for x in ok_vals) else ok_vals,
        }
        # provisional label; the authored table below may override with a justification
        if unres > 0.02 * n:
            lab = "untested"
        elif not dense:
            lab = "untested"
        elif (instr, carrier) not in live:
            lab = "untested"
        elif oc.get("ok", 0) == n:
            lab = "hardware-run"          # exhaustively swept and inert -- an inertness claim
        else:
            lab = "hardware-run"
        out[key]["label"] = lab
    return out


if __name__ == "__main__":
    v = build()
    Path(HERE / "field_verdicts_raw.json").write_text(json.dumps(v, indent=1, sort_keys=True))
    lab = collections.Counter(x["label"] for x in v.values())
    print("fields:", len(v), dict(lab))
