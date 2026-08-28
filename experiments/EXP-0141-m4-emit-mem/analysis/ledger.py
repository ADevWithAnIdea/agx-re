#!/usr/bin/env python3
"""EXP-0141 field ledger: for the ten instructions in this family, how many
fields were blocking before, and what this experiment actually moved.

Reads tools/agx-isa/validation.json READ-ONLY (the orchestrator owns it; this
experiment does not edit it) and analysis/field_verdicts.json.
"""
import json
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
REPO = EXP.parents[1]
FAM = ["atomic_mem", "atomic_rmw", "atomic_tg", "dev_scoreboard_fence",
       "device_load", "device_store", "mem_fence", "mem_fence8",
       "tg_addr_compute", "threadgroup_barrier"]
EMITTER = ("hardware-run", "isolated-byte-diff")


def main():
    val = json.load((REPO / "tools" / "agx-isa" / "validation.json").open())["instructions"]
    new = json.load((EXP / "analysis" / "field_verdicts.json").open())
    rows, tot_block, moved, still = [], 0, 0, []
    for m in FAM:
        fields = {f: d for f, d in val[m].items() if not f.startswith("_")}
        block = [f for f, d in fields.items() if d["label"] not in EMITTER]
        tot_block += len(block)
        got = []
        for f in block:
            e = new.get("%s.%s" % (m, f))
            if e and e["label"] in EMITTER:
                got.append(f)
            else:
                # byte-level arms cover several db fields at once
                joint = [k for k in new
                         if k.startswith(m + ".") and f in k.split(".", 1)[1].split("|")
                         and new[k]["label"] in EMITTER]
                (got if joint else still).append(f) if joint else still.append((m, f))
        moved += len(got)
        rows.append((m, len(fields), len(block), len(got), len(block) - len(got)))
    print("%-22s %6s %9s %8s %9s" % ("instruction", "fields", "blocking", "moved", "remaining"))
    for r in rows:
        print("%-22s %6d %9d %8d %9d" % r)
    print("%-22s %6s %9d %8d %9d" % ("TOTAL", "", tot_block, moved, tot_block - moved))
    print()
    print("still blocking:")
    for m, f in still:
        e = new.get("%s.%s" % (m, f))
        print("   %-24s %-18s %s" % (m, f, (e or {}).get("label", "untested")))
    json.dump({"total_blocking_before": tot_block, "moved_to_emitter_grade": moved,
               "still_blocking": [{"instr": m, "field": f} for m, f in still],
               "per_instruction": [{"instr": r[0], "fields": r[1], "blocking": r[2],
                                    "moved": r[3], "remaining": r[4]} for r in rows]},
              (EXP / "analysis" / "ledger.json").open("w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
