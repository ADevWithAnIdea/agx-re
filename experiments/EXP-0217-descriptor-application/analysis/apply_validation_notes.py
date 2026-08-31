#!/usr/bin/env python3
"""EXP-0217 -- amend the validation.json notes that EXP-0216's finding makes wrong,
and refresh the db_sha256 soft check.

NO `label` is changed. NO `evidence` list is changed. NO `range` is changed.
NO row is renamed, added or removed. Only `note` prose and the db-file hash.

Rule followed (dispatch, item 5): "Do not change any evidence label. If an edit
makes an existing note wrong, amend the note."

Usage: apply_validation_notes.py [--db PATH] [--labels PATH]
"""
import hashlib
import json
import sys

TAG = "**CORRECTED 2026-08-30 by EXP-0217 (from EXP-0216's re-analysis of this row's OWN raw)**"

SRC_C_LO = (
    " " + TAG + " -- THREE CLAUSES ABOVE ARE SUPERSEDED: `ROLE UNRESOLVED`, "
    "`either the packing here is reg<<2 or the second multiplicand is selected "
    "elsewhere`, and `Do not emit a register number here`. The role is "
    "RESOLVED and the packing IS reg = v >> 2. EXP-0216 re-decoded THIS row's "
    "own EXP-0154 records (512, byte+5 dense 0..255, G17P) against a host "
    "arithmetic oracle: with SEED_I = {r0:10, r1:21, r2:34, r3:47, ...}, "
    "byte+5 = 0..3 -> 101, 4..7 -> 211, 8..11 -> 341 (the anchor), 12..15 -> "
    "471 -- exactly SEED[value>>2] * 10 + 1, with the selected register "
    "released to zero on read. `dest = SEED[b5>>2] * SEED[b6>>3] + 1` scores "
    "64/64 in-domain here; BOTH addend models score 0/64. So byte+5 IS a "
    "MULTIPLICAND REGISTER SELECTOR and an emitter MAY put a register number "
    "here, packed reg << 2 (NOT (reg<<1)|size, and NOT byte+6's reg << 3). "
    "The NAME `srcC_lo` stays REFUTED and is retained only so this evidence "
    "row survives; WHICH multiplicand is A and which is B is UNDECIDABLE from "
    "this carrier (multiply commutes; no non-commutative probe), so no "
    "srcA/srcB assignment may be read into byte+5 vs byte+6. Label, range, "
    "target and evidence list are UNCHANGED -- the sweep that earned them is "
    "the same sweep."
)

SRC_B = (
    " " + TAG + " -- byte+6 is ONE OF TWO multiplicand selectors, not the only "
    "one: byte+5 is the other (reg = v >> 2; see this instruction's `srcC_lo` "
    "row). `imad` has NO field named `srcA`, so the `B` in this row's name is "
    "POSITIONAL AND ARBITRARY and carries no ordering claim -- A-vs-B is "
    "undecidable under a commutative multiply in EXP-0154's carrier. The "
    "clause `db.json modelled NO first multiplicand at all before this` remains "
    "true of the pre-2026-08-30 descriptor, but the first multiplicand was "
    "always byte+5, which EXP-0165's swap re-labelled rather than identified."
)


def main():
    dbp = "tools/agx-isa/db.json"
    vp = "tools/agx-isa/validation.json"
    if "--db" in sys.argv:
        dbp = sys.argv[sys.argv.index("--db") + 1]
    if "--labels" in sys.argv:
        vp = sys.argv[sys.argv.index("--labels") + 1]

    # Append-only guard: this script writes its target in place, so it must
    # never be pointed at a frozen raw/ copy. (EXP-0217 did exactly that once,
    # by a stray flag; the file was restored from git HEAD and this guard added.)
    if "/raw/" in vp.replace("\\", "/"):
        sys.exit("refusing to write into a raw/ tree: %s" % vp)

    v = json.load(open(vp))
    before = json.dumps(v, sort_keys=True)

    imad = v["instructions"]["imad"]
    for row, text in (("srcC_lo", SRC_C_LO), ("srcB", SRC_B)):
        assert text not in imad[row]["note"], "already applied: imad.%s" % row
        lab = imad[row]["label"]
        imad[row]["note"] = imad[row].get("note", "") + text
        assert imad[row]["label"] == lab

    v["db_sha256"] = hashlib.sha256(open(dbp, "rb").read()).hexdigest()

    assert json.dumps(v, sort_keys=True) != before
    with open(vp, "w") as fh:
        json.dump(v, fh, indent=1)
    print("amended imad.srcC_lo, imad.srcB; db_sha256 ->", v["db_sha256"][:12])


if __name__ == "__main__":
    main()
