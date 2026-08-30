#!/usr/bin/env python3
"""EXP-0173: what do the headline numbers become if the zero-free-bit "fields"
are folded into `match`, where they belong?

A field whose whole span is pinned by its own descriptor's `match` has exactly
one legal value. There is nothing for an implementer to choose, so it is part of
the opcode, not a field. Counting it inflates BOTH the emitter-grade numerator
(when it carries an emitter-grade label) and the field denominator.

This recomputes both headlines four ways. It writes nothing: db.json and
validation.json are read-only here.

    python3 experiments/EXP-0173-closure-audit/analysis/vacuous_fields.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXP))
ISA = os.path.join(ROOT, "tools", "agx-isa")
EMIT = {"hardware-run", "isolated-byte-diff"}
DATA_WORD = "data-word"


def counts(db, val, fold_zero_free, fold_partial=False):
    """Recompute (emitter_grade, total_fields, emittable_instrs, emitter_relevant)."""
    eg = tot = 0
    emittable = []
    relevant = 0
    for i in db["instructions"]:
        m = i["mnemonic"]
        entry = val["instructions"].get(m, {})
        covered = 0
        for (s, w, _v) in i.get("match", []):
            covered |= ((1 << w) - 1) << s
        keep = []
        for f in i.get("fields", []):
            span = ((1 << f["width"]) - 1) << f["start"]
            free = bin(span & ~covered).count("1")
            if fold_zero_free and free == 0:
                continue                      # folded into match: not a field
            if fold_partial and free < f["width"]:
                continue                      # also fold partially-pinned ones
            keep.append(f)
        for f in keep:
            lab = entry.get(f["name"], {}).get("label")
            if lab is not None:
                tot += 1
                if lab in EMIT:
                    eg += 1
        if i.get("emitter_role") != DATA_WORD:
            relevant += 1
            labs = [entry.get(f["name"], {}).get("label") for f in keep]
            ok = bool(keep) and all(l in EMIT for l in labs)
            if "EMITTABLE VETO" in ((entry.get("_instruction") or {}).get("note", "") or ""):
                ok = False
            if ok:
                emittable.append(m)
    return eg, tot, sorted(emittable), relevant


def main():
    db = json.load(open(os.path.join(ISA, "db.json")))
    val = json.load(open(os.path.join(ISA, "validation.json")))

    a = counts(db, val, fold_zero_free=False)
    b = counts(db, val, fold_zero_free=True)
    c = counts(db, val, fold_zero_free=True, fold_partial=True)

    # which fields are affected
    zero, partial = [], []
    for i in db["instructions"]:
        covered = 0
        for (s, w, _v) in i.get("match", []):
            covered |= ((1 << w) - 1) << s
        for f in i.get("fields", []):
            span = ((1 << f["width"]) - 1) << f["start"]
            free = bin(span & ~covered).count("1")
            lab = val["instructions"].get(i["mnemonic"], {}).get(f["name"], {}).get("label")
            rec = {"mnemonic": i["mnemonic"], "field": f["name"], "width": f["width"],
                   "free_bits": free, "label": lab, "emitter_grade": lab in EMIT,
                   "instruction_emittable_now": i["mnemonic"] in a[2]}
            if free == 0:
                zero.append(rec)
            elif free < f["width"]:
                partial.append(rec)

    out = {"_meta": {
        "experiment": "EXP-0173",
        "question": "should the 25 zero-free-bit fields be folded into `match`?",
        "AS_PUBLISHED": {"emitter_grade": a[0], "total_fields": a[1],
                         "emittable_instructions": len(a[2]),
                         "emitter_relevant_instructions": a[3],
                         "headline": "%d / %d fields; %d of %d instructions"
                                     % (a[0], a[1], len(a[2]), a[3])},
        "FOLD_ZERO_FREE_BIT_FIELDS": {"emitter_grade": b[0], "total_fields": b[1],
                                      "emittable_instructions": len(b[2]),
                                      "emitter_relevant_instructions": b[3],
                                      "headline": "%d / %d fields; %d of %d instructions"
                                                  % (b[0], b[1], len(b[2]), b[3]),
                                      "delta_emitter_grade": b[0] - a[0],
                                      "delta_total_fields": b[1] - a[1],
                                      "delta_emittable": len(b[2]) - len(a[2]),
                                      "newly_emittable": sorted(set(b[2]) - set(a[2])),
                                      "no_longer_emittable": sorted(set(a[2]) - set(b[2]))},
        "ALSO_FOLD_PARTIALLY_PINNED": {"emitter_grade": c[0], "total_fields": c[1],
                                       "emittable_instructions": len(c[2]),
                                       "emitter_relevant_instructions": c[3],
                                       "headline": "%d / %d fields; %d of %d instructions"
                                                   % (c[0], c[1], len(c[2]), c[3]),
                                       "caution": "NOT recommended: a partially pinned field "
                                                  "still has a real choice, just a narrower one. "
                                                  "The fix there is to correct start/width, not "
                                                  "to delete the field."},
        "zero_free_bit_fields": len(zero),
        "zero_free_bit_fields_carrying_emitter_grade": sum(1 for z in zero if z["emitter_grade"]),
        "zero_free_bit_fields_inside_currently_emittable_instructions":
            sum(1 for z in zero if z["instruction_emittable_now"]),
        "partially_pinned_fields": len(partial),
    }, "zero_free_bit_fields": zero, "partially_pinned_fields": partial}
    p = os.path.join(HERE, "vacuous_fields.json")
    json.dump(out, open(p, "w"), indent=1)
    print(json.dumps(out["_meta"], indent=1))
    print("\nZERO-FREE-BIT FIELDS INSIDE CURRENTLY-EMITTABLE INSTRUCTIONS:")
    for z in zero:
        if z["instruction_emittable_now"]:
            print("  %-34s w=%-2d label=%s" % (z["mnemonic"] + "." + z["field"],
                                               z["width"], z["label"]))
    print("\nwrote", p)


if __name__ == "__main__":
    sys.exit(main())
