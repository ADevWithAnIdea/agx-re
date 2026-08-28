#!/usr/bin/env python3
"""EXP-0139 case matrix -- the frozen, deterministic list of sweep cases.

`build_cases(mains)` is a PURE function of the compiled `_agc.main` byte
strings handed to it, so the identical matrix is reproduced by both gated runs
and by `verify.py --selftest` with no device present.

Two carrier styles (see harness/sweeprun.py):
  SYNTH   -- `_agc.main` fully replaced by a program assembled from
             `tools/agx-isa` field rules that a prior experiment HW-VALIDATED.
  NATURAL -- our own compiled MSL left intact; exactly ONE instruction's bytes
             overwritten in place, at an offset resolved at run time by
             tokenizing the carrier (harness/anchors.py).

Every case carries a HOST-COMPUTED oracle (`FIELD-SWEEP-PROTOCOL` §3.4). Two
oracle kinds are used and are labelled per case:
  `model`    -- an independent host computation of what the mutated field
                should produce if the pre-registered semantic model is right.
                These are the cases that can promote a field to `hardware-run`
                with real semantics.
  `baseline` -- the unmutated carrier's own host-computed MSL semantics. Used
                where no semantic model exists yet; a `match` then means the
                field is INERT at that value and a mismatch is the finding.
`expect_match=False` marks the pre-registered falsifiers (§3.5).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import anchors as A          # noqa: E402
import isa_helpers as H      # noqa: E402
import isadb                 # noqa: E402  (imported by isa_helpers/anchors)

M32 = 0xFFFFFFFF

# ---------------------------------------------------------------------------
# Inputs (identical for every NATURAL carrier; asymmetric + boundary values)
# ---------------------------------------------------------------------------
A_IN = [0x12345678, 0xFFFFFFFF, 0x0000FF00, 0xDEADBEEF, 0x00000001,
        0x00000000, 0x80000000, 0x7FFFFFFF]
B_IN = [3, 5, 8, 1, 31, 32, 2, 0]
FA_IN = [1.5, -2.25, 0.0, 7.75, -0.5, 100.0, -100.0, 3.0]
FB_IN = [2.5, -2.25, 1.0, 7.75, 0.5, -100.0, 100.0, 3.0]
NIN = len(A_IN)


def s32(u):
    return u - (1 << 32) if u & 0x80000000 else u


# ---------------------------------------------------------------------------
# SYNTH carrier register plan (iadd2 arm)
# ---------------------------------------------------------------------------
DAG_CARRIER_LEN = 1536
SLOT_OUT = 0
R_IDX = 15          # index register for device_store, always 0
R_DST = 6           # iadd2 destination AND the register device_store reads
SENTINEL = 99       # r6's pre-seed: still there => iadd2 wrote somewhere else
SEED = {0: 10, 1: 21, 2: 22, 3: 23, 4: 24, 5: 25, 6: SENTINEL,
        7: 27, 8: 28, 9: 29, 10: 30, 11: 31, 12: 32, 13: 33, 14: 34, 15: 0}
IADD_N = 2                     # srcB selects r2
IADD_BASE_SUM = SEED[0] + SEED[IADD_N]      # 10 + 22 = 32


def roundtrips(prog):
    """True if the whole synthesized program re-tokenizes exactly. A MUTATED
    instruction is often deliberately undecodable by our own disassembler --
    that is a recorded property of the case (`rt_ok`), never a build error:
    the hardware, not `tools/agx-isa`, is the authority on what the bytes mean."""
    try:
        H.assert_round_trip(prog)
        return True
    except AssertionError:
        return False


def _seed_prog(extra):
    """mov_imm-seed r0..r15 (every immediate inside mov_imm's HW-VALIDATED
    0..127 range -- values >=128 silently zero and, with iadd2's N=0
    self-read, hung the GPU twice in EXP-0128), then `extra`, then stop."""
    instrs = [H.mov_imm(r, SEED[r]) for r in range(16)]
    instrs += extra
    instrs.append(H.stop())
    return H.build_program(instrs, DAG_CARRIER_LEN)


IADD2_BASE_FIELDS = dict(addsub=1, lenbit=1, srcB_reg_hi=0, b2_bit0=0,
                          store_en=1, b2_fmt=0x15, dst=(R_DST << 1),
                          opmode=2, srcB_imm=4 * IADD_N, srcB_imm_hi=0,
                          srcB_ext=0, srcA=H.IADD2_SRCA_R0_FIXED,
                          opc_tail=0x17, opc_tail2=5)


def iadd2_prog(**over):
    f = dict(IADD2_BASE_FIELDS)
    f.update(over)
    instr = isadb.assemble("iadd2", f)
    return _seed_prog([instr, H.device_store(R_IDX, 0, SLOT_OUT, data_reg=R_DST)])


def dst_relocation_oracle(dst_field):
    """Pre-registered model for the `dst` sweep.

    `dst` is (reg<<1)|size.  EXP-0112 (HW) found R in [64,112] aliases
    r(R mod 64) and R in {126,127} faults.  So: the sum lands in the store's
    register r6 iff the effective register is 6; otherwise r6 keeps its
    mov_imm sentinel.  This model is simultaneously a re-test of EXP-0112's
    aliasing claim on a completely different instruction family."""
    reg = dst_field >> 1
    eff = (reg % 64) if 64 <= reg <= 112 else reg
    return IADD_BASE_SUM if eff == R_DST else SENTINEL


def iadd2_cases():
    cs = []

    def add(field, value, oracle, kind, expect=True, note=""):
        cs.append(dict(arm="IADD2", instr="iadd2", field=field, value=value,
                       carrier="SYNTH:carrier_dag@k", splice_kind="synth",
                       build=("iadd2", {field: value}), instr_hex=isadb.assemble("iadd2", dict(IADD2_BASE_FIELDS, **{field: value})).hex(),
                       oracle={0: oracle}, oracle_kind=kind,
                       expect_match=expect, mode="int", grid=1, tg=1,
                       out_slot=SLOT_OUT, ins="dag", note=note))

    # -- control: the unmutated construction (EXP-0128's own HW-VALIDATED rule)
    cs.append(dict(arm="IADD2", instr="iadd2", field="_baseline", value=-1,
                   carrier="SYNTH:carrier_dag@k", splice_kind="synth",
                   build=("iadd2", {}), instr_hex=isadb.assemble("iadd2", IADD2_BASE_FIELDS).hex(), oracle={0: IADD_BASE_SUM},
                   oracle_kind="model", expect_match=True, mode="int", grid=1,
                   tg=1, out_slot=SLOT_OUT, ins="dag",
                   note="EXP-0128 register-mode rule, unmutated"))
    # -- positive control: a correct program against an unreachable oracle
    cs.append(dict(arm="IADD2", instr="iadd2", field="_poscontrol", value=-1,
                   carrier="SYNTH:carrier_dag@k", splice_kind="synth",
                   build=("iadd2", {}), instr_hex=isadb.assemble("iadd2", IADD2_BASE_FIELDS).hex(), oracle={0: IADD_BASE_SUM + 123456},
                   oracle_kind="model", expect_match=False, mode="int", grid=1,
                   tg=1, out_slot=SLOT_OUT, ins="dag",
                   note="deliberate unreachable oracle: proves match-detection is not a rubber stamp"))

    # dst: full 8-bit sweep against the relocation+aliasing model
    for v in range(256):
        exp = True
        note = ""
        if (v >> 1) in (126, 127):
            exp, note = False, "EXP-0112: r126/r127 fault"
        add("dst", v, dst_relocation_oracle(v), "model", exp, note)
    # addsub (control, already isolated-byte-diff): 0 => rN - r0 (EXP-0128 SS1.4)
    add("addsub", 1, IADD_BASE_SUM, "model", True, "add")
    add("addsub", 0, (SEED[IADD_N] - SEED[0]) & M32, "model", True,
        "EXP-0128 SS1.4: register-mode subtract is rN - r0, NOT r0 - rN")
    # single-bit modifier fields
    add("lenbit", 1, IADD_BASE_SUM, "baseline", True, "10-byte form")
    add("lenbit", 0, IADD_BASE_SUM, "baseline", False,
        "FALSIFIER: lenbit=0 selects the 12-byte form -> the instruction "
        "over-consumes the following device_store's first 2 bytes")
    for f in ("b2_bit0", "store_en", "srcB_imm_hi"):
        for v in (0, 1):
            nat = IADD2_BASE_FIELDS[f]
            add(f, v, IADD_BASE_SUM, "baseline", v == nat,
                "" if v == nat else "FALSIFIER: off-anchor value")
    # multi-bit modifier fields -- dense
    for v in range(64):
        add("b2_fmt", v, IADD_BASE_SUM, "baseline", v == 0x15)
    for v in range(256):
        add("opmode", v, IADD_BASE_SUM, "baseline", v == 2)
    for v in range(128):
        add("srcB_reg_hi", v, IADD_BASE_SUM, "baseline", v == 0)
        add("srcB_ext", v, IADD_BASE_SUM, "baseline", v == 0)
    for v in range(256):
        add("srcA", v, IADD_BASE_SUM, "baseline", v == H.IADD2_SRCA_R0_FIXED)
        add("opc_tail", v, IADD_BASE_SUM, "baseline", v == 0x17)
        add("opc_tail2", v, IADD_BASE_SUM, "baseline", v == 5)
    # srcB_imm control points (already hardware-run; re-anchors the seed table)
    for n in (0, 1, 2, 3, 7, 13, 14):
        exp_val = (SEED[0] + SEED[n]) & M32 if n != 0 else (SEED[0] + SEED[0]) & M32
        cs.append(dict(arm="IADD2", instr="iadd2", field="srcB_imm", value=4 * n,
                       carrier="SYNTH:carrier_dag@k", splice_kind="synth",
                       build=("iadd2", {"srcB_imm": 4 * n}), instr_hex=isadb.assemble("iadd2", dict(IADD2_BASE_FIELDS, srcB_imm=4 * n)).hex(),
                       oracle={0: exp_val}, oracle_kind="model", expect_match=True,
                       mode="int", grid=1, tg=1, out_slot=SLOT_OUT, ins="dag",
                       note="control: srcB_imm=4N selects rN (EXP-0128)"))
    return cs


# ---------------------------------------------------------------------------
# SYNTH carrier: ibitcount / iunary (the 8-byte byte0==0x27 space)
# ---------------------------------------------------------------------------
R_SRC = 3                       # popcount source register
POP_SRC_VAL = 0b1011011         # 91 -> popcount 5, inside mov_imm's 0..127
POP_EXPECT = bin(POP_SRC_VAL).count("1")


def bitcount_prog(**over):
    f = dict(fn_hi=0, form=5, cache=1, dst=(R_DST << 1), op_enable=2,
             src=(R_SRC << 2), srcdesc=0x5c, tail=4)
    f.update(over)
    instr = isadb.assemble("ibitcount", f)
    seeds = dict(SEED)
    return _seed_prog_with(seeds, [instr, H.device_store(R_IDX, 0, SLOT_OUT, data_reg=R_DST)])


def _seed_prog_with(seeds, extra):
    instrs = [H.mov_imm(r, seeds[r]) for r in range(16)]
    instrs += extra
    instrs.append(H.stop())
    return H.build_program(instrs, DAG_CARRIER_LEN)


SEED_POP = dict(SEED)
SEED_POP[R_SRC] = POP_SRC_VAL


IBITCOUNT_BASE_FIELDS = dict(fn_hi=0, form=5, cache=1, dst=(R_DST << 1),
                              op_enable=2, src=(R_SRC << 2), srcdesc=0x5c, tail=4)


def bitcount_prog2(**over):
    f = dict(IBITCOUNT_BASE_FIELDS)
    f.update(over)
    instr = isadb.assemble("ibitcount", f)
    return _seed_prog_with(SEED_POP, [instr, H.device_store(R_IDX, 0, SLOT_OUT, data_reg=R_DST)])


def bitcount_cases():
    cs = []

    def add(field, value, oracle, kind, expect=True, note=""):
        cs.append(dict(arm="IBITCOUNT", instr="ibitcount", field=field, value=value,
                       carrier="SYNTH:carrier_dag@k", splice_kind="synth",
                       build=("ibitcount", {field: value}), instr_hex=isadb.assemble("ibitcount", dict(IBITCOUNT_BASE_FIELDS, **{field: value})).hex(),
                       oracle={0: oracle}, oracle_kind=kind, expect_match=expect,
                       mode="int", grid=1, tg=1, out_slot=SLOT_OUT, ins="dag",
                       note=note))

    cs.append(dict(arm="IBITCOUNT", instr="ibitcount", field="_baseline", value=-1,
                   carrier="SYNTH:carrier_dag@k", splice_kind="synth",
                   build=("ibitcount", {}), instr_hex=isadb.assemble("ibitcount", IBITCOUNT_BASE_FIELDS).hex(), oracle={0: POP_EXPECT},
                   oracle_kind="model", expect_match=True, mode="int", grid=1, tg=1,
                   out_slot=SLOT_OUT, ins="dag",
                   note="synthesized popcount: r6 = popcount(r3=%d) = %d" % (POP_SRC_VAL, POP_EXPECT)))
    # PRIORITY-1 FIELD: tail -- the single field blocking ibitcount, dense 0..255
    for v in range(256):
        exp, note = (v == 4), ""
        if v == 2:
            note = "FALSIFIER: EXP-0129 observed tail=2 degrading the GPR read"
        add("tail", v, POP_EXPECT, "baseline", exp, note)
    # supporting controls that also re-test the family on a SYNTHESIZED carrier
    # (every prior ibitcount datum came from a compiler-emitted anchor)
    for v in range(8):
        add("form", v, POP_EXPECT, "baseline", v == 5)
    for v in (0, 1):
        add("fn_hi", v, POP_EXPECT, "baseline", v == 0)
        add("cache", v, POP_EXPECT, "baseline", v == 1)
    for r in range(16):
        add("src", r << 2, bin(SEED_POP[r]).count("1"), "model", True,
            "src=reg<<2 selects r%d (seed %d)" % (r, SEED_POP[r]))
    for r in range(16):
        add("dst", r << 1, POP_EXPECT if r == R_DST else SEED_POP[r], "model", True,
            "dst=reg<<1: result lands in r%d, the store still reads r6" % r)
    for v in range(256):
        add("srcdesc", v, POP_EXPECT, "baseline", v == 0x5c)
    for v in range(16):
        add("op_enable", v, POP_EXPECT, "baseline", (v >> 1) & 1 == 1)
    return cs


IUNARY_B1 = 0x2d      # a byte0=0x27 8-byte form that tokenizes as `iunary`
IUNARY_B2 = 0x22      #   (NOT ibitcount) and still computes -- pilot-located


def iunary_prog(operand_bytes):
    blob = bytes([0x27, IUNARY_B1, IUNARY_B2]) + operand_bytes
    assert len(blob) == 8
    return _seed_prog_with(SEED_POP, [blob, H.device_store(R_IDX, 0, SLOT_OUT, data_reg=R_DST)])


IUNARY_BASE_OPERAND = bytes([(R_DST << 1), 0x02, (R_SRC << 2), 0x5c, 0x04])


def iunary_cases():
    """`iunary.operand` is db.json's 40-bit RAW byte+3..+7 blob. This arm sweeps
    each of its five bytes on a program that tokenizes as `iunary` (byte+1 =
    0x2d, so the tighter `ibitcount` match does NOT win), testing the
    pre-registered model that the blob is really the SAME five one-byte
    sub-fields ibitcount already names: dst / op_enable / src / srcdesc / tail."""
    cs = []
    names = ["dst", "op_enable", "src", "srcdesc", "tail"]

    def add(sub, idx, value, oracle, kind, expect=True, note=""):
        ob = bytearray(IUNARY_BASE_OPERAND)
        ob[idx] = value
        cs.append(dict(arm="IUNARY", instr="iunary", field="operand",
                       subfield=sub, value=(idx << 8) | value, byte_index=idx,
                       byte_value=value, carrier="SYNTH:carrier_dag@k",
                       splice_kind="synth", build=("iunary", {"operand": bytes(ob).hex()}), instr_hex=(bytes([0x27, IUNARY_B1, IUNARY_B2]) + bytes(ob)).hex(),
                       oracle={0: oracle}, oracle_kind=kind, expect_match=expect,
                       mode="int", grid=1, tg=1, out_slot=SLOT_OUT, ins="dag",
                       note=note))

    cs.append(dict(arm="IUNARY", instr="iunary", field="operand", subfield="_baseline",
                   value=-1, byte_index=-1, byte_value=-1,
                   carrier="SYNTH:carrier_dag@k", splice_kind="synth",
                   build=("iunary", {"operand": IUNARY_BASE_OPERAND.hex()}), instr_hex=(bytes([0x27, IUNARY_B1, IUNARY_B2]) + IUNARY_BASE_OPERAND).hex(),
                   oracle={0: POP_EXPECT}, oracle_kind="model", expect_match=True,
                   mode="int", grid=1, tg=1, out_slot=SLOT_OUT, ins="dag",
                   note="byte0=0x27 b1=0x2d b2=0x22 -- tokenizes as iunary, not ibitcount"))
    # byte+5 (src): the model says reg<<2 selects the source register
    for r in range(16):
        add("src", 2, r << 2, bin(SEED_POP[r]).count("1"), "model", True,
            "model: operand byte 2 == ibitcount.src (reg<<2) -> r%d" % r)
    # byte+3 (dst): the model says reg<<1 relocates the result
    for r in range(16):
        add("dst", 0, r << 1, POP_EXPECT if r == R_DST else SEED_POP[r], "model", True,
            "model: operand byte 0 == ibitcount.dst (reg<<1) -> r%d" % r)
    # dense per-byte sweeps of the remaining three bytes + the two above
    for idx, sub in enumerate(names):
        for v in range(256):
            add(sub, idx, v, POP_EXPECT, "baseline",
                v == IUNARY_BASE_OPERAND[idx],
                "dense byte sweep of operand byte %d" % idx)
    return cs


# ---------------------------------------------------------------------------
# NATURAL carriers
# ---------------------------------------------------------------------------
NAT_SRC = "ialu_probes.metal"

# id -> (function, mnemonic, occurrence, input-set, oracle model)
NAT_ANCHORS = {
    "IBFE":      ("k_bfe_const",   "ibfe",      0, "uint"),
    "IBFE_SH":   ("k_shr",         "ibfe",      0, "uint"),
    "IBFINS":    ("k_shl",         "ibfins",    0, "uint"),
    "IMAD":      ("k_imad",        "imad",      0, "uint"),
    "IMINMAX":   ("k_umax",        "iminmax",   0, "uint"),
    "ISEL8":     ("k_abs",         "isel8",     0, "int"),
    "ISEL10":    ("k_cmpsel",      "isel10",    0, "uint"),
    "ISEL_REG":  ("k_bfe_const_s", "isel_reg",  0, "int"),
    "ISHIFT":    ("k_ashr",        "ishift",    0, "int"),
    "ICMPSEL":   ("k_cmpsel2",     "icmpsel",   0, "float"),
    "IBITCOUNT_NAT": ("k_pop",     "ibitcount", 0, "uint"),
    "ISEL10_C":  ("k_div",         "isel10_c",  0, "uint"),
    "ICMP_PRED": ("k_div",         "icmp_pred", 0, "uint"),
}


def baseline_oracle(kind):
    """Host-computed expected output of each NATURAL carrier's own MSL."""
    if kind == "k_bfe_const":
        return {i: (a >> 4) & 0xFF for i, a in enumerate(A_IN)}
    if kind == "k_bfe_const_s":
        v = {}
        for i, a in enumerate(A_IN):
            x = (a >> 4) & 0xFF
            v[i] = (x - 256 if x & 0x80 else x) & M32
        return v
    if kind == "k_shr":
        return {i: (a >> (b & 31)) & M32 for i, (a, b) in enumerate(zip(A_IN, B_IN))}
    if kind == "k_shl":
        return {i: (a << (b & 31)) & M32 for i, (a, b) in enumerate(zip(A_IN, B_IN))}
    if kind == "k_imad":
        return {i: (a * b + 7) & M32 for i, (a, b) in enumerate(zip(A_IN, B_IN))}
    if kind == "k_umax":
        return {i: max(a, b) for i, (a, b) in enumerate(zip(A_IN, B_IN))}
    if kind == "k_abs":
        return {i: abs(s32(a)) & M32 for i, a in enumerate(A_IN)}
    if kind == "k_cmpsel":
        return {i: (0xAA if a < b else 0x55) for i, (a, b) in enumerate(zip(A_IN, B_IN))}
    if kind == "k_ashr":
        return {i: (s32(a) >> 4) & M32 for i, a in enumerate(A_IN)}
    if kind == "k_cmpsel2":
        return {i: (1 if a < b else 0) for i, (a, b) in enumerate(zip(FA_IN, FB_IN))}
    if kind == "k_pop":
        return {i: bin(a).count("1") for i, a in enumerate(A_IN)}
    if kind == "k_div":
        return {i: (a // b if b else 0xFFFFFFFF) for i, (a, b) in enumerate(zip(A_IN, B_IN))}
    raise KeyError(kind)


# ---- per-field semantic models (the `model` oracles) -----------------------
def ibfe_offset_model(off):
    return {i: (a >> off) & 0xFF if off < 32 else 0 for i, a in enumerate(A_IN)}


def ibfe_width_model(w):
    if w == 0 or w >= 32:
        return {i: (a >> 4) & M32 for i, a in enumerate(A_IN)}
    return {i: (a >> 4) & ((1 << w) - 1) for i, a in enumerate(A_IN)}


def ishift_shamt_model(byte):
    if byte % 4:
        return None
    n = byte // 4
    if n > 31:
        return None
    return {i: (s32(a) >> n) & M32 for i, a in enumerate(A_IN)}


IMINMAX_SEL_MODEL = {
    0: lambda a, b: _fbits(max(_f(a), _f(b))),
    1: lambda a, b: _fbits(min(_f(a), _f(b))),
    4: lambda a, b: max(a, b),
    5: lambda a, b: min(a, b),
    6: lambda a, b: max(s32(a), s32(b)) & M32,
    7: lambda a, b: min(s32(a), s32(b)) & M32,
}


def _f(u):
    import struct
    return struct.unpack("<f", struct.pack("<I", u & M32))[0]


def _fbits(x):
    import struct
    return struct.unpack("<I", struct.pack("<f", x))[0]


ISEL10_CC_MODEL = {}   # filled by the sweep: classified post-hoc, oracle=baseline


def nat_cases(mains):
    """Build every NATURAL-carrier case. `mains` maps function name -> the
    compiled `_agc.main` bytes of that carrier."""
    cs = []

    def emit(arm, mn, fn, off, ln, field, value, blob, oracle, kind, expect,
             mode, note="", subfield=None):
        cs.append(dict(arm=arm, instr=mn, field=field, value=value,
                       carrier="NAT:%s@%s+0x%03x" % (fn, mn, off),
                       splice_kind="natural", fn=fn, splice_off=off,
                       instr_hex=blob.hex(), oracle=oracle, oracle_kind=kind,
                       expect_match=expect, mode=mode, grid=NIN, tg=NIN,
                       out_slot=2, ins=("float" if mode == "float" else "uint"),
                       note=note, subfield=subfield))

    for arm, (fn, mn, occ, ikind) in NAT_ANCHORS.items():
        main = mains[fn]
        off, ln, fields = A.find(main, mn, occ)
        anchor = main[off:off + ln]
        base = baseline_oracle(fn)
        mode = "int" if ikind == "int" else ("float_in" if ikind == "float" else "uint")
        # baseline (no splice)
        emit(arm, mn, fn, off, ln, "_baseline", -1, anchor, base, "model", True,
             mode, "unmutated anchor %s" % anchor.hex())
        # deliberate unreachable oracle -> proves match detection works
        bogus = {k: (v + 0x5A5A5A) & M32 for k, v in base.items()}
        emit(arm, mn, fn, off, ln, "_poscontrol", -1, anchor, bogus, "model",
             False, mode, "FALSIFIER: correct program vs unreachable oracle")
        for f in [x for ins in isadb.DB if ins["mnemonic"] == mn for x in ins["fields"]]:
            name, w = f["name"], f["width"]
            nat = A.get_field(anchor, mn, name)
            vals = list(range(1 << w)) if w <= 8 else _wide_values(w)
            for v in vals:
                blob = A.set_field(anchor, mn, name, v)
                oracle, okind, expect, note = base, "baseline", (v == nat), ""
                # --- semantic models, where one exists -----------------------
                if arm == "IBFE" and name == "offset":
                    oracle, okind = ibfe_offset_model(v), "model"
                    expect = True
                    note = "model: o = (a >> %d) & 0xFF" % v
                elif arm == "IBFE" and name == "width":
                    oracle, okind = ibfe_width_model(v), "model"
                    expect = True
                    note = "model: o = (a >> 4) & ((1<<%d)-1); w=0/w>=32 => no mask" % v
                elif arm == "ISHIFT" and name == "shamt":
                    m = ishift_shamt_model(v)
                    if m is not None:
                        oracle, okind, expect = m, "model", True
                        note = "model: shamt byte = n<<2 -> o = a >> %d (arithmetic)" % (v // 4)
                elif arm == "IMINMAX" and name == "sel" and v in IMINMAX_SEL_MODEL:
                    fnm = IMINMAX_SEL_MODEL[v]
                    oracle = {i: fnm(a, b) & M32 for i, (a, b) in enumerate(zip(A_IN, B_IN))}
                    okind, expect = "model", True
                    note = "model: sel=%d (db corpus map 0=fmax 1=fmin 4=umax 5=umin 6=imax 7=imin)" % v
                emit(arm, mn, fn, off, ln, name, v, blob, oracle, okind, expect,
                     mode, note)
    return cs


def _wide_values(w):
    """Boundaries + all powers of two + >=16 interior samples, per
    FIELD-SWEEP-PROTOCOL §3.3 for fields wider than 8 bits."""
    hi = (1 << w) - 1
    vals = {0, 1, 2, 3, hi, hi - 1, hi - 2, hi // 2, hi // 2 + 1, hi // 3, (2 * hi) // 3}
    vals |= {1 << k for k in range(w)}
    vals |= {(1 << k) - 1 for k in range(1, w)}
    step = max(1, (hi + 1) // 24)
    vals |= {(k * step) & hi for k in range(24)}
    vals |= {0x55 & hi, 0xAA & hi, 0x5A5A & hi, 0xA5A5 & hi}
    return sorted(v for v in vals if 0 <= v <= hi)


# ---------------------------------------------------------------------------
# EXTRAPOLATE-AND-TEST: encodings our own compiler never emitted
# ---------------------------------------------------------------------------
def extrapolated_cases(mains):
    """`isel_reg8` (byte+2==0x25, 8-byte) has NO anchor anywhere in our own
    compiled corpus. db.json says it "adopts the isel8 field layout". This arm
    CONSTRUCTS it from the isel8 anchor by rewriting byte+2 to 0x25 and then
    sweeps every isel_reg8 field on the result -- the Rosenzweig
    extrapolate-then-test method CLAUDE.md names as a primary job."""
    cs = []
    fn, mn0 = "k_abs", "isel8"
    main = mains[fn]
    off, ln, _ = A.find(main, mn0, 0)
    anchor = bytearray(main[off:off + ln])
    anchor[2] = 0x25
    anchor = bytes(anchor)
    recs, _ = isadb.disassemble(anchor)
    tok = recs[0]["mnemonic"] if recs else None
    base = baseline_oracle(fn)
    cs.append(dict(arm="ISEL_REG8", instr="isel_reg8", field="_baseline", value=-1,
                   carrier="NAT:%s@isel8+0x%03x (byte+2 -> 0x25)" % (fn, off),
                   splice_kind="natural", fn=fn, splice_off=off,
                   instr_hex=anchor.hex(), oracle=base, oracle_kind="model",
                   expect_match=False, mode="int", grid=NIN, tg=NIN, out_slot=2,
                   ins="uint", subfield=None,
                   note="EXTRAPOLATED: isel8 anchor with byte+2 0x0f -> 0x25; "
                        "tokenizes as %s. expect_match=False because the isel8 "
                        "abs() result is NOT predicted to survive the op change." % tok))
    if tok == "isel_reg8":
        for f in [x for ins in isadb.DB if ins["mnemonic"] == "isel_reg8" for x in ins["fields"]]:
            name, w = f["name"], f["width"]
            natv = A.get_field(anchor, "isel_reg8", name)
            for v in (range(1 << w) if w <= 8 else _wide_values(w)):
                blob = A.set_field(anchor, "isel_reg8", name, v)
                cs.append(dict(arm="ISEL_REG8", instr="isel_reg8", field=name,
                               value=v, carrier="NAT:%s@isel8+0x%03x(->0x25)" % (fn, off),
                               splice_kind="natural", fn=fn, splice_off=off,
                               instr_hex=blob.hex(), oracle=base,
                               oracle_kind="baseline", expect_match=False,
                               mode="int", grid=NIN, tg=NIN, out_slot=2,
                               ins="uint", subfield=None,
                               note="extrapolated isel_reg8 field sweep (natural=%d)" % natv))
    return cs


def build_cases(mains):
    cs = []
    cs += iadd2_cases()
    cs += bitcount_cases()
    cs += iunary_cases()
    cs += nat_cases(mains)
    cs += extrapolated_cases(mains)
    for i, c in enumerate(cs):
        c["i"] = i
        # tri-state pre-registered PREDICTION (FIELD-SWEEP-PROTOCOL SS3.5).
        # `match`    -- we predict the oracle is reproduced;
        # `mismatch` -- a pre-registered FALSIFIER: we predict it is NOT;
        # `unknown`  -- an honest dense sweep of a field with no model yet;
        #               the outcome IS the finding and no prediction is claimed.
        if c["note"].startswith("FALSIFIER") or c["field"] == "_poscontrol":
            c["predict"] = "mismatch"
        elif c["oracle_kind"] == "model":
            c["predict"] = "match" if c["expect_match"] else "mismatch"
        else:
            c["predict"] = "match" if c["expect_match"] else "unknown"
    return cs


# ---------------------------------------------------------------------------
# Lazy program materialization (keeps 30k x 1536-byte programs out of memory
# and out of raw/: the JSONL records only the MUTATED INSTRUCTION's bytes,
# which is exactly what FIELD-SWEEP-PROTOCOL SS4's `bytes` key asks for).
# ---------------------------------------------------------------------------
def materialize(case):
    """Return (splices, ) for sweeprun.Carrier.run(). SYNTH cases return one
    whole-program splice at offset 0; NATURAL cases return the single mutated
    instruction at its resolved anchor offset."""
    if case["splice_kind"] == "synth":
        kind, kw = case["build"]
        if kind == "iadd2":
            prog = iadd2_prog(**kw)
        elif kind == "ibitcount":
            prog = bitcount_prog2(**kw)
        elif kind == "iunary":
            prog = iunary_prog(bytes.fromhex(kw["operand"]))
        else:
            raise KeyError(kind)
        return [(0, bytes(prog))]
    return [(case["splice_off"], bytes.fromhex(case["instr_hex"]))]
