#!/usr/bin/env python3
"""EXP-0161 case matrix (frozen at CAPTURE_CONTRACT time; sha256 recorded there).

Two carrier styles per instruction where possible, so every load-bearing claim
has an independent second method:

  * `SYNTH`   -- the whole `_agc.main` is a program we assembled, whose r0..r14
                 are seeded by device_load from an authored SEED buffer (the
                 fix for EXP-0154's <=127 mov_imm seeds) and whose BLOCK is
                 lifted byte-for-byte out of the compiled form of our own MSL.
                 Oracle: the full 16-register architectural dump.
  * `INPLACE` -- our own probe kernel exactly as the compiler produced it, with
                 ONE instruction mutated in place. Oracle: a host-computed
                 function of an authored input vector.

CLEAN-ROOM: block bytes come from the compiled form of our own MSL; field
geometry comes from our own pinned tools/agx-isa/db.json.
"""
from __future__ import print_function

import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402

DB = json.loads((H.ISA_DIR / "db.json").read_text())
INS = dict((i["mnemonic"], i) for i in DB["instructions"])
M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF


# ---------------------------------------------------------------------------
# authored input vectors
# ---------------------------------------------------------------------------
def POISON_WORD(i):
    """0xDEADBEEF + i: positional, so an UNWRITTEN word identifies itself and a
    suspect fault can be adjudicated offline (FIELD-SWEEP-PROTOCOL 7A)."""
    return (0xDEADBEEF + i) & M32


def poison(nwords):
    return b"".join(struct.pack("<I", POISON_WORD(i)) for i in range(nwords))


def pack32(v):
    return b"".join(struct.pack("<I", x & M32) for x in v)


def pack64(v):
    return b"".join(struct.pack("<Q", x & M64) for x in v)


def packf(v):
    return b"".join(struct.pack("<f", float(x)) for x in v)


# EXP-0146's frozen u64 stimulus plus EXP-0153's four boundary rows, VERBATIM,
# so a G17P measurement is comparable with the M4 measurement it revisits.
# Rows 0,1,3,5,7,8,9,10,11 CARRY out of the low word; rows 2,4,6 do not -- that
# mixture is exactly the discriminating stimulus EXP-0154's carrier lacked.
U64_A = [0x0123456789ABCDEF, 0x00000001F0000000, 0x0000000312345678,
         0xFFFFFFFFFFFFFFFF, 0x0000000A7FFFFFFF, 0x0000000C80000000,
         0x0000000000000000, 0xDEADBEEFCAFEBABE, 0x8000000000000000,
         0x7FFFFFFFFFFFFFFF, 0xFFFFFFFF00000000, 0xFFFFFFFFFFFFFFFE]
U64_B = [0x00000000FEDCBA98, 0x0000000210000000, 0x0000000411111111,
         0x0000000000000001, 0x0000000B80000000, 0x0000000D80000000,
         0x0000000000000000, 0x1234567887654321, 0x8000000000000000,
         0x0000000000000001, 0x00000000FFFFFFFF, 0x0000000000000003]
N64 = len(U64_A)

# 32-bit stimulus: asymmetric, boundary, and every-bit-live values, so ibfe's
# offset/width and mov_zext16's narrow are observable at every bit position.
A_U32 = [0x12345678, 0xFFFFFFFF, 0x0000FF00, 0xDEADBEEF,
         0x00000001, 0x80000000, 0x7FFFFFFF, 0xA5A5A5A5,
         0x0F0F0F0F, 0xFEDCBA98, 0x00010001, 0xC0FFEE33]
NU32 = len(A_U32)

# positive finite floats: legal for rsqrt/log2/sqrt/exp2, distinct results
F_IN = [4.0, 9.0, 0.25, 16.0, 2.0, 64.0, 0.5, 100.0, 1.5, 36.0, 0.125, 81.0]
NF = len(F_IN)

# For the ROUND family every candidate rounding mode must give a DIFFERENT
# answer, so the stimulus is fractional and signed and straddles .5 both ways.
F_ROUND = [1.5, -1.5, 2.5, -2.5, 0.5, -0.5, 3.25, -3.25,
           7.75, -7.75, 0.125, -0.125]
assert len(F_ROUND) == NF


def _rsqrt(x):
    return 1.0 / (x ** 0.5)


def _f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


