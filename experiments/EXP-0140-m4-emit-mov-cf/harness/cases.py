#!/usr/bin/env python3
"""EXP-0140 FROZEN case matrix.

Pure, deterministic, no GPU: `build_cases(mainlens)` returns the complete
ordered list of case descriptors.  `mainlens` supplies each carrier's
`_agc.main` length, re-derived fresh by harness/baseline.py (never assumed);
the frozen contract records the expected values and run.py hard-asserts them.

Every case carries a HOST-COMPUTED oracle (a dict {out_word_index: value}).
For exploratory values inside a dense sweep the oracle is the carrier's own
BASELINE output vector -- i.e. the case tests INERTNESS -- and
`expect_match` is null (no prediction made).  Where a real prediction exists
(`expect_match` True/False) it is pre-registered here, before any gated run.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402
sys.path.insert(0, str(HERE.parents[2] / "tools" / "agx-isa"))
import isadb  # noqa: E402

# --------------------------------------------------------------- constants
UNI_SLOT_OUT, UNI_SLOT_MEM = 0, 1
MAGIC = [0xA1B2C3D4, 0x1E2F3040, 0x55AA33CC, 0x0F1E2D3C]   # u0..u3, bound by run.py
POISON = 7                 # every GPR pre-seeded to this before a MOV test
MOVIMM_TESTVAL = 99
REGMOVE_IMM_K = 85         # uniform_mov immediate-region probe value
REGMOVE_USRC_IMM = 0x80 | REGMOVE_IMM_K

# uniform-register indices that hold our four bound constants.  DERIVED from
# this experiment's own disclosed pilot (work/pilot/pilot2.py, 256-value usrc
# sweep) and matching EXP-0020's independent "byte1 steps by 4" corpus
# observation.  Pre-registered here as a PREDICTION the gated runs test.
USRC_UNIFORM_MAP = {0x18: 0, 0x19: 0, 0x1C: 1, 0x1D: 1,
                     0x20: 2, 0x21: 2, 0x24: 3, 0x25: 3}

# select carriers
SEL_A1 = [0, 1, 2, 3, 4, 5, 6, 7]
SEL_A2 = [3, 90, 4, 91, 5, 92, 100, 101]
SEL_THRESH = 5
SEL_TRUE, SEL_FALSE = 100, 200
PSEL_TRUE, PSEL_FALSE = 111, 222
PSEL_THRESH = 4

# CF carrier inputs
CF_A = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
CF_N = [0, 1, 2, 3, 4, 8, 16, 32]

CARRIER_MAINLEN_EXPECT = {"uni": 300, "dsel5": 46, "gsel4": 32, "cf": 152}
SEL_INSTR_OFF = 0x18       # `sel`  inside dsel5's own compile
PSEL_INSTR_OFF = 0x0A      # `psel` inside gsel4's own compile
SEL_BASE_BODY = (0xC2, 0xA0, 0xC8)
PSEL_BASE_BODY = (0x22, 0xA0, 0xDE)


def _pow2(width):
    return [1 << i for i in range(width)]


def _wide_values(width):
    """Protocol coverage for a field wider than 8 bits: boundaries, every
    power of two, and >=16 asymmetric interior samples."""
    mx = (1 << width) - 1
    vals = [0, 1, 2, mx - 1, mx] + _pow2(width)
    vals += [mx // 3, mx // 7, (mx // 2) ^ 0x5A5, 0x1234 & mx, 0x0F0F & mx,
             0xAAAA & mx, 0x5555 & mx, 0x00FF & mx, 0xFF00 & mx, 0x0FF0 & mx,
             0x1357 & mx, 0x2468 & mx, 0x9E37 & mx, 0x7C15 & mx, 0x3B9A & mx,
             0xC0DE & mx]
    seen, out = set(), []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


# ================================================================ MOV arm
def _seed_all(poison=POISON):
    return [H.mov_imm(j, poison) for j in range(16)]


def _alloc(D, scan=False):
    """Allocate the harness's three role registers (index / control / pad) so
    that none collides with the destination under test, and -- for the
    12-register aliasing scans -- none lies inside the scanned range r0..r11."""
    pool = [r for r in ((15, 14, 13, 12) if scan else (15, 14, 13, 12, 11, 10))
            if r != D]
    return pool[0], pool[1], pool[2]


def _mov_read2(instrs, D, idx, ctrl, mainlen):
    """append: store r_D -> out[0], store r_ctrl -> out[1]."""
    instrs = list(instrs)
    instrs.append(H.mov_imm(idx, 0))
    instrs.append(H.device_store(idx, 0, UNI_SLOT_OUT, data_reg=D))
    instrs.append(H.mov_imm(idx, 1))
    instrs.append(H.device_store(idx, 0, UNI_SLOT_OUT, data_reg=ctrl))
    instrs.append(H.stop())
    return H.build_program(instrs, mainlen)


def _mov_scan(instrs, idx, nscan, mainlen):
    """append: store r_0..r_(nscan-1) -> out[0..nscan-1] using r_idx."""
    instrs = list(instrs)
    for j in range(nscan):
        instrs.append(H.mov_imm(idx, j))
        instrs.append(H.device_store(idx, 0, UNI_SLOT_OUT, data_reg=j))
    instrs.append(H.stop())
    return H.build_program(instrs, mainlen)


def g1_mov_imm_dst(ml):
    cs = []
    for D in range(16):
        idx, ctrl, _ = _alloc(D)
        body = _seed_all() + [H.mov_imm(D, MOVIMM_TESTVAL)]
        prog = _mov_read2(body, D, idx, ctrl, ml)
        cs.append(dict(group="mov_imm.dst", instr="mov_imm", field="dst", value=D,
                        carrier="uni", dispatch=(1, 1), prog=prog,
                        bytes=H.mov_imm(D, MOVIMM_TESTVAL).hex(),
                        oracle={0: MOVIMM_TESTVAL, 1: POISON}, expect_match=True,
                        mode="int", note="dst selects r_D; ctrl register must stay poisoned"))
    for D in (0, 5, 10, 15):
        idx, _, _ = _alloc(D, scan=True)
        body = _seed_all() + [H.mov_imm(D, MOVIMM_TESTVAL)]
        prog = _mov_scan(body, idx, 12, ml)
        orc = {j: (MOVIMM_TESTVAL if j == D else POISON) for j in range(12)}
        cs.append(dict(group="mov_imm.dst.alias_scan", instr="mov_imm", field="dst", value=D,
                        carrier="uni", dispatch=(1, 1), prog=prog,
                        bytes=H.mov_imm(D, MOVIMM_TESTVAL).hex(),
                        oracle=orc, expect_match=True, mode="int",
                        note="12-register aliasing scan: only r_D may change"))
    # pre-registered falsifier: a CORRECT construction judged against a bogus oracle
    D = 4
    idx, ctrl, _ = _alloc(D)
    prog = _mov_read2(_seed_all() + [H.mov_imm(D, MOVIMM_TESTVAL)], D, idx, ctrl, ml)
    cs.append(dict(group="mov_imm.dst.falsifier", instr="mov_imm", field="dst", value=D,
                    carrier="uni", dispatch=(1, 1), prog=prog,
                    bytes=H.mov_imm(D, MOVIMM_TESTVAL).hex(),
                    oracle={0: MOVIMM_TESTVAL + 1, 1: POISON}, expect_match=False, mode="int",
                    note="FALSIFIER: correct program, deliberately unreachable oracle"))
    # pre-registered boundary re-check (EXP-0128's imm>=128 silent zero), dst still under test
    D = 6
    idx, ctrl, _ = _alloc(D)
    prog = _mov_read2(_seed_all() + [H.mov_imm_raw(D, 200)], D, idx, ctrl, ml)
    cs.append(dict(group="mov_imm.dst.imm_boundary", instr="mov_imm", field="dst", value=D,
                    carrier="uni", dispatch=(1, 1), prog=prog,
                    bytes=H.mov_imm_raw(D, 200).hex(),
                    oracle={0: 0, 1: POISON}, expect_match=True, mode="int",
                    note="imm=200 predicted to SILENTLY ZERO r_D (EXP-0128), dst still selects r_D"))
    return cs


def g2_get_sr(ml):
    """grid=8/tg=8: r0 = thread_position_in_grid.x, then out[r0] = r0.
    A working SR read gives out == [0..7]; a no-op leaves the poison 7 in r0
    so all eight lanes store 7 into out[7]."""
    cs = []
    baseline_oracle = {i: i for i in range(8)}

    def mk(field, value, form, dpw, dpm, sr=0xA0, note="", expect=None, oracle=None):
        instrs = [H.mov_imm(0, POISON),
                  H.get_sr_tid(dst=0, form=form, sr_sel=sr, dp_width=dpw, dp_marker=dpm),
                  H.device_store(0, 0, UNI_SLOT_OUT, data_reg=0), H.stop()]
        prog = H.build_program(instrs, ml)
        return dict(group="get_sr." + field, instr="get_sr", field=field, value=value,
                    carrier="uni", dispatch=(8, 8), prog=prog,
                    bytes=H.get_sr_tid(dst=0, form=form, sr_sel=sr, dp_width=dpw,
                                        dp_marker=dpm).hex(),
                    oracle=(baseline_oracle if oracle is None else oracle),
                    expect_match=expect, mode="int", note=note)

    for f in (0, 1):
        cs.append(mk("form", f, f, 0x10, 6,
                      expect=(True if f == 1 else None),
                      note=("compiler-natural value" if f == 1 else "exploratory (inertness test)")))
    for w in range(256):
        cs.append(mk("dp_width", w, 1, w, 6,
                      expect=(True if w == 0x10 else None),
                      note=("compiler-natural value" if w == 0x10 else "exploratory (inertness test)")))
    for m in range(32):
        cs.append(mk("dp_marker", m, 1, 0x10, m,
                      expect=(True if m == 6 else None),
                      note=("compiler-natural value" if m == 6 else "exploratory (inertness test)")))
    # pre-registered falsifier: sr_sel in the immediate region -> r0 = 0 in every
    # lane, so all eight lanes store 0 into out[0]; out != [0..7].
    cs.append(mk("sr_sel_falsifier", 0x00, 1, 0x10, 6, sr=0x00, expect=False,
                  note="FALSIFIER: sr_sel=0x00 predicted NOT to yield the per-lane tid vector"))
    return cs


def g3_regmove(ml):
    """The four bytes of the 0x?B family, swept independently.  Six bytes of
    inert `mov_imm(pad,0)` follow the test instruction so that a value which
    the hardware decodes as an 8- or 10-byte instruction consumes only
    padding and never the following store's leader."""
    cs = []

    def mk(field, value, D, b1, b2, b3, oracle, expect, note, scan=False):
        idx, ctrl, pad = _alloc(D, scan=scan)
        instrs = _seed_all() + [H.regmove(D, b1, b2, b3)] + [H.mov_imm(pad, 0)] * 3
        prog = (_mov_scan(instrs, idx, 12, ml) if scan
                else _mov_read2(instrs, D, idx, ctrl, ml))
        return dict(group="regmove." + field, instr="regmove", field=field, value=value,
                    carrier="uni", dispatch=(1, 1), prog=prog,
                    bytes=H.regmove(D, b1, b2, b3).hex(), oracle=oracle,
                    expect_match=expect, mode="int", note=note)

    # (a) dst nibble
    for D in range(16):
        cs.append(mk("dst", D, D, REGMOVE_USRC_IMM, 0x01, 0x08,
                      {0: REGMOVE_IMM_K, 1: POISON}, True,
                      "dst nibble selects r_D; usrc in the immediate region"))
    # (b) byte+1 = usrc / src_reg+src_flag
    for U in range(256):
        if U >= 0x80:
            orc, exp, nt = {0: U & 0x7F, 1: POISON}, True, "immediate region: value = usrc & 0x7f"
        elif U in USRC_UNIFORM_MAP:
            orc = {0: H.i32(MAGIC[USRC_UNIFORM_MAP[U]]), 1: POISON}
            exp, nt = True, "uniform register holding our bound constant u%d" % USRC_UNIFORM_MAP[U]
        else:
            orc, exp, nt = {0: POISON, 1: POISON}, None, "exploratory (inertness test)"
        cs.append(mk("usrc", U, 3, U, 0x01, 0x08, orc, exp, nt))
    # (c) byte+2 = form / src_class / subform
    for F in range(256):
        if F == 0x01:
            orc, exp, nt = {0: REGMOVE_IMM_K, 1: POISON}, True, "the only value known to move"
        else:
            orc, exp, nt = {0: POISON, 1: POISON}, None, "exploratory (inertness test)"
        cs.append(mk("byte2", F, 3, REGMOVE_USRC_IMM, F, 0x08, orc, exp, nt))
    # (d) byte+3 = op_desc
    for P in range(256):
        if P == 0x08:
            orc, exp, nt = {0: REGMOVE_IMM_K, 1: POISON}, True, "the only value known to move"
        else:
            orc, exp, nt = {0: POISON, 1: POISON}, None, "exploratory (inertness test)"
        cs.append(mk("byte3", P, 3, REGMOVE_USRC_IMM, 0x01, P, orc, exp, nt))
    # (e) the five db.json descriptor discriminators, named
    for nm, b2 in (("reg_move_c0", 0x00), ("reg_move_c1", 0x01), ("reg_move_c2var", 0x02),
                   ("reg_move_c9", 0x09), ("reg_move_cb", 0x0B)):
        cs.append(mk("descriptor_" + nm, b2, 3, REGMOVE_USRC_IMM, b2, 0x08,
                      {0: REGMOVE_IMM_K, 1: POISON}, (b2 == 0x01),
                      "db.json descriptor %s: predicted to move ONLY for byte+2=0x01" % nm))
    # (f) op_desc bit2 redirect (EXP-0087) -- 12-register scan
    for P in (0x08, 0x0C):
        cs.append(mk("opdesc_redirect_scan", P, 3, REGMOVE_USRC_IMM, 0x01, P,
                      {j: (REGMOVE_IMM_K if (j == 3 and P == 0x08) else POISON)
                       for j in range(12)},
                      (P == 0x08),
                      "12-register scan; bit2 set predicted to redirect the write off r3",
                      scan=True))
    # (g) falsifier
    cs.append(mk("falsifier", 0x00, 3, REGMOVE_USRC_IMM, 0x00, 0x08,
                  {0: REGMOVE_IMM_K, 1: POISON}, False,
                  "FALSIFIER: byte+2=0x00 predicted NOT to move the value"))
    return cs


