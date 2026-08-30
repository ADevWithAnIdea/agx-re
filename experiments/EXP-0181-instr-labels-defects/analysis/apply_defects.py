#!/usr/bin/env python3
"""EXP-0181 Task 2 -- apply the three narrowings that survived re-derivation.

ONE coherent write to tools/agx-isa/db.json.  Every field it touches has its
PRE-STATE asserted first, so re-running against an already-patched tree fails
loudly instead of double-applying.

Applied (see analysis/defects_rederived.json for the re-derivation):
  D1  iter_at.grp        bits 0..7  -> bit 7 only          (match pins 0..6 = 0x2f)
  D3  reg_move_cb.form   bits 16..23 -> bits 20..23        (match pins 16..19 = 0xb)
  D4  shift_amt_move.kind bits 16..23 -> bits 20..23       (match pins 16..19 = 0xc)
                          enum re-based {0x1c,0x3c} -> {1,3}

NOT applied, deliberately:
  D2  pixel_order.scope -- its free bits (24..27, 29, 31) are NOT CONTIGUOUS, and the
      committed evidence contradicts the match that would define the split.  Semantics
      note only.  See RESULTS.md section 3.2.

The pinned remainder of each narrowed field is preserved in the descriptor's
`match_notes` block, the convention EXP-0175 established for the 25 zero-free-bit
folds, with a `note` distinguishing a PARTIAL narrowing from a full fold.

Usage:  python3 analysis/apply_defects.py [--dry-run]
CLEAN-ROOM: edits our own machine-readable ISA database from our own measurements.
"""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DBP = os.path.join(ROOT, "tools", "agx-isa", "db.json")

PRE_SHA = "a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22"


def get(db, m):
    for i in db["instructions"]:
        if i["mnemonic"] == m:
            return i
    raise KeyError(m)


def fld(ins, n):
    for f in ins["fields"]:
        if f["name"] == n:
            return f
    raise KeyError("%s.%s" % (ins["mnemonic"], n))


def note(ins, entry):
    ins.setdefault("match_notes", []).append(entry)