CARRIERS = {
    "u64add": dict(
        func="k_u64add", fast_math=False, grid=N64, tg=N64,
        inputs={0: ("a_u64.bin", pack64(U64_A)), 1: ("b_u64.bin", pack64(U64_B)),
                2: ("poison_u64.bin", poison(2 * N64))},
        outs={2: 8 * N64}, out_idx=2, dtype="u64",
        oracle=[(a + b) & M64 for a, b in zip(U64_A, U64_B)],
        tol=None,
        doc="out[gid] = a[gid] + b[gid] on `ulong`: the iadd2(lo) -> carry_gen "
            "-> psel -> iadd2(hi) chain, with a stimulus in which 9 of 12 rows "
            "genuinely carry out of the low word."),
    "zext16": dict(
        func="k_zext16", fast_math=False, grid=NU32, tg=NU32,
        inputs={0: ("a_u32.bin", pack32(A_U32)),
                1: ("poison_u32.bin", poison(NU32))},
        outs={1: 4 * NU32}, out_idx=1, dtype="u32",
        oracle=[a & 0xFFFF for a in A_U32], tol=None,
        doc="out[gid] = uint(ushort(a[gid])): EXP-0146's carrier, in which "
            "byte+1 was found INERT and attributed to ALU forwarding."),
    "bfe": dict(
        func="k_bfe", fast_math=False, grid=NU32, tg=NU32,
        inputs={0: ("a_u32.bin", pack32(A_U32)),
                1: ("poison_u32.bin", poison(NU32))},
        outs={1: 4 * NU32}, out_idx=1, dtype="u32",
        oracle=[(a >> 4) & 0xFF for a in A_U32], tol=None,
        doc="out[gid] = extract_bits(a[gid], 4u, 8u): EXP-0033's single-ibfe "
            "shape, the carrier EXP-0139 used for the offset/width rules."),
    "shr5": dict(
        func="k_shr_const", fast_math=False, grid=NU32, tg=NU32,
        inputs={0: ("a_u32.bin", pack32(A_U32)),
                1: ("poison_u32.bin", poison(NU32))},
        outs={1: 4 * NU32}, out_idx=1, dtype="u32",
        oracle=[(a >> 5) & M32 for a in A_U32], tol=None,
        doc="out[gid] = a[gid] >> 5u: a SECOND, independent ibfe lowering "
            "(offset=5, width=0 => extract-to-MSB)."),
    "rsqrt": dict(
        func="k_rsqrt", fast_math=False, grid=NF, tg=NF,
        inputs={0: ("f_in.bin", packf(F_IN)),
                1: ("poison_f32.bin", poison(NF))},
        outs={1: 4 * NF}, out_idx=1, dtype="f32",
        oracle=[_f32(_rsqrt(x)) for x in F_IN], tol=1e-5,
        doc="out[gid] = fast::rsqrt(a[gid]): ONE fspecial (0xaf, fnclass 1)."),
    "log2": dict(
        func="k_log2", fast_math=False, grid=NF, tg=NF,
        inputs={0: ("f_in.bin", packf(F_IN)),
                1: ("poison_f32.bin", poison(NF))},
        outs={1: 4 * NF}, out_idx=1, dtype="f32",
        oracle=[_f32(__import__("math").log2(x)) for x in F_IN], tol=1e-5,
        doc="out[gid] = fast::log2(a[gid]): ONE fspecial (0x2f, fnclass 2). "
            "Second, independent fspecial carrier."),
    "floor": dict(
        func="k_floor", fast_math=False, grid=NF, tg=NF,
        inputs={0: ("f_in2.bin", packf(F_ROUND)),
                1: ("poison_f32.bin", poison(NF))},
        outs={1: 4 * NF}, out_idx=1, dtype="f32",
        oracle=[_f32(__import__("math").floor(x)) for x in F_ROUND], tol=None,
        doc="out[gid] = floor(a[gid]): the DIRECT (0x2f) ROUND family, the only "
            "one in which db.json's byte+8 round-mode enum is claimed to apply. "
            "Its input vector has fractional and negative values so floor, ceil, "
            "trunc and rint all differ."),
    "rcp_precise": dict(
        func="k_rcp", fast_math=False, grid=NF, tg=NF,
        inputs={0: ("f_in.bin", packf(F_IN)),
                1: ("poison_f32.bin", poison(NF))},
        outs={1: 4 * NF}, out_idx=1, dtype="f32",
        oracle=[_f32(1.0 / x) for x in F_IN], tol=1e-6,
        doc="out[gid] = 1.0f/a[gid] without fast-math: a SECOND, independent "
            "fspecial_est carrier (the precise reciprocal lowering)."),
    "rsqrt_precise": dict(
        func="k_rsqrt_precise", fast_math=False, grid=NF, tg=NF,
        inputs={0: ("f_in.bin", packf(F_IN)),
                1: ("poison_f32.bin", poison(NF))},
        outs={1: 4 * NF}, out_idx=1, dtype="f32",
        oracle=[_f32(_rsqrt(x)) for x in F_IN], tol=1e-6,
        doc="out[gid] = precise::rsqrt(a[gid]): the Newton-Raphson lowering "
            "that uses the low-precision fspecial_est seed op."),
}


