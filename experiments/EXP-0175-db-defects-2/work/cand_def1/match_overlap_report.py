#!/usr/bin/env python3
"""Report fields whose span overlaps their own descriptor's `match`.

DEF-0170-1. A `match` entry CONTROLS every bit it spans -- it pins each to a
value, zero bits included. So a field overlapping its own match is a descriptor
defect, and there is no safe way to resolve the conflict silently:

  * OR-ing match then field (the original assemble()) left match-set bits STUCK
    at 1, silently UNDER-COVERING any sweep driven through it: `iter.grp`
    reached 8 of 256 encodings while its experiment reported 256 dispatched.
  * clearing the span then OR-ing (the first fix) lets the field override the
    match and silently emits A DIFFERENT INSTRUCTION.

assemble() now REFUSES the conflict instead. This report exists so the
underlying descriptor defects are visible rather than latent.

The zero-free-bit rows matter most: those "fields" have exactly ONE legal value,
so they are part of the match. An emitter-grade label on one is vacuous -- there
is no value for an implementer to choose -- and worse, it tells them a field
exists where none does.

    python3 tools/agx-isa/match_overlap_report.py

CLEAN-ROOM: pure analysis over our own db.json + validation.json.
"""
import json, os, sys

D = os.path.dirname(os.path.abspath(__file__))
EMIT = {"hardware-run", "isolated-byte-diff"}


def main():
    db = json.load(open(os.path.join(D, "db.json")))
    val = json.load(open(os.path.join(D, "validation.json")))
    emittable = set(val["coverage"]["emittable_mnemonics"])
    rows = []
    for i in db["instructions"]:
        covered = 0
        for (s, w, _v) in i.get("match", []):
            covered |= ((1 << w) - 1) << s
        for f in i.get("fields", []):
            span = ((1 << f["width"]) - 1) << f["start"]
            if not covered & span:
                continue
            nfree = bin(span & ~covered).count("1")
            lab = val["instructions"].get(i["mnemonic"], {}).get(f["name"], {}).get("label")
            rows.append({"mnemonic": i["mnemonic"], "field": f["name"],
                         "width": f["width"], "free_bits": nfree,
                         "legal_values": 1 << nfree, "label": lab,
                         "instruction_emittable": i["mnemonic"] in emittable,
                         "emitter_grade_label": lab in EMIT})
    zero = [r for r in rows if r["free_bits"] == 0]
    vac = [r for r in zero if r["emitter_grade_label"]]
    print("fields overlapping their own descriptor match: %d" % len(rows))
    print("  of those, ZERO free bits (one legal value -- not a field): %d" % len(zero))
    print("  of those, carrying an EMITTER-GRADE label (vacuous claim): %d" % len(vac))
    print()
    print("%-34s %3s %5s %6s  %-20s %s" % ("instr.field", "w", "free", "legal", "label", "instr emittable"))
    for r in sorted(rows, key=lambda r: (r["free_bits"], r["mnemonic"], r["field"])):
        print("  %-34s %3d %5d %6d  %-20s %s" % (
            r["mnemonic"] + "." + r["field"], r["width"], r["free_bits"],
            r["legal_values"], r["label"], "yes" if r["instruction_emittable"] else ""))
    out = os.path.join(D, "match_overlap.json")
    json.dump({"_meta": {"defect": "DEF-0170-1",
                         "total": len(rows), "zero_free_bits": len(zero),
                         "vacuous_emitter_grade": len(vac)},
               "rows": rows}, open(out, "w"), indent=1)
    print("\nwrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