def main():
    dry = "--dry-run" in sys.argv
    raw = open(DBP, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != PRE_SHA:
        print("WARNING: db.json sha %s != the pre-state this script was written against\n"
              "         (%s). Pre-state field assertions still gate every edit." % (sha, PRE_SHA),
              file=sys.stderr)
    db = json.loads(raw.decode("utf-8"))

    # ---- D1  iter_at.grp -------------------------------------------------
    ins = get(db, "iter_at")
    f = fld(ins, "grp")
    assert (f["start"], f["width"], f["type"]) == (0, 8, "raw"), f
    assert ins["match"][0] == [0, 7, 47], ins["match"]
    f["start"], f["width"] = 7, 1
    note(ins, {"name": "grp", "start": 0, "width": 7, "type": "raw", "value": 47,
               "note": "PARTIAL NARROWING (EXP-0181, DEF-0168-A). The former `grp` declared "
                       "bits 0..7 while this descriptor's own match pins bits 0..6 to 0x2f, "
                       "so 254 of its 256 values encoded a DIFFERENT instruction and "
                       "assemble() refused all but two of them. Only bit 7 is free; `grp` "
                       "now declares that bit alone. This entry is the pinned remainder."})
    ins["semantics"] += (
        "  FIELD NARROWED (EXP-0181, from EXP-0168 section 7): `grp` declared bits 0..7 over a match "
        "that pins bits 0..6 to 0x2f, so byte0 has exactly TWO legal values, 0x2f and 0xaf, "
        "and every other value is a decode desync -- which is why three experiments hit hangs "
        "sweeping it and why EXP-0168's arm was stopped after 4 of 256 values. `grp` is now the "
        "single free bit 7. MEASURED, G17P, EXP-0168 rclean07/08/09 (three gated runs, identical "
        "in all three): grp=1 (byte0 0xaf) is `ok` on both the centroid carrier r_i8 and the "
        "4-sample carrier r_i8s; grp=0 (byte0 0x2f) is `wrong_value` on r_i8 and `ok` on r_i8s. "
        "So bit 7 changes the observation at 1 sample and not at 4. The two out-of-descriptor "
        "values dispatched (0x00, 0x01) HUNG the device on both carriers, in all three runs.")

    # ---- D3  reg_move_cb.form -------------------------------------------
    ins = get(db, "reg_move_cb")
    f = fld(ins, "form")
    assert (f["start"], f["width"], f["type"]) == (16, 8, "raw"), f
    assert [16, 4, 11] in ins["match"], ins["match"]
    f["start"], f["width"] = 20, 4
    note(ins, {"name": "form", "start": 16, "width": 4, "type": "raw", "value": 11,
               "note": "PARTIAL NARROWING (EXP-0181, DEF-0168-C). The former `form` declared "
                       "the whole of byte+2 while the match pins its LOW NIBBLE to 0xb, so only "
                       "16 of its 256 values were legal. `form` is now the free high nibble; the "
                       "encoded byte is (form << 4) | 0x0b. This entry is the pinned remainder."})
    ins["semantics"] += (
        "  FIELD NARROWED (EXP-0181, from EXP-0168 section 7): `form` declared bits 16..23 over a "
        "match pinning bits 16..19 to 0xb; it is now the free high nibble (bits 20..23), and the "
        "byte an emitter writes is (form << 4) | 0x0b. RE-SCORED against EXP-0169's dense G17P "
        "sweep restricted to the 16 legal bytes (2 carriers C1_alu / C3_uni x 2 gated runs, "
        "identical in all four): form 0..3 (bytes 0x0b/0x1b/0x2b/0x3b) are `ok`; form 4..15 are "
        "`wrong_value`. So the narrowed field is DENSELY covered, 16 of 16, and its accepted set "
        "is exactly the four low forms. The corpus only ever emits form 1, 2 and 3 "
        "(0x1b x7, 0x2b x10, 0x3b x14 over 31 firings).")

    # ---- D4  shift_amt_move.kind ----------------------------------------
    ins = get(db, "shift_amt_move")
    f = fld(ins, "kind")
    assert (f["start"], f["width"], f["type"]) == (16, 8, "enum"), f
    assert f.get("enum") == {"28": "shift_amt", "60": "rotate_amt"}, f.get("enum")
    assert [16, 4, 12] in ins["match"], ins["match"]
    f["start"], f["width"] = 20, 4
    f["enum"] = {"1": "shift_amt (byte+2 = 0x1c)", "3": "rotate_amt (byte+2 = 0x3c)"}
    note(ins, {"name": "kind", "start": 16, "width": 4, "type": "enum", "value": 12,
               "note": "PARTIAL NARROWING (EXP-0181, DEF-0168-D). The former `kind` declared "
                       "the whole of byte+2 while the match pins its LOW NIBBLE to 0xc, so only "
                       "16 of its 256 values were legal and the enum keys 28/60 were whole-byte "
                       "values. `kind` is now the free high nibble; the encoded byte is "
                       "(kind << 4) | 0x0c, and the enum keys are re-based accordingly. "
                       "This entry is the pinned remainder."})
    ins["semantics"] += (
        "  FIELD NARROWED (EXP-0181, from EXP-0168 section 7): `kind` declared bits 16..23 over a "
        "match pinning bits 16..19 to 0xc; it is now the free high nibble (bits 20..23), and the "
        "byte an emitter writes is (kind << 4) | 0x0c. The enum keys are re-based from the "
        "whole-byte 0x1c/0x3c to 1/3. RE-SCORED against the dense sweeps restricted to the 16 "
        "legal bytes: G17P (EXP-0154, k_rot_var, 2 gated runs, identical) `ok` at kind 1 and 3, "
        "`wrong_value` at every even kind, `silent_zero` at every other odd kind; M4 (EXP-0146 "
        "run01/run02, identical) `ok` at kind 0,1,2,3 and `silent_zero` at kind 4..15. So the "
        "narrowed field is DENSELY covered 16 of 16 on BOTH targets, and G17P accepts a strict "
        "SUBSET of what M4 accepts. Recorded, not smoothed: on the same G17P carrier the "
        "hardware also accepts byte+2 = 0x14 and 0x34 -- low nibble 4, OUTSIDE this descriptor's "
        "match -- so the 0xc pin describes this descriptor, not the hardware's full accept set.")

    # ---- D2  pixel_order.scope: reported, NOT narrowed -------------------
    ins = get(db, "pixel_order")
    f = fld(ins, "scope")
    assert (f["start"], f["width"], f["type"]) == (24, 8, "mod"), f
    ins["semantics"] += (
        "  DEF-0181-1 -- `scope` CANNOT BE NARROWED, and the reason is a second defect "
        "(EXP-0181, re-derived from EXP-0147's committed raw). This descriptor's match pins "
        "instruction bits 28 and 30 (byte+3 bits 4 and 6), which lie INSIDE the 8-bit `scope` "
        "field, so `scope` declares 8 bits of which only 6 are choosable and assemble() refuses "
        "192 of its 256 values. The free bits are 24..27, 29 and 31 -- NOT CONTIGUOUS -- so no "
        "single (start,width) field can express them, and truncating `scope` to the contiguous "
        "run 24..27 would make bit 31 unencodable, which is precisely the acquire-vs-release "
        "distinction (0x50 vs 0xd0) this descriptor documents. Splitting `scope` into three "
        "fields WOULD express them, but the match those boundaries would be drawn around is "
        "itself contradicted by the committed measurement: EXP-0147's dense M4 sweep (256 values "
        "x 2 gated runs, both carriers) accepts byte+3 iff bit4==1 AND (bit6 XOR bit7)==1 in the "
        "ACQUIRE member and iff bit4==1 AND bit7==1 in the RELEASE member. Neither accept set is "
        "contained in the match's legal set {high nibble 5,7,d,f}: each carrier accepts 32 values "
        "the match REJECTS (high nibbles 9 and b) and rejects 32 the match ADMITS. The bit-30 pin "
        "comes from EXP-0162 on G17P and the refuting sweep from EXP-0147 on M4, so this may be a "
        "target difference or a carrier difference; it is NOT resolved here and no boundary is "
        "moved on the strength of it. Consequence for a label auditor: `scope`'s recorded range "
        "\"full 8-bit range, dense (256 cases)\" overstates the field by 4x -- only 64 of those "
        "256 values are legal under this descriptor.")

    # json.dumps(indent=1) with NO trailing newline reproduces the repository's
    # db.json byte-for-byte (verified against the pre-image before writing).
    out = json.dumps(db, indent=1)
    if dry:
        print("dry run: %d bytes, sha %s" % (len(out), hashlib.sha256(out.encode()).hexdigest()))
        return 0
    open(DBP, "w", encoding="utf-8").write(out)
    print("wrote %s\n  pre  sha %s\n  post sha %s"
          % (DBP, sha, hashlib.sha256(out.encode()).hexdigest()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