# ---------------------------------------------------------------------------
# byte / field mutation
# ---------------------------------------------------------------------------
def set_field(blk, tgt, start, width, value):
    """`blk` with the db field [start, start+width) of the instruction at byte
    offset `tgt` set to `value`; LSB-first across the instruction's bytes,
    exactly as tools/agx-isa/db.json defines it."""
    b = bytearray(blk)
    for i in range(width):
        bit = start + i
        byi = tgt + (bit >> 3)
        mask = 1 << (bit & 7)
        if (value >> i) & 1:
            b[byi] |= mask
        else:
            b[byi] &= 0xFF ^ mask
    return bytes(b)


def set_byte(blk, tgt, byte_index, value):
    b = bytearray(blk)
    b[tgt + byte_index] = value & 0xFF
    return bytes(b)


# ---------------------------------------------------------------------------
# arms
# ---------------------------------------------------------------------------
R1 = [0, 1]
R4 = list(range(16))
R6 = list(range(64))
R7 = list(range(128))
R8 = list(range(256))
SAFE_SRC = list(range(192))         # fspecial byte+3 SAFE region (EXP-0138)
DANGER_SRC = list(range(192, 256))  # lease-only

# arm -> dict(style, carrier, probe/anchor, offsets, fields, raw bytes, note)
ARMS = [
    # ---------------- carry_gen ------------------------------------------
    dict(arm="A_CARRY_INPLACE", style="inplace", carrier="u64add",
         instr="carry_gen", ioff=42,
         fields={"dst": R4, "srcA": R8, "srcB": R8, "cmpmode": R8, "b5": R8},
         raw={0: R8, 2: R8},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00),
                     ("__falsifier_b2", "raw", 2, 0x00)],
         note="byte0 low nibble and byte+2 are db.json MATCH bits, not fields, "
              "so both are probed raw. byte+2 := 0x00 is EXP-0038's A18 "
              "neutralisation, re-run here as F1b."),
    dict(arm="A_CARRY_SYNTH", style="synth", probe="k_u64add", kind="int",
         block=(32, 72), instr="carry_gen", ioff=10,
         fields={"dst": R4, "srcA": R8, "srcB": R8, "cmpmode": R8, "b5": R8},
         raw={0: R8, 2: R8},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00),
                     ("__falsifier_b2", "raw", 2, 0x00)],
         note="the iadd2(lo)->carry_gen->psel->iadd2(hi)->iadd2 run lifted "
              "whole; r1 and r3 (the low add's operands) both have bit31 set, "
              "so the add ALWAYS carries -- the EXP-0154 fix."),
    # ---------------- mov_zext16 -----------------------------------------
    dict(arm="B_ZEXT_SYNTH", style="synth", probe="k_zext16", kind="int",
         block=(18, 22), instr="mov_zext16", ioff=0,
         fields={"src_reg": R7, "src_flag": R1, "subform": R8, "extend": R8},
         raw={0: R8},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="the decisive carrier for EXP-0146's OPEN question: here the "
              "source is NOT the immediately preceding device_load, and every "
              "seeded register has a DISTINCT non-zero high halfword, so the "
              "zero-extend is not the identity and its result names its source."),
    dict(arm="B_ZEXT_INPLACE", style="inplace", carrier="zext16",
         instr="mov_zext16", ioff=18,
         fields={"src_reg": R7, "src_flag": R1, "subform": R8, "extend": R8},
         raw={0: R8},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="EXP-0146's own carrier, re-run on G17P as the control: if "
              "byte+1 is inert HERE and live in B_ZEXT_SYNTH, forwarding is "
              "the explanation."),
    # ---------------- ibfe ------------------------------------------------
    dict(arm="C_IBFE_BFE", style="inplace", carrier="bfe",
         instr="ibfe", ioff=18,
         fields={"offset": R6, "width": R6, "sign_ext": R1, "b6_bit0": R1},
         raw={},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="the offset-literal / width-mod-32 asymmetry, in a carrier whose "
              "32-bit stimulus makes every bit position live."),
    dict(arm="C_IBFE_SHR", style="inplace", carrier="shr5",
         instr="ibfe", ioff=18,
         fields={"offset": R6, "width": R6},
         raw={},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="a SECOND, independent ibfe lowering (logical shift right)."),
    dict(arm="C_IBFE_SYNTH", style="synth", probe="k_bfe", kind="int",
         block=(18, 30), instr="ibfe", ioff=0,
         fields={"offset": R6, "width": R6},
         raw={},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="third method: the same two fields in the synthesized carrier, "
              "judged by the 16-register dump."),
    # ---------------- fspecial (SAFE region only) -------------------------
    dict(arm="D_FSPEC_INPLACE", style="inplace", carrier="rsqrt",
         instr="fspecial", ioff=18,
         fields={"fn_hi": R1, "fnclass": R4, "dst": R4, "src_cache": R8,
                 "src": SAFE_SRC, "src_class": R8, "src_ext": R8,
                 "fnsel": R8, "precsel": R8, "roundmode": R8,
                 "sched_flag": R8},
         raw={0: R8},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="ELEVEN fields nobody has ever swept. `src` is restricted to the "
              "SAFE region 0..191; 192..255 is arm G, under the GPU lease."),
    dict(arm="D2_FSPEC_LOG2", style="inplace", carrier="log2",
         instr="fspecial", ioff=18,
         fields={"fnclass": R4, "fnsel": R8, "precsel": R8, "roundmode": R8,
                 "fn_hi": R1},
         raw={},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="second, independent fspecial carrier (0x2f direct family) for "
              "the function/precision selectors."),
    dict(arm="D3_FSPEC_SYNTH", style="synth", probe="k_rsqrt", kind="float",
         block=(18, 28), instr="fspecial", ioff=0,
         fields={"fn_hi": R1, "fnclass": R4, "dst": R4, "src_cache": R8,
                 "src": SAFE_SRC, "src_class": R8, "src_ext": R8,
                 "fnsel": R8, "precsel": R8, "roundmode": R8,
                 "sched_flag": R8},
         raw={0: R8},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="the operand->register map for fspecial, via the 16-register "
              "dump and float seeds."),
    # ---------------- fspecial_est ---------------------------------------
    dict(arm="E_FSPEC_EST", style="inplace", carrier="rsqrt_precise",
         instr="fspecial_est", ioff=18,
         fields={"dst": R4, "srcA": R8, "subop": R8, "b4": R8, "b5": R8},
         raw={0: R8},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="b4/b5 are the two remaining tokenization-only fields blocking "
              "fspecial_est; dst/srcA/subop are re-run as controls."),
]

