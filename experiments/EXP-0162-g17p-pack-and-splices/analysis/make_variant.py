#!/usr/bin/env python3
"""EXP-0162 -- build a VARIANT COPY of tools/agx-isa/ with one proposed change
applied, so a match/length change can be A/B'd without ever touching the live
tree. Same shape as work/dbtriage/make_c_variant.py and EXP-0148's
analysis/make_variant.py, so the numbers are directly comparable.

  python3 analysis/make_variant.py <name>       (--list to enumerate)

CLEAN-ROOM: operates only on our own db.json and our own compiled-shader corpus.
"""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
LIVE = os.path.join(REPO, "tools", "agx-isa")
OUT = os.path.join(EXP, "work", "cvar")


def desc(db, m):
    for i in db["instructions"]:
        if i["mnemonic"] == m:
            return i
    raise KeyError(m)


# ---------------------------------------------------------------- variants
def v_pixel_order(d):
    """P1: `pixel_order` -- drop the byte+4 match pin (which contradicts the
    declared `flags` field AND, per EXP-0162 run04, is not even the whole legal
    set: 112 acquire / 224 release byte+4 values are pixel-exact on G17P), and
    replace it with the byte+3 bits the HARDWARE requires of BOTH members:
    bit4 == 1 and bit6 == 1.

    Evidence (EXP-0162 run04, G17P, dense 0..255, detection-power control passed):
      acquire byte+3 legal = bit4 & (bit6 ^ bit7)   64/256
      release byte+3 legal = bit4 & bit7            64/256
      union                = bit4 & (bit6 | bit7)   -- INEXPRESSIBLE in the
      (start,width,value) match language, so the expressible SUBSET
      bit4 & bit6 is used: it contains the compiler's own 0x50/0xd0 and the
      texture-barrier pair's 0x51/0xd1, and NO corpus byte+3 value.
    """
    p = desc(d, "pixel_order")
    p["match"] = [[0, 8, 7], [16, 8, 84], [28, 1, 1], [30, 1, 1]]
    return d


def v_vary_store(d):
    """P2: split the byte0==0x57 group. All 615 corpus vertex-stage stores have
    byte+1 bit1 SET; all 10 fragment-stage ops have it CLEAR (EXP-0162 desk scan).
    HW (EXP-0162 run04/run05, G17P): SETTING bit1 on the fragment op kills the
    fragment; clearing an unrelated bit (0x14 -> 0x1c) is null, exactly as
    EXP-0091 measured on M4.

    vary_store gains `[9,1,1]`; a new 6-byte `frag_sample_submit` takes `[9,1,0]`.
    The LENGTH RULE change lives in isadb.py and is applied by _patch_length().
    """
    p = desc(d, "vary_store")
    p["match"] = [[0, 8, 87], [9, 1, 1]]
    p.pop("emit_unsafe", None)
    p["semantics"] = p["semantics"] + (
        "  [LENGTH + MATCH SPLIT PROPOSED, EXP-0162, G17P] byte+1 bit1 selects the "
        "FORM: set = this 8-byte vertex-stage varying store; clear = the 6-byte "
        "fragment sample-mask submission op (`frag_sample_submit`). Discriminator "
        "derived from 625/625 corpus tokens and confirmed on hardware.")
    new = {
        "mnemonic": "frag_sample_submit",
        "length": 6,
        "match": [[0, 8, 87], [9, 1, 0]],
        "fields": [
            {"name": "kind", "start": 8, "width": 8, "type": "mod"},
            {"name": "amode", "start": 16, "width": 8, "type": "mod"},
            {"name": "b3", "start": 24, "width": 8, "type": "mod"},
            {"name": "src_sel", "start": 32, "width": 8, "type": "reg"},
            {"name": "tag", "start": 40, "width": 8, "type": "imm"},
        ],
        "semantics": (
            "FRAGMENT sample-mask / kill submission op (EXP-0091 located it; "
            "EXP-0162 separated it from vary_store). 6 bytes: 57 <kind> <amode> "
            "<b3> <src_sel> <tag>. Submits the fragment's [[sample_mask]] (or the "
            "discard_fragment() kill) for colour, depth and occlusion together. "
            "src_sel (byte+4) bits[4:0] select the register holding the computed "
            "mask; 0x00 is the register the compiler routes it into and any other "
            "tested value reads a register that behaves as always-zero, i.e. kills "
            "the fragment. Effective mask width is exactly rasterSampleCount bits."),
        "provenance": (
            "HW-VALIDATED (EXP-0162, G17P, render splice, detection-power control "
            "passed: byte+4 0x00 -> 0x01 turns the surviving pixel (0.75,0.5,0.25,1) "
            "into the clear colour, and the unspliced mask=0 control does the same). "
            "Separated from vary_store by byte+1 bit1: 615/615 corpus vertex stores "
            "set it, 10/10 corpus fragment ops clear it, and SETTING it on the "
            "fragment op kills the fragment on hardware. Earlier location and the "
            "MSAA mask-width contract: EXP-0091 (M4)."),
    }
    d["instructions"].append(new)
    return d


def v_both(d):
    return v_vary_store(v_pixel_order(d))


VARIANTS = {"pixel_order": v_pixel_order, "vary_store": v_vary_store, "both": v_both}

LENGTH_OLD = """    if b0 == 0x57:
        return 8                       # vary_store (EXP-0037 HW)"""
LENGTH_NEW = """    if b0 == 0x57:
        # EXP-0162 (G17P): byte+1 bit1 selects the FORM, and therefore the length.
        # Set = the 8-byte VERTEX varying store (615/615 corpus tokens, all vertex
        # stage, all with byte+5 in {0x40,0x41}). Clear = the 6-byte FRAGMENT
        # sample-mask submission op (10/10 corpus tokens, all fragment stage, all
        # with byte+5 == 0x01), whose bytes +6..+7 are the LEADER OF THE NEXT
        # INSTRUCTION -- the over-consumption EXP-0091 reported.
        # byte+2 does NOT discriminate: 0x54/0x55/0x56 occur in BOTH populations.
        return 8 if (_b1 & 0x02) else 6"""


def _patch_length(dst, apply_it):
    p = os.path.join(dst, "isadb.py")
    s = open(p).read()
    if not apply_it:
        return
    assert LENGTH_OLD in s, "length rule anchor not found"
    open(p, "w").write(s.replace(LENGTH_OLD, LENGTH_NEW))


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        print("\n".join(sorted(VARIANTS)))
        return
    name = sys.argv[1]
    dst = os.path.join(OUT, name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(LIVE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    dbp = os.path.join(dst, "db.json")
    db = json.load(open(dbp))
    db = VARIANTS[name](db)
    json.dump(db, open(dbp, "w"), indent=1)
    _patch_length(dst, name in ("vary_store", "both"))
    print("built", dst)


main()