# ============================================================= select arm
def _sel_oracle(a_vec, true_v, false_v):
    return {i: (true_v if a_vec[i] > SEL_THRESH else false_v) for i in range(8)}


def g4_sel(ml):
    cs = []
    for vec_name, a_vec in (("A1", SEL_A1), ("A2", SEL_A2)):
        base = _sel_oracle(a_vec, SEL_TRUE, SEL_FALSE)
        for bi in (1, 2, 3):
            for v in range(256):
                body = list(SEL_BASE_BODY)
                body[bi - 1] = v
                if bi == 3 and v >= 128:
                    orc, exp = _sel_oracle(a_vec, SEL_TRUE, v), True
                    nt = "byte+3 predicted to be the FALSE-arm 8-bit immediate (value = byte)"
                elif bi == 3:
                    orc, exp = _sel_oracle(a_vec, SEL_TRUE, 0), True
                    nt = "byte+3 < 0x80 predicted to read an unwritten operand -> 0"
                else:
                    orc, exp, nt = base, None, "exploratory (inertness test)"
                cs.append(dict(group="sel.body.b%d" % bi, instr="sel", field="body",
                                value=(v << (8 * (bi - 1))), carrier="dsel5",
                                dispatch=(8, 8), inputs=vec_name,
                                patch=(SEL_INSTR_OFF + bi, v),
                                bytes=bytes([0x16] + body).hex(), oracle=orc,
                                expect_match=exp, mode="int",
                                note="%s [a=%s]" % (nt, vec_name)))
        # whole-body boundaries + powers of two
        for bodyv in _wide_values(24):
            b = [(bodyv >> 0) & 0xFF, (bodyv >> 8) & 0xFF, (bodyv >> 16) & 0xFF]
            cs.append(dict(group="sel.body.wide", instr="sel", field="body", value=bodyv,
                            carrier="dsel5", dispatch=(8, 8), inputs=vec_name,
                            patch3=(SEL_INSTR_OFF + 1, bytes(b)),
                            bytes=bytes([0x16] + b).hex(), oracle=base, expect_match=None,
                            mode="int", note="whole-field boundary/power-of-two sample [a=%s]" % vec_name))
        cs.append(dict(group="sel.body.baseline", instr="sel", field="body",
                        value=(SEL_BASE_BODY[0] | (SEL_BASE_BODY[1] << 8) | (SEL_BASE_BODY[2] << 16)),
                        carrier="dsel5", dispatch=(8, 8), inputs=vec_name,
                        patch3=(SEL_INSTR_OFF + 1, bytes(SEL_BASE_BODY)),
                        bytes=bytes([0x16] + list(SEL_BASE_BODY)).hex(), oracle=base,
                        expect_match=True, mode="int", note="unmutated baseline [a=%s]" % vec_name))
    cs.append(dict(group="sel.body.falsifier", instr="sel", field="body", value=0,
                    carrier="dsel5", dispatch=(8, 8), inputs="A1",
                    patch3=(SEL_INSTR_OFF + 1, bytes(SEL_BASE_BODY)),
                    bytes=bytes([0x16] + list(SEL_BASE_BODY)).hex(),
                    oracle={i: 12345 for i in range(8)}, expect_match=False, mode="int",
                    note="FALSIFIER: unmutated baseline judged against an unreachable oracle"))
    return cs