# The lease-only arm. NEVER included in the unlocked matrix.
DANGER_ARM = dict(
    arm="G_FSPEC_DANGER", style="inplace", carrier="rsqrt",
    instr="fspecial", ioff=18,
    fields={"src": DANGER_SRC}, raw={}, falsifiers=[],
    note="EXP-0138 recorded three reproducible GPU hangs at byte+3 192/193/194 "
         "under a 12 s watchdog and safety-stopped. Run ONLY under "
         "~/agxre/gpulease.sh, 12 s watchdog, STOP after two genuine hangs.")


# ---------------------------------------------------------------------------
# SUPPLEMENTARY arms (CAPTURE_CONTRACT amendment_01), added after run01/run02
# to give three fields a SECOND independent carrier. Each is a new carrier for
# a field already swept, never a re-run of a case already recorded.
# ---------------------------------------------------------------------------
SUPP_ARMS = [
    dict(arm="B2_ZEXT_SYNTH_R5", style="synth", probe="k_zext16", kind="int",
         block=(18, 22), instr="mov_zext16", ioff=0,
         block_patch=[(0, 0x53)],
         fields={"src_reg": R7, "src_flag": R1, "subform": R8, "extend": R8},
         raw={},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="the r5 form of mov_zext16 (byte0 high nibble = 5), which run01 "
              "showed drives `r5 = r5 & 0xFFFF`. A SECOND independent context "
              "for src_reg/src_flag: if they are inert here too, the inertness "
              "is a property of the field and not of the r1 anchor."),
    dict(arm="E2_FSPEC_EST_RCP", style="inplace", carrier="rcp_precise",
         instr="fspecial_est", ioff=18,
         fields={"dst": R4, "srcA": R8, "subop": R8, "b4": R8, "b5": R8},
         raw={0: R8},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="second, independent fspecial_est carrier (precise 1/x rather "
              "than precise rsqrt)."),
    dict(arm="C2_IBFE_SHR_X", style="inplace", carrier="shr5",
         instr="ibfe", ioff=18,
         fields={"sign_ext": R1, "b6_bit0": R1, "b2_bit0": R1, "store_en": R1},
         raw={},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="second carrier for ibfe's 1-bit fields."),
]


