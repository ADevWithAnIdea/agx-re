#!/usr/bin/env python3
"""DB-defect triage -- build a VARIANT copy of the ISA tool tree with ONE class-(c)
change applied, so a match/length change can be A/B'd without ever touching the live
tools/agx-isa/ tree.  Mirrors EXP-0148/analysis/make_variant.py.

Usage:  python3 work/dbtriage/make_c_variant.py <variant-name>
        python3 work/dbtriage/make_c_variant.py --list

Metrics are then produced by work/dbtriage/ab_run.sh <variant-name>, which reports the
two numbers EXP-0148 gated on: CLEAN FILES and STRICT LEFTOVER BYTES over the 1080-file
own-MSL corpus (its baseline move was 803 -> 832 files and 395,390 -> 389,368 bytes; the
live tree today reproduces 832 / 389,368).

CLEAN-ROOM: operates only on our own db.json and our own compiled-shader corpus.
"""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
LIVE = os.path.join(REPO, "tools", "agx-isa")
OUT = os.path.join(HERE, "cvar")


def desc(db, m):
    for i in db["instructions"]:
        if i["mnemonic"] == m:
            return i
    raise KeyError(m)


# ---------------------------------------------------------------- db patches --
def c1_pixel_order(db, isasrc):
    """EXP-0147: `flags` is declared at bits[32:40] AND pinned to 0x06 by the match.
    Drop the match constant; keep the field."""
    d = desc(db, "pixel_order")
    d["match"] = [t for t in d["match"] if t[0] != 32]
    return db, isasrc


def c2_carry_gen(db, isasrc):
    """EXP-0146: byte+2's real rule is (v & 0xCD) == 0x05, not the whole byte == 0x35.
    Bits 1, 4 and 5 are DON'T-CARE (8 of 256 values work)."""
    d = desc(db, "carry_gen")
    d["match"] = [t for t in d["match"] if t[0] != 16] + \
                 [[16, 1, 1], [18, 1, 1], [19, 1, 0], [22, 1, 0], [23, 1, 0]]
    d["fields"] = d["fields"] + [
        {"name": "b2_free1", "start": 17, "width": 1, "type": "mod"},
        {"name": "b2_free45", "start": 20, "width": 2, "type": "mod"},
    ]
    return db, isasrc


def c3_cvt_bf16(db, isasrc):
    """EXP-0144: the match pins byte+4 == 0x01, but our own compiler emits byte+4 == 0x05
    for float->bfloat, so the descriptor fails to decode its own compiler's output."""
    d = desc(db, "cvt_bf16")
    d["match"] = [t for t in d["match"] if t[0] != 32]
    return db, isasrc


def c7_sfu_marker(db, isasrc):
    """EXP-0146: both bytes are load-bearing but only (b0 & 0xF7)==0x06 and
    (b1 & 0x13)==0x02 are required. The current match pins both bytes whole, so the
    descriptor has ZERO fields and cannot express the free bits."""
    d = desc(db, "sfu_marker")
    d["match"] = [[0, 1, 0], [1, 1, 1], [2, 1, 1], [4, 4, 0],
                  [8, 1, 0], [9, 1, 1], [12, 1, 0]]
    d["fields"] = [
        {"name": "b0_bit3", "start": 3, "width": 1, "type": "mod"},
        {"name": "b1_bits23", "start": 10, "width": 2, "type": "mod"},
        {"name": "b1_bits567", "start": 13, "width": 3, "type": "mod"},
    ]
    return db, isasrc


def c8_reg_move(db, isasrc):
    """EXP-0140: reg_move_c0/c1/c2var/c9/cb are ONE 4-byte instruction whose byte+2 is a
    form selector. Collapse the five into one descriptor with byte+2 as a field.
    uniform_mov is left alone (it additionally pins byte+3)."""
    keep = {"reg_move_c0", "reg_move_c1", "reg_move_c2var", "reg_move_c9", "reg_move_cb"}
    db["instructions"] = [i for i in db["instructions"] if i["mnemonic"] not in keep] + [{
        "mnemonic": "reg_move",
        "length": 4,
        "match": [[0, 4, 11]],
        "fields": [
            {"name": "dst", "start": 4, "width": 4, "type": "reg"},
            {"name": "src_reg", "start": 8, "width": 7, "type": "reg"},
            {"name": "src_flag", "start": 15, "width": 1, "type": "mod",
             "enum": {"0": "gpr/immediate", "1": "uniform file"}},
            {"name": "form", "start": 16, "width": 8, "type": "mod"},
            {"name": "op_desc", "start": 24, "width": 8, "type": "mod"},
        ],
        "semantics": "PROPOSAL (EXP-0140, not applied): one 4-byte register move whose "
                     "byte+2 (`form`) is a form selector. Only form in "
                     "{0x01,0x05,0x11,0x15,0x21,0x25,0x31,0x35} actually moves a value.",
        "provenance": "PROPOSAL -- HW byte+2 sweep 0..255 in one carrier (EXP-0140)",
    }]
    return db, isasrc


# ------------------------------------------------------------ isadb patches --
ANCHOR_MOVIMM = None  # discovered at build time; see c9


