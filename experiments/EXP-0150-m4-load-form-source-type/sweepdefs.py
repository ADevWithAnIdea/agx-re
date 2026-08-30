#!/usr/bin/env python3
"""EXP-0150 sweep matrix: every case declared once, frozen before capture.

All cases are `synth`: a COMPLETE hand-assembled AGX program (tools/agx-isa
`isadb.assemble()` only, never a captured byte string) spliced over the whole of
`kernels/carrier.metal`'s compiled `_agc.main[0:CARRIER_LEN]`. That is the
strongest evidence level in CODEX.md step 3 -- an independently generated
encoding executed on hardware.

Program skeleton, identical in every case:

    mov_imm(rIDX, 0)                              # index register := 0
    falu2i(rCAN = rIDX + 8.0, mods=0x00)          # SENTINEL, independent path
    device_store(out[word 4] = rCAN)              #   -> out[4] == 8.0 iff we ran
    <source setup: device_load(s) and/or falu2i ALU seed(s)>
    <the consuming instruction under test>
    mov_imm(rIDX, 0)                              # re-zero: a swept load
                                                  # destination may have hit rIDX
    device_store(out[word 0] = result)            # the observation
    stop()
    mov_imm(rPAD, 0) * n                          # padding AFTER stop: never runs

Oracles are host-computed here from the ISA semantics we authored; nothing is
read off a GPU run. Each case also carries the SILENT SIGNATURES -- the values
that result if one or both operands read as 0.0 -- because on this hardware a
wrong field value yields a silent zero, not a fault.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402
import carriers as C  # noqa: E402

CARRIER_LEN = 170          # asserted against the freshly compiled carrier

# --- the authored constants ------------------------------------------------
K_CONS = H.imm_value(1.5)     # falu2i consumer immediate
SEED_A = H.imm_value(2.0)     # ALU seed placed in rA
SEED_B = H.imm_value(5.0)     # ALU seed placed in rB
V_A = C.V_A                   # -8.5   loaded from mem[1]
V_B = C.V_B                   #  7.25  loaded from mem[2]

# every value used in an oracle must be exactly what the hardware computes
for _n, _v, _w in (("K_CONS", K_CONS, 1.5), ("SEED_A", SEED_A, 2.0),
                   ("SEED_B", SEED_B, 5.0),
                   ("SENTINEL", H.imm_value(C.SENTINEL_VALUE), C.SENTINEL_VALUE)):
    if _v != _w:
        raise SystemExit("minifloat codec cannot represent %s exactly: %r != %r"
                         % (_n, _v, _w))

PF = (0, 1, 2, 3)             # producer form bits, extmode[7:6]
CF = (0x00, 0x40, 0x80, 0xC0)  # consumer source-type bits, byte[7:6]


# ---------------------------------------------------------------------------
# program construction
# ---------------------------------------------------------------------------
def _canary():
    """Integrity sentinel, written before the instruction under test through a
    path that does not involve it: out[word 4] = 8.0. A `STATUS OK` run whose
    sentinel did not land is an INVALID measurement, not a silent zero."""
    return [H.mov_imm(H.R_IDX, 0),
            H.falu2i_raw(H.R_CAN, H.R_IDX, C.SENTINEL_VALUE, mods=0x00),
            H.device_store(index_reg=H.R_IDX, base_slot=C.SLOT_OUT,
                           data_reg=H.R_CAN, idx_off=1, addr_mode=0x54)]


def _epilogue(data_reg=None, extmode=None, addr_mode=0x54):
    return [H.mov_imm(H.R_IDX, 0),
            H.device_store(index_reg=H.R_IDX, base_slot=C.SLOT_OUT,
                           data_reg=data_reg, extmode=extmode, idx_off=0,
                           addr_mode=addr_mode)]


def _build(instrs, pad_dst=H.R_PAD):
    body = b"".join(instrs) + H.stop()
    if len(body) > CARRIER_LEN:
        raise ValueError("program body %d bytes exceeds carrier %d"
                         % (len(body), CARRIER_LEN))
    rem = CARRIER_LEN - len(body)
    if rem % 2:
        raise ValueError("odd padding remainder %d" % rem)
    out = body + H.mov_imm(pad_dst, 0) * (rem // 2)
    assert len(out) == CARRIER_LEN
    return out


def _src(kind, reg, which):
    """Source setup for register `reg`. `which` selects the constant so the two
    operands of a falu2 are always distinguishable.

    kind == 'load'  ->  device_load mem[1 or 2]  (value V_A / V_B)
    kind == 'alu'   ->  falu2i(reg = rIDX + SEED) (value SEED_A / SEED_B)
    """
    if kind == "load":
        return ([H.device_load(index_reg=H.R_IDX, base_slot=C.SLOT_MEM,
                               extmode=2 * reg, idx_off=1 if which == "A" else 2)],
                V_A if which == "A" else V_B)
    if kind == "alu":
        return ([H.falu2i_raw(reg, H.R_IDX, SEED_A if which == "A" else SEED_B,
                              mods=0x00)],
                SEED_A if which == "A" else SEED_B)
    raise ValueError(kind)


def prog_falu2i(src, mods, cons_reg=None, extmode=None, D=H.R_D):
    """<source into rA>; falu2i(rD = r{cons_reg} + 1.5, mods); store out[0]=rD."""
    cons_reg = H.R_A if cons_reg is None else cons_reg
    if src == "load":
        setup = [H.device_load(index_reg=H.R_IDX, base_slot=C.SLOT_MEM,
                               extmode=2 * H.R_A if extmode is None else extmode,
                               idx_off=1)]
        val = V_A
    else:
        setup, val = _src("alu", H.R_A, "A")
    body = _canary() + setup + \
        [H.falu2i_raw(D, cons_reg, K_CONS, mods=mods)] + _epilogue(data_reg=D)
    oracle = val + K_CONS
    silent = [("srcA_zero", 0.0 + K_CONS)]
    return _build(body), oracle, silent, setup[0]


def prog_falu2(kindA, kindB, byte5, opflags5=1, ctrl=0, D=H.R_D):
    """<source into rA>; <source into rB>; falu2(rD = rA + rB, byte5); store."""
    setA, vA = _src(kindA, H.R_A, "A")
    setB, vB = _src(kindB, H.R_B, "B")
    neg = (byte5 >> 3) & 1
    instr = H.falu2_raw(D, H.R_A, H.R_B, byte5, opflags5=opflags5, ctrl=ctrl)
    body = _canary() + setA + setB + [instr] + _epilogue(data_reg=D)
    sB = -vB if neg else vB
    oracle = vA + sB
    silent = [("srcA_zero", 0.0 + sB), ("srcB_zero", vA), ("both_zero", 0.0)]
    return _build(body), oracle, silent, instr, ("negated" if neg else "nominal")


def prog_store(src, extmode, addr_mode, data_reg=None):
    """<source into r{data_reg}>; store out[0] = that register, with the store's
    own extmode / addr_mode under test."""
    if src == "load":
        data_reg = H.R_A if data_reg is None else data_reg
        setup = [H.device_load(index_reg=H.R_IDX, base_slot=C.SLOT_MEM,
                               extmode=2 * data_reg, idx_off=1)]
        val = V_A
    else:
        data_reg = H.R_D if data_reg is None else data_reg
        setup, val = _src("alu", data_reg, "A")
    store = H.device_store(index_reg=H.R_IDX, base_slot=C.SLOT_OUT,
                           extmode=extmode, idx_off=0, addr_mode=addr_mode)
    body = _canary() + setup + [H.mov_imm(H.R_IDX, 0), store]
    silent = [("no_data", 0.0)]
    return _build(body), val, silent, store


def prog_sentinel_only():
    """FALSIFIER for the poison mechanism: canary only, no store to out[0].
    out[0] must come back as 0xDEADBEEF -- proving the readback distinguishes
    'the GPU wrote nothing' from 'the GPU wrote zero'."""
    return _build(_canary())


# ---------------------------------------------------------------------------
# case / arm helpers
# ---------------------------------------------------------------------------
def _case(arm, instr, field, value, prog, oracle, silent, ibytes="", note="",
          expect_match=None, meta=None, roundtrip=False, variant="nominal"):
    c = {"arm": arm, "instr": instr, "field": field, "value": value,
         "prog": prog.hex(), "oracle": {"out0": oracle}, "silent": silent,
         "ibytes": ibytes, "note": note, "expect_match": expect_match,
         "meta": meta or {}, "oracle_variant": variant}
    # CODEX step 10 round trip, RECORDED per case (a swept value may legitimately
    # retokenize the program), ASSERTED on controls.
    try:
        H.assert_round_trip(prog)
        c["rt"] = True
    except AssertionError:
        c["rt"] = False
    if roundtrip and not c["rt"]:
        raise AssertionError("control case %s/%s failed round trip" % (arm, field))
    return c


def _arm(name, instr, field, cases, doc):
    return {"arm": name, "instr": instr, "field": field, "cases": cases, "doc": doc}


# ---------------------------------------------------------------------------
# the matrix
# ---------------------------------------------------------------------------
def build_controls():
    cs = []

    p, o, s, ib = prog_falu2i("load", 0xC0)
    cs.append(_case("CTRL", "falu2i", "_load_baseline", 0xC0, p, o, s, ib.hex(),
                    "EXP-0101's HW-VALIDATED load->falu2i construction, mods=0xC0.",
                    True, roundtrip=True))
    p, o, s, ib = prog_falu2i("load", 0x00)
    cs.append(_case("CTRL", "falu2i", "_load_mods0", 0x00, p, o, s, ib.hex(),
                    "EXP-0101 adversarial: load-sourced operand with mods=0. "
                    "PRE-REGISTERED TO FAIL (expect 1.5).", False, roundtrip=True))
    p, o, s, ib = prog_falu2i("alu", 0x00)
    cs.append(_case("CTRL", "falu2i", "_alu_baseline", 0x00, p, o, s, ib.hex(),
                    "ALU(falu2i)-sourced operand with mods=0 (expect 3.5).",
                    True, roundtrip=True))
    p, o, s, ib = prog_falu2i("alu", 0xC0)
    cs.append(_case("CTRL", "falu2i", "_alu_mods_C0", 0xC0, p, o, s, ib.hex(),
                    "H4 PREDICTION: ALU-sourced operand with the LOAD form. "
                    "Pre-registered to FAIL; if it passes, the bits are "
                    "indifferent for ALU sources.", False))
    p, o, s, ib = prog_falu2i("load", 0xC0, cons_reg=39)
    cs.append(_case("CTRL", "falu2i", "_wrong_reg", 39, p, o, s, ib.hex(),
                    "detection check: correct form, consumer pointed at r39 "
                    "while the load targets r7. PRE-REGISTERED TO FAIL.",
                    False, roundtrip=True))

    p, o, s, ib = prog_store("load", 2 * H.R_A, 0x56)
    cs.append(_case("CTRL", "device_store", "_fwd_baseline", 2 * H.R_A, p, o, s,
                    ib.hex(), "load-forwarded store, addr_mode=0x56 (expect -8.5).",
                    True, roundtrip=True))
    p, o, s, ib = prog_store("load", 2 * H.R_A, 0x54)
    cs.append(_case("CTRL", "device_store", "_fwd_am54", 0x54, p, o, s, ib.hex(),
                    "EXP-0141 H2 adversarial: load-forwarded store with "
                    "addr_mode=0x54. PRE-REGISTERED TO FAIL.", False, roundtrip=True))
    p, o, s, ib = prog_store("alu", 2 * H.R_D, 0x54)
    cs.append(_case("CTRL", "device_store", "_alu_baseline", 2 * H.R_D, p, o, s,
                    ib.hex(), "ALU-sourced store, addr_mode=0x54 (expect 2.0).",
                    True, roundtrip=True))

    p, o, s, ib, var = prog_falu2("load", "load", 0xC0)
    cs.append(_case("CTRL", "falu2", "_LL_baseline", 0xC0, p, o, s, ib.hex(),
                    "falu2 with BOTH operands load-sourced, byte+5=0xC0 "
                    "(expect -1.25).", None, roundtrip=True, variant=var))
    p, o, s, ib, var = prog_falu2("load", "load", 0x00)
    cs.append(_case("CTRL", "falu2", "_LL_b5_00", 0x00, p, o, s, ib.hex(),
                    "same with byte+5=0x00. PREDICTED TO FAIL.", False,
                    roundtrip=True, variant=var))
    p, o, s, ib, var = prog_falu2("alu", "alu", 0x00)
    cs.append(_case("CTRL", "falu2", "_AA_baseline", 0x00, p, o, s, ib.hex(),
                    "falu2 with BOTH operands ALU-sourced, byte+5=0x00 "
                    "(predicted 7.0).", None, roundtrip=True, variant=var))

    p = prog_sentinel_only()
    cs.append(_case("CTRL", "-", "_poison_falsifier", 0, p, C.POISON_F32,
                    [("wrote_zero", 0.0)], "",
                    "canary only, nothing stored to out[0]: the readback MUST "
                    "come back 0xDEADBEEF. Proves 'wrote nothing' is "
                    "distinguishable from 'wrote zero'.", True, roundtrip=True))
    return [_arm("CTRL", "-", "_controls", cs,
                 "baselines, pre-registered falsifiers, and the poison falsifier")]


def build_h1():
    arms = []

    # --- H1: producer extmode DENSE with the consumer FIXED at r7 -----------
    cs = []
    for v in range(256):
        p, o, s, ib = prog_falu2i("load", 0xC0, cons_reg=H.R_A, extmode=v)
        cs.append(_case("H1_extmode_dense_r7", "device_load", "extmode", v, p, o,
                        s, ib.hex(),
                        "consumer FIXED at r7 (unlike EXP-0141's paired sweep)",
                        None, {"pf": (v >> 6) & 3, "reg_interp": v >> 1,
                               "cons_reg": H.R_A}))
    arms.append(_arm("H1_extmode_dense_r7", "device_load", "extmode", cs,
                     "device_load.extmode 0..255 DENSE with the consumer register "
                     "HELD at r7. This is the arm EXP-0141 could not run: its "
                     "L_extmode paired the consumer to r(v>>1), which cannot "
                     "separate 'bit 6 is register bit 5' from 'bit 6 is a form "
                     "bit and the paired consumer was pointed at the wrong "
                     "register'. Predicted accepted set: {0x0E, 0x0F}."))

    # --- H1: WHERE DID IT LAND (the model discriminator) --------------------
    cs = []
    for R0 in (7, 20):
        for pf in PF:
            em = (2 * R0) | (pf << 6)
            for cons in (R0, em >> 1):
                p, o, s, ib = prog_falu2i("load", 0xC0, cons_reg=cons, extmode=em)
                cs.append(_case("H1_land", "device_load", "extmode", em, p, o, s,
                                ib.hex(),
                                "pf=%d base r%d, consumer field %d (effective r%d)"
                                % (pf, R0, cons, H.eff_reg(cons)), None,
                                {"pf": pf, "base_reg": R0, "cons_reg": cons,
                                 "eff_cons_reg": H.eff_reg(cons),
                                 "interp": "form" if cons == R0 else "register"}))
    arms.append(_arm("H1_land", "device_load", "extmode", cs,
                     "For each producer form pf, the SAME load run against both "
                     "candidate consumer registers: the form-model target (base "
                     "register unchanged) and the register-model target "
                     "(extmode>>1). Disjoint predictions -- see PRE_REGISTRATION "
                     "H1."))
    return arms


def build_h2():
    arms = []
    for tag, paired in (("fixed", False), ("paired", True)):
        cs = []
        for pf in PF:
            em = (2 * H.R_A) | (pf << 6)
            cons = (em >> 1) if paired else H.R_A
            for cf in CF:
                p, o, s, ib = prog_falu2i("load", cf, cons_reg=cons, extmode=em)
                cs.append(_case("H2_44_" + tag, "falu2i", "mods", cf, p, o, s,
                                ib.hex(), "pf=%d cf=0x%02X consumer r%d (eff r%d)"
                                % (pf, cf, cons, H.eff_reg(cons)), None,
                                {"pf": pf, "cf": cf >> 6, "extmode": em,
                                 "cons_reg": cons,
                                 "eff_cons_reg": H.eff_reg(cons)}))
        arms.append(_arm("H2_44_" + tag, "falu2i", "mods", cs,
                         "the dispatched 4x4: producer form x consumer "
                         "source-type bits, consumer at the %s-model register."
                         % ("register" if paired else "form")))
    return arms


def build_h3_h4():
    arms = []

    # --- falu2i byte+5 DENSE under both operand provenances -----------------
    for src, tag in (("load", "load"), ("alu", "alu")):
        cs = []
        for v in range(256):
            p, o, s, ib = prog_falu2i(src, v)
            cs.append(_case("C_falu2i_b5_" + tag, "falu2i", "mods", v, p, o, s,
                            ib.hex(), "operand provenance = %s" % src, None,
                            {"cf": (v >> 6) & 3, "src": src}))
        arms.append(_arm("C_falu2i_b5_" + tag, "falu2i", "mods", cs,
                         "falu2i byte+5 (`mods`, instruction bits 47:40) DENSE "
                         "0..255 with a %s-sourced operand. EXP-0101 tested 8 "
                         "points here under one provenance; 01/10 were never "
                         "run." % src))

    # --- falu2 byte+5 DENSE under all four provenance combinations ----------
    for kA, kB in (("load", "load"), ("load", "alu"), ("alu", "load"),
                   ("alu", "alu")):
        tag = kA[0].upper() + kB[0].upper()
        cs = []
        for v in range(256):
            p, o, s, ib, var = prog_falu2(kA, kB, v)
            cs.append(_case("C_falu2_b5_" + tag, "falu2", "byte5", v, p, o, s,
                            ib.hex(), "srcA=%s srcB=%s" % (kA, kB), None,
                            {"cf": (v >> 6) & 3, "srcA": kA, "srcB": kB,
                             "mod_lo": v & 7, "srcB_neg": (v >> 3) & 1,
                             "mod_hi": (v >> 4) & 0xF}, variant=var))
        arms.append(_arm("C_falu2_b5_" + tag, "falu2", "byte5", cs,
                         "falu2 byte+5 DENSE 0..255 with srcA=%s, srcB=%s. Bits "
                         "7:6 of this byte are instruction bits 47:46 -- the "
                         "same literal bits as falu2i's mods[7:6]. The two MIXED "
                         "arms are the sharpest test of what 01 and 10 mean "
                         "(PRE_REGISTRATION H3b)." % (kA, kB)))

    # --- secondary scans, pre-registered for the 'srcA-only' refuter --------
    for kA, kB in (("load", "alu"), ("alu", "load")):
        tag = kA[0].upper() + kB[0].upper()
        cs = []
        for v in range(32):
            p, o, s, ib, var = prog_falu2(kA, kB, 0xC0, opflags5=v)
            cs.append(_case("C_falu2_opflags_" + tag, "falu2", "opflags", v, p, o,
                            s, ib.hex(), "byte+5 held at 0xC0", None,
                            {"srcA": kA, "srcB": kB}, variant=var))
        arms.append(_arm("C_falu2_opflags_" + tag, "falu2", "opflags", cs,
                         "falu2.opflags 0..31 DENSE (instruction bits 23:19) "
                         "with srcA=%s, srcB=%s: looks for a second operand-class "
                         "control if byte+5 turns out to describe only srcA."
                         % (kA, kB)))
        cs = []
        for v in range(128):
            p, o, s, ib, var = prog_falu2(kA, kB, 0xC0, ctrl=v)
            cs.append(_case("C_falu2_ctrl_" + tag, "falu2", "ctrl", v, p, o, s,
                            ib.hex(), "byte+5 held at 0xC0", None,
                            {"srcA": kA, "srcB": kB}, variant=var))
        arms.append(_arm("C_falu2_ctrl_" + tag, "falu2", "ctrl", cs,
                         "falu2.ctrl 0..127 DENSE (instruction bits 38:32; bits "
                         "0/1 are the known length selector, EXP-0119) with "
                         "srcA=%s, srcB=%s." % (kA, kB)))
    return arms


def build_store():
    arms = []
    for src, am, tag in (("load", 0x56, "fwd"), ("alu", 0x54, "alu")):
        cs = []
        for v in range(256):
            p, o, s, ib = prog_store(src, v, am)
            cs.append(_case("S_extmode_" + tag, "device_store", "extmode", v, p,
                            o, s, ib.hex(), "data source = %s, addr_mode=0x%02X"
                            % (src, am), None, {"cf": (v >> 6) & 3, "src": src}))
        arms.append(_arm("S_extmode_" + tag, "device_store", "extmode", cs,
                         "device_store.extmode DENSE 0..255 with %s-sourced data. "
                         "EXP-0141 ran the ALU case (accepted {2R, 2R|0xC0}); the "
                         "LOAD-forwarded case is new and is where correspondence "
                         "predicts only 2R|0xC0 survives." % src))
        base_reg = H.R_A if src == "load" else H.R_D
        cs = []
        for v in range(256):
            p, o, s, ib = prog_store(src, 2 * base_reg, v)
            cs.append(_case("S_addrmode_" + tag, "device_store", "addr_mode", v,
                            p, o, s, ib.hex(), "data source = %s" % src, None,
                            {"bit1": (v >> 1) & 1, "src": src}))
        arms.append(_arm("S_addrmode_" + tag, "device_store", "addr_mode", cs,
                         "device_store.addr_mode DENSE 0..255 with %s-sourced "
                         "data: positive-control replication of EXP-0141 H2's "
                         "data-source selector on an independent harness." % src))

    # --- store 4-way: cf x addr_mode x provenance ---------------------------
    cs = []
    for src in ("load", "alu"):
        base_reg = H.R_A if src == "load" else H.R_D
        for am in (0x54, 0x56):
            for cf in CF:
                em = (2 * base_reg) | cf
                p, o, s, ib = prog_store(src, em, am)
                cs.append(_case("S_44", "device_store", "extmode", em, p, o, s,
                                ib.hex(), "src=%s addr_mode=0x%02X cf=0x%02X"
                                % (src, am, cf), None,
                                {"cf": cf >> 6, "addr_mode": am, "src": src,
                                 "data_reg": base_reg}))
    arms.append(_arm("S_44", "device_store", "extmode", cs,
                     "device_store source-type bits x addr_mode bit 1 x operand "
                     "provenance: are the two consumer-side selectors the same "
                     "mechanism or two?"))

    # --- does the store's extmode bit 6 carry register bit 5? ---------------
    cs = []
    for R in (4, 20, 33, 40):
        for cf in CF:
            em = ((2 * R) | cf) & 0xFF
            p, o, s, ib = prog_store("load", em, 0x56, data_reg=R)
            cs.append(_case("S_extmode_highreg", "device_store", "extmode", em, p,
                            o, s, ib.hex(),
                            "data in r%d, extmode=2R|0x%02X" % (R, cf), None,
                            {"data_reg": R, "cf": cf >> 6, "two_r": 2 * R}))
    arms.append(_arm("S_extmode_highreg", "device_store", "extmode", cs,
                     "data registers 4/20/33/40 x the four bit-pair codes. r33 "
                     "and r40 have 2R >= 64, so bit 6 of extmode is REQUIRED by "
                     "the register model and FORBIDDEN by a form model -- the "
                     "store-side analogue of H1_land."))
    return arms


def build_all():
    arms = build_controls() + build_h1() + build_h2() + build_h3_h4() + build_store()
    seen = set()
    for a in arms:
        if a["arm"] in seen:
            raise SystemExit("duplicate arm name %s" % a["arm"])
        seen.add(a["arm"])
    return arms


if __name__ == "__main__":
    import json
    arms = build_all()
    print(json.dumps({"n_arms": len(arms),
                      "n_cases": sum(len(a["cases"]) for a in arms),
                      "arms": [{"arm": a["arm"], "instr": a["instr"],
                                "field": a["field"], "n": len(a["cases"])}
                               for a in arms]}, indent=1))