# CAPTURE_CONTRACT amendment_02: a THIRD batch, kept in its own list so the
# supp02/supp03 gated pair's matrix stays byte-identical to what it ran.
SUPP2_ARMS = [
    dict(arm="D4_FSPEC_FLOOR", style="inplace", carrier="floor",
         instr="fspecial", ioff=18,
         fields={"roundmode": R8, "fnclass": R4, "fn_hi": R1, "precsel": R8,
                 "fnsel": R8},
         raw={},
         falsifiers=[("__falsifier_byte0", "raw", 0, 0x00)],
         note="CAPTURE_CONTRACT amendment_02. run01/run02 showed that on the "
              "rsqrt and log2 datapaths only bit0 of byte+8 is live (and set, "
              "it returns NaN). db.json's round-mode enum (0 nearest / 2 floor "
              "/ 4 ceil / 6 trunc) is claimed only for the ROUND family, so it "
              "is tested HERE, on a floor carrier, by computed value."),
]


def _anchor_block(rep, arm):
    main = bytes.fromhex(rep[arm["probe"]]["main_hex"])
    lo, hi = arm["block"]
    return main[lo:hi]


def build_cases(anchor_report, arms=None, include_danger=False):
    arms = list(arms if arms is not None else ARMS)
    if include_danger:
        arms = arms + [DANGER_ARM]
    cases = []
    for a in arms:
        if a["style"] == "synth":
            blk = _anchor_block(anchor_report, a)
        else:
            c = CARRIERS[a["carrier"]]
            blk = bytes.fromhex(anchor_report[c["func"]]["main_hex"])
        for (bi, bv) in a.get("block_patch", []):
            blk = set_byte(blk, a["ioff"], bi, bv)
        tgt = a["ioff"]
        ilen = INS[a["instr"]]["length"]
        base = dict(arm=a["arm"], style=a["style"], instr=a["instr"],
                    ioff=tgt, kind=a.get("kind", ""),
                    carrier=a.get("carrier", ""), probe=a.get("probe", ""),
                    anchor=blk[tgt:tgt + ilen].hex())
        # pre-registered falsifiers FIRST, so a broken arm is visible early
        for (name, how, idx, val) in a["falsifiers"]:
            nb = set_byte(blk, tgt, idx, val)
            c = dict(base)
            c.update(field=name, value=val, bytes=nb.hex(),
                     byte_index=idx, predict="not_ok")
            cases.append(c)
        c = dict(base)
        c.update(field="__baseline", value=0, bytes=blk.hex(), predict="ok")
        cases.append(c)
        fdefs = dict((f["name"], f) for f in INS[a["instr"]]["fields"])
        for fname, vals in sorted(a["fields"].items()):
            f = fdefs[fname]
            for v in vals:
                nb = set_field(blk, tgt, f["start"], f["width"], v)
                c = dict(base)
                c.update(field=fname, value=v, bytes=nb.hex(),
                         fstart=f["start"], fwidth=f["width"], predict="")
                cases.append(c)
        for bi, vals in sorted(a.get("raw", {}).items()):
            for v in vals:
                nb = set_byte(blk, tgt, bi, v)
                c = dict(base)
                c.update(field="__raw_b%d" % bi, value=v, bytes=nb.hex(),
                         byte_index=bi, predict="")
                cases.append(c)
    for i, c in enumerate(cases):
        c["idx"] = i
    return cases


def matrix_sha256(cases):
    import hashlib
    blob = json.dumps([[c["arm"], c["field"], c["value"], c["bytes"]]
                       for c in cases], sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def main():
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cs = build_cases(rep)
    dg = build_cases(rep, arms=[], include_danger=True)
    print("unlocked cases:", len(cs))
    print("matrix_sha256 :", matrix_sha256(cs))
    print("danger cases  :", len(dg))
    print("danger_sha256 :", matrix_sha256(dg))
    from collections import Counter
    for a, n in sorted(Counter(c["arm"] for c in cs).items()):
        print("   %-18s %5d" % (a, n))


if __name__ == "__main__":
    main()
