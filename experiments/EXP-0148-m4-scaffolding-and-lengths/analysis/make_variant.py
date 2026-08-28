#!/usr/bin/env python3
"""EXP-0148 -- build a variant copy of the ISA tool tree with ONE length-rule
change applied, so candidate rules can be A/B'd without ever touching the live
tools/agx-isa/ tree.

Usage: python3 make_variant.py <variant-name>

Each variant is an exact copy of work/isa_copy/ with a textual patch applied to
isadb.py's instr_length().  The patches are literal string replacements against
the frozen isadb.py so they are auditable and fail loudly if the source moves.
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "..", "work", "isa_copy")

# --- anchors in the frozen isadb.py -----------------------------------------
ANCHOR_LO9_COMPACT = """        b2 = buf[off + 2] if off + 2 < len(buf) else -1
        if b2 in (0x18, 0x38, 0x19, 0x21, 0x31, 0x30, 0x39):
            return 4                   # compact float accumulate/move (arith-enable bit clear)."""
NEW_LO9_COMPACT = """        b2 = buf[off + 2] if off + 2 < len(buf) else -1
        if b2 >= 0 and (b2 & 0x07) in (0x00, 0x01):
            return 4                   # EXP-0148 H1: OP-SELECT class rule. byte+2 bits[2:0] is the
                                       # float-ALU op-select; values {0,1} are the COMPACT 4-byte
                                       # accumulate/move class (superset of the enumerated
                                       # 0x18/0x19/0x21/0x30/0x31/0x38/0x39). Must be tested BEFORE
                                       # the 6+2*(byte+4&3) extension, because for a 4-byte op
                                       # byte+4 is the NEXT instruction's leader.
        if b2 in (0x18, 0x38, 0x19, 0x21, 0x31, 0x30, 0x39):
            return 4                   # compact float accumulate/move (arith-enable bit clear)."""

ANCHOR_HALF = """    if b0 == 0x10:
        if buf[off + 2] & 0x02:"""
NEW_HALF = """    if b0 == 0x10:
        if (buf[off + 2] & 0x07) in (0x00, 0x01):
            return 4                   # EXP-0148 H2: the fp16 sibling of the low-nibble-9 compact
                                       # 4-byte class (op-select byte+2 bits[2:0] in {0,1}).
        if buf[off + 2] & 0x02:"""

ANCHOR_2E = """            return 8 if (b4 & 0x02) else 6  # fused mul / mul-add coord op (EXP-0037)"""
NEW_2E = """            return 6 + 2 * (b4 & 0x03)  # EXP-0148 H1b: the 0x26/0x2e coord op-selects use the
                                        # SAME byte+4 low-2-bit extension as the rest of the group;
                                        # the old `8 if b4&2 else 6` needed two hand-patches above
                                        # (b4==0x82 -> 10, the 0x2e/0x87/0x23 -> 12) that this rule
                                        # reproduces (0x82&3=2 -> 10, 0x23&3=3 -> 12)."""

ANCHOR_NB10 = """        if b2 == 0x17 or (b2 & 0x0f) in (0x0e, 0x0f):
            return 10"""
NEW_NB10 = """        if b2 >= 0 and (b2 & 0x06) == 0x06 and b2 not in (0xd7, 0xe7) \\
                and not (b1 == 0x00 and b2 == 0x06):
            return 10                  # EXP-0148 H4: the 0x?b 10-byte modifier/logic/convert class
                                       # is (byte+2 & 0x06) == 0x06 -- low nibbles {6,7,e,f}. The old
                                       # dispatch enumerated {7,e,f} (+0x17) and left low nibble 6
                                       # undecodable, which is the external compiler engineer's
                                       # 10-byte XOR example `4b 85 16 07 02 08 00 00 00 00`
                                       # (EXP-0099 6.1). 0xd7/0xe7 stay excluded (device-store
                                       # leaders appearing as a mid-desync byte+2); the
                                       # tg_atomic_prep signature (b1==0x00 && b2==0x06) is left to
                                       # its own rule below.
        if b2 == 0x17 or (b2 & 0x0f) in (0x0e, 0x0f):
            return 10"""

ANCHOR_OP04_8 = """    if b0 == 0x04 and off + 1 < len(buf) and buf[off+1] != 0xea:
        return 8                       # op04_len8 (byte0==0x04 residue; see descriptor note)"""

VARIANTS = {
    "h1_lo9":      [(ANCHOR_LO9_COMPACT, NEW_LO9_COMPACT)],
    "h2_half":     [(ANCHOR_HALF, NEW_HALF)],
    "h1b_coord":   [(ANCHOR_2E, NEW_2E)],
    "h4_nb10":     [(ANCHOR_NB10, NEW_NB10)],
    "h5_op04_2":   [(ANCHOR_OP04_8,
                     "    if b0 == 0x04 and off + 1 < len(buf) and buf[off+1] != 0xea:\n"
                     "        return 2                       # EXP-0148 H5 candidate: 2 bytes\n")],
    "h5_op04_4":   [(ANCHOR_OP04_8,
                     "    if b0 == 0x04 and off + 1 < len(buf) and buf[off+1] != 0xea:\n"
                     "        return 4                       # EXP-0148 H5 candidate: 4 bytes\n")],
    "combined":    [(ANCHOR_LO9_COMPACT, NEW_LO9_COMPACT), (ANCHOR_HALF, NEW_HALF),
                    (ANCHOR_2E, NEW_2E), (ANCHOR_NB10, NEW_NB10)],
}


def main():
    name = sys.argv[1]
    patches = VARIANTS[name]
    dst = os.path.join(HERE, "..", "work", "variant_" + name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(BASE, dst, ignore=shutil.ignore_patterns("__pycache__"))
    p = os.path.join(dst, "isadb.py")
    src = open(p).read()
    for old, new in patches:
        if src.count(old) != 1:
            raise SystemExit("ANCHOR NOT UNIQUE/FOUND (%d hits) in %s:\n%s" % (src.count(old), name, old[:120]))
        src = src.replace(old, new)
    open(p, "w").write(src)
    print("built", dst)


if __name__ == "__main__":
    main()