def _psel_oracle(true_v, false_v, grid):
    return {i: (true_v if i < PSEL_THRESH else false_v) for i in range(grid)}


def g5_psel(ml):
    cs = []
    for grid in (8, 4):
        base = _psel_oracle(PSEL_TRUE, PSEL_FALSE, grid)
        for bi, fname in ((1, "flag"), (2, "mode"), (3, "sel")):
            for v in range(256):
                body = list(PSEL_BASE_BODY)
                body[bi - 1] = v
                if bi == 3 and v >= 128:
                    orc, exp = _psel_oracle(PSEL_TRUE, v, grid), True
                    nt = "byte+3 predicted to be the FALSE-arm 8-bit immediate (value = byte)"
                elif bi == 3:
                    orc, exp = _psel_oracle(PSEL_TRUE, 0, grid), True
                    nt = "byte+3 < 0x80 predicted to read an unwritten operand -> 0"
                else:
                    orc, exp, nt = base, None, "exploratory (inertness test)"
                cs.append(dict(group="psel.%s" % fname, instr="psel", field=fname, value=v,
                                carrier="gsel4", dispatch=(grid, grid),
                                patch=(PSEL_INSTR_OFF + bi, v),
                                bytes=bytes([0x05] + body).hex(), oracle=orc,
                                expect_match=exp, mode="int",
                                note="%s [grid=%d]" % (nt, grid)))
        cs.append(dict(group="psel.baseline", instr="psel", field="flag", value=PSEL_BASE_BODY[0],
                        carrier="gsel4", dispatch=(grid, grid),
                        patch3=(PSEL_INSTR_OFF + 1, bytes(PSEL_BASE_BODY)),
                        bytes=bytes([0x05] + list(PSEL_BASE_BODY)).hex(), oracle=base,
                        expect_match=True, mode="int", note="unmutated baseline [grid=%d]" % grid))
    cs.append(dict(group="psel.falsifier", instr="psel", field="flag", value=PSEL_BASE_BODY[0],
                    carrier="gsel4", dispatch=(8, 8),
                    patch3=(PSEL_INSTR_OFF + 1, bytes(PSEL_BASE_BODY)),
                    bytes=bytes([0x05] + list(PSEL_BASE_BODY)).hex(),
                    oracle={i: 999 for i in range(8)}, expect_match=False, mode="int",
                    note="FALSIFIER: unmutated baseline judged against an unreachable oracle"))
    return cs


