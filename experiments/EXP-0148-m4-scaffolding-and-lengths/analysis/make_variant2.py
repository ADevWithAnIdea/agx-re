#!/usr/bin/env python3
"""EXP-0148 -- variant builder that can also add DESCRIPTORS to the db.json copy.

Two of the pre-registered length rules (H2, H4) failed their first A/B not because
the length was wrong but because `decode_one` requires a descriptor whose declared
`length` equals the computed length; the new lengths had no matching descriptor and
the token became undecodable. This builder adds the missing descriptors to the
variant's db.json copy so the length hypothesis can actually be tested.

Usage: python3 make_variant2.py <variant-name>
"""
import json, os, shutil, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "..", "work", "isa_copy")
spec = importlib.util.spec_from_file_location("mv", os.path.join(HERE, "make_variant.py"))
mv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mv)

HALF_COMPACT4 = {
    "mnemonic": "half_compact4",
    "length": 4,
    "match": [[0, 8, 16]],
    "fields": [
        {"name": "dst", "start": 8, "width": 8, "type": "reg"},
        {"name": "opsel", "start": 16, "width": 3, "type": "mod"},
        {"name": "opmode", "start": 19, "width": 5, "type": "mod"},
        {"name": "operand", "start": 24, "width": 8, "type": "reg"},
    ],
    "semantics": "EXP-0148 PROPOSED. 4-byte COMPACT native-half (fp16) float ALU: the byte0==0x10 "
                 "sibling of the low-nibble-9 falu_compact4/falu_acc. Selected by op-select "
                 "(byte+2 bits[2:0]) in {0,1}. Same field layout as half_alu with the 6-byte form's "
                 "srcB/src_modifier tail absent.",
    "provenance": "EXP-0148 (corpus tokenization, own-MSL): required so byte0==0x10 opsel-{0,1} "
                  "tokens have a length-4 descriptor to decode into. STRUCTURAL.",
}

B_ALU10_LO6 = {
    "mnemonic": "b_alu10_lo6",
    "length": 10,
    "match": [[0, 4, 11], [16, 4, 6]],
    "fields": [
        {"name": "dst", "start": 4, "width": 4, "type": "reg"},
        {"name": "src_reg", "start": 8, "width": 7, "type": "reg"},
        {"name": "src_flag", "start": 15, "width": 1, "type": "mod"},
        {"name": "opsel_hi", "start": 20, "width": 4, "type": "mod"},
        {"name": "srcA", "start": 24, "width": 8, "type": "reg"},
        {"name": "modA", "start": 32, "width": 8, "type": "mod"},
        {"name": "modB", "start": 40, "width": 8, "type": "mod"},
        {"name": "z6", "start": 48, "width": 8, "type": "imm"},
        {"name": "outmod", "start": 56, "width": 8, "type": "mod"},
        {"name": "ext8", "start": 64, "width": 8, "type": "imm"},
        {"name": "ext9", "start": 72, "width": 8, "type": "imm"},
    ],
    "semantics": "EXP-0148 PROPOSED. The byte+2-low-nibble-6 member of the 0x?b 10-byte "
                 "modifier/logic/convert ALU class, same layout as the b_alu10_lo7/loe/lof "
                 "siblings. Its existence is what makes the external compiler engineer's 10-byte "
                 "XOR example `4b 85 16 07 02 08 00 00 00 00` (byte+2 == 0x16) decodable; "
                 "EXP-0099 6.1 reported that example as decodable under NO family.",
    "provenance": "EXP-0148 (structural, from the class rule (byte+2 & 0x06) == 0x06). STRUCTURAL.",
}

DB_ADDS = {
    "h2_half_desc": [HALF_COMPACT4],
    "h4_nb10_desc": [B_ALU10_LO6],
    "final": [HALF_COMPACT4, B_ALU10_LO6],
}
PATCHES = {
    "h2_half_desc": [(mv.ANCHOR_HALF, mv.NEW_HALF)],
    "h4_nb10_desc": [(mv.ANCHOR_NB10, mv.NEW_NB10)],
    "final": [(mv.ANCHOR_LO9_COMPACT, mv.NEW_LO9_COMPACT), (mv.ANCHOR_HALF, mv.NEW_HALF),
              (mv.ANCHOR_2E, mv.NEW_2E), (mv.ANCHOR_NB10, mv.NEW_NB10)],
}


def main():
    name = sys.argv[1]
    dst = os.path.join(HERE, "..", "work", "variant_" + name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(BASE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    p = os.path.join(dst, "isadb.py")
    src = open(p).read()
    for old, new in PATCHES[name]:
        if src.count(old) != 1:
            raise SystemExit("ANCHOR NOT UNIQUE/FOUND (%d) %s" % (src.count(old), old[:100]))
        src = src.replace(old, new)
    open(p, "w").write(src)
    dbp = os.path.join(dst, "db.json")
    db = json.load(open(dbp))
    have = {d["mnemonic"] for d in db["instructions"]}
    for d in DB_ADDS[name]:
        if d["mnemonic"] not in have:
            db["instructions"].append(d)
    json.dump(db, open(dbp, "w"), indent=1)
    print("built", dst, "descriptors:", [d["mnemonic"] for d in DB_ADDS[name]])


if __name__ == "__main__":
    main()