def c9_mov_imm12(db, isasrc):
    """EXP-0140: the 2-byte mov_imm with imm7 == 12 does not tokenize -- byte+1 = 0x0C
    makes the pair look like the 4-byte low-nibble-0xC preamble group. Try letting the
    low-nibble-0xC 4-byte rule lose to a preceding low-nibble-0xC mov_imm leader."""
    old = "    if (b0 & 0x0f) == 0x0c:"
    if isasrc.count(old) != 1:
        raise SystemExit("c9: anchor %r not unique (%d)" % (old, isasrc.count(old)))
    new = ("    if (b0 & 0x0f) == 0x0c and not (off + 1 < len(buf) and buf[off + 1] == 0x0c\n"
           "                                   and (b0 & 0xf0) != 0x00):\n"
           "        # TRIAGE C9 candidate (EXP-0140): a mov_imm pair `?c 0c` (imm7 == 12)\n"
           "        # is otherwise swallowed by the 4-byte preamble rule.\n"
           "        pass\n"
           "    if (b0 & 0x0f) == 0x0c:")
    return db, isasrc.replace(old, new, 1)



def c1b_pixel_order(db, isasrc):
    """C1 REFINED. Dropping [32,8,6] alone REGRESSES: pixel_order's match then equals
    threadgroup_barrier's ([0,8,7]+[16,8,84]) and loses the specificity tie-break, so even
    the compiler's own `07 14 54 50 06 00` decodes as threadgroup_barrier. Replace the
    byte+4 pin with a byte+1 discriminator instead: `kind` is 0x14 (acquire) or 0x04
    (release), i.e. bits {0,1,3,5,6,7} clear and bit2 set, with bit4 the acquire/release
    selector. That makes pixel_order MORE specific than threadgroup_barrier (23 match bits
    vs 16) while leaving byte+4 free, and mem_fence (24 bits) still out-specifies it."""
    d = desc(db, "pixel_order")
    d["match"] = [t for t in d["match"] if t[0] != 32] + \
                 [[8, 2, 0], [10, 1, 1], [11, 1, 0], [13, 3, 0]]
    d["fields"] = [f for f in d["fields"] if f["name"] != "kind"] + [
        {"name": "kind", "start": 12, "width": 1, "type": "enum",
         "enum": {"1": "acquire/wait (byte+1 0x14)", "0": "release/signal (byte+1 0x04)"}},
    ]
    return db, isasrc


def c7b_sfu_marker(db, isasrc):
    """C7 REFINED. The free bits of sfu_marker's byte+1 are gated by the LENGTH RULE
    (`b0 == 0x06 and b1 == 0x02 -> 2`), not by the match, so relaxing the descriptor alone
    cannot reach them. Relax the length rule to (b1 & 0x13) == 0x02 -- AFTER the rtq_pred
    test, which must keep winning (0xc2 & 0x13 == 0x02 would otherwise swallow it) -- and
    relax the match to match. byte0's free bit3 is NOT relaxed: byte0 0x0e is the
    stop/end group's own length key, so the HW-legal `0e 02` is UNREACHABLE for our
    tokenizer without resolving that collision. Recorded, not fixed."""
    d = desc(db, "sfu_marker")
    d["match"] = [[0, 8, 6], [8, 1, 0], [9, 1, 1], [12, 1, 0]]
    d["fields"] = [
        {"name": "b1_bits23", "start": 10, "width": 2, "type": "mod"},
        {"name": "b1_bits567", "start": 13, "width": 3, "type": "mod"},
    ]
    old = "    if b0 == 0x06 and _b1 == 0x02:                          return 2   # 06 02"
    if isasrc.count(old) != 1:
        raise SystemExit("c7b: length anchor not unique (%d)" % isasrc.count(old))
    new = ("    if b0 == 0x06 and (_b1 & 0x13) == 0x02:               return 2   # 06 02\n"
           "                                       # TRIAGE C7b (EXP-0146): byte+1 bits 2,3,5,6,7\n"
           "                                       # are DON'T-CARE on hardware (32 of 256 values\n"
           "                                       # run correctly). Must stay BELOW the rtq_pred\n"
           "                                       # test above: 0xc2 & 0x13 == 0x02.")
    return db, isasrc.replace(old, new, 1)

VARIANTS = {
    "c1_pixel_order": c1_pixel_order,
    "c1b_pixel_order": c1b_pixel_order,
    "c2_carry_gen": c2_carry_gen,
    "c3_cvt_bf16": c3_cvt_bf16,
    "c7_sfu_marker": c7_sfu_marker,
    "c7b_sfu_marker": c7b_sfu_marker,
    "c8_reg_move": c8_reg_move,
    "baseline": lambda db, s: (db, s),
}


def main():
    if "--list" in sys.argv:
        print("\n".join(sorted(VARIANTS)))
        return
    name = sys.argv[1]
    fn = VARIANTS[name]
    dst = os.path.join(OUT, name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for f in ("isadb.py", "db.json", "roundtrip_test.py", "agxisa.py"):
        shutil.copy(os.path.join(LIVE, f), dst)
    db = json.load(open(os.path.join(dst, "db.json")))
    src = open(os.path.join(dst, "isadb.py")).read()
    db, src = fn(db, src)
    open(os.path.join(dst, "db.json"), "w").write(json.dumps(db, indent=2))
    open(os.path.join(dst, "isadb.py"), "w").write(src)
    print("built", dst)


if __name__ == "__main__":
    main()