# ================================================================= CF arm
def cf_baseline_oracle():
    return {i: H.cf_oracle(CF_A[i], CF_N[i]) for i in range(8)}


CF_SWEEPS = [
    # (order, sequence index, mnemonic, field, width)  -- dispatch priority order
    ("if_push", H.CF_IDX["if_push"], "if_push", "scope", 8),
    ("if_push", H.CF_IDX["if_push"], "if_push", "scope_kind", 8),
    ("if_push_pred", H.CF_IDX["if_push_pred"], "if_push_pred", "scope", 8),
    ("if_push_pred", H.CF_IDX["if_push_pred"], "if_push_pred", "level", 8),
    ("jump", H.CF_IDX["jump"], "jump", "branch_ctrl", 8),
    ("jump", H.CF_IDX["jump"], "jump", "link", 8),
    ("jump_cond", H.CF_IDX["jump_cond"], "jump_cond", "cf_scope", 8),
    ("jump_cond", H.CF_IDX["jump_cond"], "jump_cond", "reserved", 8),
    ("pop_reconverge", H.CF_IDX["pop_reconverge_a"], "pop_reconverge", "scope", 8),
    ("pop_reconverge", H.CF_IDX["pop_reconverge_a"], "pop_reconverge", "scope_kind", 8),
    ("pop_reconverge", H.CF_IDX["pop_reconverge_b"], "pop_reconverge", "scope", 8),
    ("pop_reconverge", H.CF_IDX["pop_reconverge_b"], "pop_reconverge", "scope_kind", 8),
    ("ret", H.CF_IDX["ret"], "ret", "linkmode", 8),
    ("ret", H.CF_IDX["ret"], "ret", "scoreboard", 8),
]

