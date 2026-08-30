#!/usr/bin/env python3
"""EXP-0203 frozen case matrix.

Every mutation uses `db.json`'s OWN `start`/`width` geometry for the field, and
`harness/selftest.py` asserts offline that each mutated encoding differs from its arm's
anchor **only inside that span** -- the aliasing trap (`match`-pinned bits an assembler
cannot clear making different values assemble to identical bytes) cannot occur here because
the instructions are built byte by byte, but it is asserted rather than assumed.

CLEAN-ROOM: our own field geometry over our own assembled bytes.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H          # noqa: E402
import oracle as O               # noqa: E402

DB = json.loads((H.ISA_DIR / "db.json").read_text())
INS = {i["mnemonic"]: i for i in DB["instructions"]}


# --------------------------------------------------------------------------
# Base instances.  Operands are drawn from r6..r9 ONLY -- the registers that are
# non-infrastructure in BOTH layouts -- so the operand values do not move between arms.
#   hA = 0x0D -> r6.hi     hB = 0x11 -> r8.hi     hC = 0x12 -> r9.lo
# byte+2 = 0x06 : opsel 6 (hfma), opflags 0.
# byte+4 = 0x13 : length selector 3 (12 bytes), negate-c, NO source release.  Established
#                 offline from EXP-0180's committed raw; EXP-0180's own 0x93 additionally
#                 ZEROES the half-lane named by byte+5, which would collide with a
#                 destination sweep.
# --------------------------------------------------------------------------
HA, HB, HC = 0x0D, 0x11, 0x12
FMA12_B2, FMA12_B4 = 0x06, 0x13
FMA12_TAIL = (0x00, 0x00, 0x00, 0x80, 0x01, 0x00)
HP_B2 = 0x18
DST_FIXED = 1                      # observable in layout HI and in layout LO

ARMS = [
    {"id": "F12_DST_A", "instr": "half_alu_fma12", "carrier": "A", "layout": "HI",
     "seeds": "A", "fields": ["dst"]},
    {"id": "F12_DST_B", "instr": "half_alu_fma12", "carrier": "B", "layout": "LO",
     "seeds": "B", "fields": ["dst"]},
    {"id": "F12_DST_C", "instr": "half_alu_fma12", "carrier": "A", "layout": "LO",
     "seeds": "B", "fields": ["dst"]},
    {"id": "F12_DST_D", "instr": "half_alu_fma12", "carrier": "B", "layout": "HI",
     "seeds": "A", "fields": ["dst"]},
    {"id": "F12_EXT_A", "instr": "half_alu_fma12", "carrier": "A", "layout": "HI",
     "seeds": "A", "fields": ["ext"]},
    {"id": "F12_EXT_B", "instr": "half_alu_fma12", "carrier": "B", "layout": "HI",
     "seeds": "B", "fields": ["ext"]},
    {"id": "HP_A", "instr": "half_pack", "carrier": "A", "layout": "HI", "seeds": "A",
     "fields": ["dstlo", "b3"]},
    {"id": "HP_B", "instr": "half_pack", "carrier": "B", "layout": "HI", "seeds": "B",
     "fields": ["dstlo", "b3"]},
]


def anchor_bytes(instr):
    if instr == "half_alu_fma12":
        return H.fma12(DST_FIXED, hA=HA, hB=HB, hC=HC, b2=FMA12_B2, b4=FMA12_B4,
                       tail=FMA12_TAIL)
    if instr == "half_pack":
        return H.halfpack(DST_FIXED, hB=HA, hA=HB, b2=HP_B2)
    raise ValueError(instr)


def set_field(blk, start, width, value):
    b = bytearray(blk)
    for i in range(width):
        bit = start + i
        byi = bit >> 3
        if byi >= len(b):
            raise IndexError("field bit %d lies outside the %d-byte block" % (bit, len(b)))
        mask = 1 << (bit & 7)
        if (value >> i) & 1:
            b[byi] |= mask
        else:
            b[byi] &= 0xFF ^ mask
    return bytes(b)


def set_byte(blk, byte_index, value):
    b = bytearray(blk)
    b[byte_index] = value & 0xFF
    return bytes(b)


def field_geom(instr, name):
    for f in INS[instr]["fields"]:
        if f["name"] == name:
            return f["start"], f["width"]
    raise KeyError("%s.%s" % (instr, name))


# --------------------------------------------------------------------------
# Falsifiers and controls.  Each carries a PRE-REGISTERED expectation, recorded in the case
# so the raw states what should happen before the run, not after.
# --------------------------------------------------------------------------
CTL_SEEDED_DESCRIPTORS = [0x0D, 0x0C, 0x11, 0x10, 0x13, 0x12, 0x0F, 0x0E]
CTL_UNSEEDED_DESCRIPTORS = [32, 62, 126]      # GPRs 16, 31, 63


def instruments(arm):
    """Returns [(field_label, bytes, meta)] for one arm."""
    instr = arm["instr"]
    a = anchor_bytes(instr)
    out = []
    nbytes = len(a)
    lay = H.LAYOUTS[arm["layout"]]
    null_blk = H.mov_imm(lay.R_ZERO, 0) * (nbytes // 2)
    out.append(("__fals_F1_null", null_blk,
                {"expect": "oracle MISMATCH (nothing is written) AND null_match TRUE",
                 "oracle_kind": "anchor_model"}))
    if instr == "half_alu_fma12":
        out.append(("__fals_F2_opsel", H.fma12(DST_FIXED, hA=HA, hB=HB, hC=HC,
                                               b2=(FMA12_B2 & ~7) | H.OPSEL_HADD,
                                               b4=FMA12_B4, tail=FMA12_TAIL),
                    {"expect": "oracle MISMATCH: opsel 6 -> 4 changes the operation",
                     "oracle_kind": "model"}))
        out.append(("__fals_F4_dstshift", a,
                    {"expect": "oracle MISMATCH by construction: the anchor writes r%d but "
                               "the oracle is asked to predict r%d" % (DST_FIXED, DST_FIXED + 1),
                     "oracle_kind": "model", "oracle_dst_override": DST_FIXED + 1}))
        for i, d in enumerate(CTL_SEEDED_DESCRIPTORS):
            out.append(("__ctl_live_srcA", H.fma12(DST_FIXED, hA=d, hB=HB, hC=HC,
                                                   b2=FMA12_B2, b4=FMA12_B4, tail=FMA12_TAIL),
                        {"expect": "oracle MATCH; the observable MUST move across these 8",
                         "oracle_kind": "model", "ctl_index": i, "ctl_desc": d}))
        for i, d in enumerate(CTL_UNSEEDED_DESCRIPTORS):
            out.append(("__ctl_unseeded", H.fma12(DST_FIXED, hA=d, hB=HB, hC=HC,
                                                  b2=FMA12_B2, b4=FMA12_B4, tail=FMA12_TAIL),
                        {"expect": "oracle-with-zero MATCH (carrier property, PRE_REG 4.4)",
                         "oracle_kind": "model", "ctl_index": i, "ctl_desc": d}))
    else:
        out.append(("__fals_F3_hp_opsel", H.halfpack(DST_FIXED, hB=HA, hA=HB, b2=HP_B2 | 1),
                    {"expect": "oracle MISMATCH: byte+2 0x18 -> 0x19 is a different op",
                     "oracle_kind": "model"}))
        out.append(("__fals_F4_dstshift", a,
                    {"expect": "oracle MISMATCH by construction (dst override)",
                     "oracle_kind": "model", "oracle_dst_override": DST_FIXED + 1}))
        for i, d in enumerate(CTL_SEEDED_DESCRIPTORS):
            out.append(("__ctl_hp_live", H.halfpack(DST_FIXED, hB=d, hA=HB, b2=HP_B2),
                        {"expect": "oracle MATCH; the observable MUST move across these 8",
                         "oracle_kind": "model", "ctl_index": i, "ctl_desc": d}))
        for i, d in enumerate(CTL_UNSEEDED_DESCRIPTORS):
            out.append(("__ctl_unseeded", H.halfpack(DST_FIXED, hB=d, hA=HB, b2=HP_B2),
                        {"expect": "oracle-with-zero MATCH (carrier property)",
                         "oracle_kind": "model", "ctl_index": i, "ctl_desc": d}))
    return out


# --------------------------------------------------------------------------
def build_cases():
    cases = []
    idx = 0
    for arm in ARMS:
        instr = arm["instr"]
        anc = anchor_bytes(instr)
        for label, blk, meta in instruments(arm):
            rec = {"idx": idx, "arm": arm["id"], "instr": instr, "field": label,
                   "value": meta.get("ctl_desc", -1), "byte_index": None,
                   "fstart": None, "fwidth": None,
                   "bytes": blk.hex(), "anchor": anc.hex(),
                   "carrier": arm["carrier"], "layout": arm["layout"],
                   "seeds": arm["seeds"], "kind": "instrument"}
            rec.update({k: v for k, v in meta.items() if k != "ctl_desc"})
            cases.append(rec)
            idx += 1
        for fname in arm["fields"]:
            start, width = field_geom(instr, fname)
            if width <= 8:
                for v in range(1 << width):
                    blk = set_field(anc, start, width, v)
                    cases.append({"idx": idx, "arm": arm["id"], "instr": instr,
                                  "field": fname, "value": v, "byte_index": None,
                                  "fstart": start, "fwidth": width,
                                  "bytes": blk.hex(), "anchor": anc.hex(),
                                  "carrier": arm["carrier"], "layout": arm["layout"],
                                  "seeds": arm["seeds"], "kind": "field",
                                  "oracle_kind": "model",
                                  "expect": "oracle MATCH if the field is what H1/H3/H4 say"})
                    idx += 1
            else:
                lo, hi = start // 8, (start + width - 1) // 8
                for bi in range(lo, hi + 1):
                    for v in range(256):
                        blk = set_byte(anc, bi, v)
                        cases.append({"idx": idx, "arm": arm["id"], "instr": instr,
                                      "field": fname, "value": v, "byte_index": bi,
                                      "fstart": start, "fwidth": width,
                                      "bytes": blk.hex(), "anchor": anc.hex(),
                                      "carrier": arm["carrier"], "layout": arm["layout"],
                                      "seeds": arm["seeds"], "kind": "field_byte",
                                      "oracle_kind": "model",
                                      "expect": "byte-resolved; `ext` CANNOT reach "
                                                "hardware-run (2048 of 2^64)"})
                        idx += 1
    return cases


def matrix_sha256(cases):
    h = hashlib.sha256()
    for c in cases:
        h.update(("%s|%s|%s|%s|%s\n" % (c["arm"], c["field"], c["value"],
                                        c["byte_index"], c["bytes"])).encode())
    return h.hexdigest()


if __name__ == "__main__":
    cs = build_cases()
    import collections
    print("cases:", len(cs), "sha256:", matrix_sha256(cs))
    for k, v in sorted(collections.Counter((c["arm"], c["field"]) for c in cs).items()):
        print("  %-12s %-18s %d" % (k[0], k[1], v))
