#!/usr/bin/env python3
"""EXP-0207 census: what the compiler actually emitted, per carrier.

A census is evidence in its own right and it is read BEFORE any sweep verdict:
if a new carrier's target instruction is byte-identical to a carrier already
tried, it is NOT a new dimension and the sweep on it is one more arm that cannot
express the field.  Reads raw/<run>/sweep.jsonl `arm_meta` records only.

  python3 analysis/census.py [raw/<run_id> ...]
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)


def main():
    dirs = sys.argv[1:] or sorted(glob.glob(os.path.join(EXP, "raw", "*"))) + \
        sorted(glob.glob(os.path.join(EXP, "work", "*")))
    out = {}
    for d in dirs:
        f = os.path.join(d, "sweep.jsonl")
        if not os.path.isfile(f):
            continue
        for line in open(f, errors="replace"):
            try:
                r = json.loads(line)
            except Exception:                                  # noqa: BLE001
                continue
            if r.get("kind") == "arm_meta":
                out[r["arm"]] = {
                    "run": os.path.basename(d), "instr": r["instr"], "stage": r["stage"],
                    "how": r.get("how"), "occurrences": r.get("occurrences"),
                    "instr_hex": r.get("instr_hex"),
                    "baseline_field_values": r.get("baseline_field_values"),
                    "program_len": r.get("program_len"),
                    "tokenize_leftover": (r.get("tokenize_leftover") or "")[:40],
                    "carrier": r.get("carrier"),
                }
            elif r.get("kind") in ("arm_not_attempted", "arm_error"):
                out.setdefault(r["arm"], {}).update(
                    {"run": os.path.basename(d), "status": r.get("kind"),
                     "why": r.get("why") or r.get("error", "")[:300]})
    json.dump(out, open(os.path.join(HERE, "census.json"), "w"), indent=1, sort_keys=True)
    byinstr = {}
    for a, v in sorted(out.items()):
        byinstr.setdefault(v.get("instr", "?"), []).append((a, v))
    for ins, rows in sorted(byinstr.items()):
        print("=== %s" % ins)
        for a, v in rows:
            if "instr_hex" in v:
                print("  %-12s occ=%-3s hex=%-26s %s"
                      % (a, v.get("occurrences"), v.get("instr_hex"),
                         json.dumps(v.get("baseline_field_values"), sort_keys=True)))
            else:
                print("  %-12s %s : %s" % (a, v.get("status"), str(v.get("why"))[:150]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