CF_NATURAL = {("if_push", "scope"): 0x54, ("if_push", "scope_kind"): 0x1A,
              ("if_push_pred", "scope"): 0x54, ("if_push_pred", "level"): 1,
              ("jump", "branch_ctrl"): 0x54, ("jump", "link"): 0x00,
              ("jump_cond", "cf_scope"): 0x54, ("jump_cond", "reserved"): 0x00,
              ("pop_reconverge", "scope"): 0x04, ("pop_reconverge", "scope_kind"): None,
              ("ret", "linkmode"): 0x04, ("ret", "scoreboard"): 0x22}


def cf_jump_cond_offsets():
    """A STRUCTURED, bounded `jump_cond.offset` set -- never a dense 48-bit
    sweep.  EXP-0115 measured branch reach on `jump`, NOT on `jump_cond`, so
    that range does not transfer; and an arbitrary displacement is the exact
    construction that hung the GPU in EXP-0128.  The set is: every valid
    instruction START offset in the frozen skeleton expressed relative to the
    jump_cond's own address, plus small misalignments around the natural
    target, plus a handful of far probes."""
    prog = H.cf_program()
    starts, off = [], 0
    while off < len(prog):
        try:
            _, L = isadb.decode_one(prog, off)
        except ValueError:
            break
        starts.append(off)
        off += L
    jc_addr = starts[H.CF_IDX["jump_cond"]]
    vals = []
    for s in starts:
        vals.append(s - jc_addr)
    natural = 0x40
    for d in (-4, -3, -2, -1, 1, 2, 3, 4):
        vals.append(natural + d)
    vals += [0, 1, 2, -1, -2, 0x80, 0x100, -0x40]
    seen, out = set(), []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return jc_addr, starts, out


def g6_cf(ml):
    cs = []
    base = cf_baseline_oracle()
    cs.append(dict(group="cf.baseline", instr="cf_skeleton", field="-", value=0,
                    carrier="cf", dispatch=(8, 8), prog=H.cf_program(),
                    bytes="", oracle=base, expect_match=True, mode="float",
                    note="unmutated EXP-0090/EXP-0112 CF skeleton", arm="cf.baseline"))
    cs.append(dict(group="cf.falsifier", instr="cf_skeleton", field="-", value=0,
                    carrier="cf", dispatch=(8, 8), prog=H.cf_program(),
                    bytes="", oracle={i: 1.0 for i in range(8)}, expect_match=False,
                    mode="float", note="FALSIFIER: unmutated skeleton, unreachable oracle",
                    arm="cf.baseline"))
    for arm, seqi, mnem, field, width in CF_SWEEPS:
        nat = CF_NATURAL.get((mnem, field))
        for v in range(1 << width):
            seq = H.cf_sequence()
            prog = H.cf_program(override=(seqi, field, v))
            testbytes = isadb.assemble(seq[seqi][0], dict(seq[seqi][1], **{field: v}))
            cs.append(dict(group="%s.%s@%d" % (mnem, field, seqi), instr=mnem, field=field,
                            value=v, carrier="cf", dispatch=(8, 8), prog=prog,
                            bytes=testbytes.hex(), oracle=base,
                            expect_match=(True if (nat is not None and v == nat) else None),
                            mode="float", arm="%s.%s@%d" % (arm, field, seqi),
                            note=("compiler-natural value" if (nat is not None and v == nat)
                                  else "exploratory (inertness test)")))
    # pop_reconverge.reserved (16 bits) -- protocol wide-field coverage
    for seqi, tag in ((H.CF_IDX["pop_reconverge_a"], "a"), (H.CF_IDX["pop_reconverge_b"], "b")):
        for v in _wide_values(16):
            seq = H.cf_sequence()
            prog = H.cf_program(override=(seqi, "reserved", v))
            testbytes = isadb.assemble("pop_reconverge", dict(seq[seqi][1], reserved=v))
            cs.append(dict(group="pop_reconverge.reserved@%d" % seqi, instr="pop_reconverge",
                            field="reserved", value=v, carrier="cf", dispatch=(8, 8),
                            prog=prog, bytes=testbytes.hex(), oracle=base,
                            expect_match=(True if v == 0 else None), mode="float",
                            arm="pop_reconverge.reserved@%d" % seqi,
                            note=("compiler-natural value" if v == 0
                                  else "exploratory (inertness test)")))
    # jump_cond.offset -- structured, bounded
    jc_addr, starts, offs = cf_jump_cond_offsets()
    for v in offs:
        seq = H.cf_sequence()
        prog = H.cf_program(override=(H.CF_IDX["jump_cond"], "offset",
                                       v & ((1 << 48) - 1)))
        testbytes = isadb.assemble("jump_cond", dict(seq[H.CF_IDX["jump_cond"]][1],
                                                       offset=v & ((1 << 48) - 1)))
        cs.append(dict(group="jump_cond.offset", instr="jump_cond", field="offset", value=v,
                        carrier="cf", dispatch=(8, 8), prog=prog, bytes=testbytes.hex(),
                        oracle=base, expect_match=(True if v == 0x40 else None),
                        mode="float", arm="jump_cond.offset",
                        note=("compiler-natural value (target +0x%x)" % (jc_addr + 0x40)
                              if v == 0x40 else
                              "exploratory: target = 0x%x %s an instruction start"
                              % ((jc_addr + v) & 0xFFFF,
                                 "IS" if (jc_addr + v) in starts else "is NOT"))))
    return cs


# ================================================================= assembly
def build_cases(mainlens):
    cs = []
    cs += g1_mov_imm_dst(mainlens["uni"])
    cs += g2_get_sr(mainlens["uni"])
    cs += g3_regmove(mainlens["uni"])
    cs += g4_sel(mainlens["dsel5"])
    cs += g5_psel(mainlens["gsel4"])
    cs += g6_cf(mainlens["cf"])
    for i, c in enumerate(cs):
        c["i"] = i
        c.setdefault("arm", c["group"])
        if "prog" in c and isinstance(c["prog"], (bytes, bytearray)):
            c["prog"] = bytes(c["prog"])
    return cs


if __name__ == "__main__":
    import json
    cs = build_cases(CARRIER_MAINLEN_EXPECT)
    from collections import Counter
    print("total cases:", len(cs))
    for g, n in Counter(c["group"] for c in cs).most_common():
        print("  %-32s %d" % (g, n))
