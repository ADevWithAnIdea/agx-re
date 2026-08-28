#!/usr/bin/env python3
"""EXP-0113 case matrix -- register-file model (H1/H2/H3).

Every case = ONE hand-built AGX program (concat of isa_helpers.py builders,
each a tools/agx-isa isadb.assemble() call, OR -- for the H1_LOADFWD group
only, see below -- a splice grafted onto a REAL compiled instance's OTHER,
untouched instructions), padded to a carrier's own compiled length, spliced
over that carrier's compiled `_agc.main` (offset 0), executed on real M4
hardware via tools/agxtest, and compared to an independently computed
oracle -- never derived from an observed output.

## Group summary (see PRE_REGISTRATION.md for the full falsifier table)

- SEED_CHECK: sanity (3 cases). Carrier: kernels/carrier.metal.
- H1_ALIAS_RECONFIRM: independent re-confirmation of EXP-0099/EXP-0105's
  own falu2/falu2i srcA_reg/srcB_reg low-6-bit aliasing finding (2 cases,
  no FTZ risk -- V_LOW=30.0 is a normal float). Carrier: carrier.metal.
- H1_CTRL_BITS_4_6: finishes EXP-0105's own disclosed gap (ctrl bits 4-6
  of falu2's 7-bit `ctrl` field, UNTESTED there), crossed against reg=3
  (low) and reg=67 (high field value) (6 cases). Carrier: carrier.metal.
- H1_LOADFWD: THE decisive new H1 contribution. This experiment's own
  pilot phase (PROGRESS.md Milestone 2) discovered that a device_load
  whose `dst_lo`/`dst_ext9` fields are set to encode a candidate register
  R (dst = dst_lo | (dst_ext9<<2)), immediately followed by a PLAIN-8-bit-
  field consumer (iminmax's `srcA`) ALSO set to R, appears to read the
  loaded value correctly across an enormous R range -- INCLUDING values
  (96-127) already proven, by an independent path (get_sr+device_store,
  EXP-0092), to be OUTSIDE the physical 96-GPR file. Two decisive follow-
  up probes (both reproduced here under gate) show this apparent success
  is NOT genuine persistent register-file access: (a) a SECOND, later,
  independently-issued consumer reading the SAME nominal R gets 0, not
  the value (persistence fails); (b) merely ADDING that second consumer
  changes the FIRST read's own result too (even at R=7, an ordinary low
  register) -- i.e. the apparent "read" is sensitive to overall program
  SHAPE, not a stable, addressable location. This generalizes EXP-0105's
  own flagged, unexplained "iminmax splice has zero effect" anomaly:
  the mechanism is some kind of fragile, adjacency/shape-dependent
  pipeline forwarding, not indexed GPR access. Carrier:
  kernels/loadfwd_carrier.metal (an independently compiled, functionally
  verified `int a=...,b=...; out=max(a,b);`-shaped kernel with extra dead
  arithmetic for spare body length -- see that file's own header).
  CLEAN-ROOM NOTE: every byte executed is either produced by
  isadb.assemble() from named fields, or is an UNTOUCHED byte range of
  OUR OWN compiled kernel (loadfwd_carrier.metal) -- this experiment
  never inspects or reuses any byte from an Apple binary.
- H2_REGMOVE_C9: is byte0=0x2b (EXP-0087's own "undecoded" instance,
  hex `2b0009c0`) a real GPR move? Statically, `isadb.assemble(
  'reg_move_c9', {dst:2,src_reg:0,src_flag:0,src_class:0,op_desc:0xC0})`
  reproduces those exact 4 bytes (verified in analysis.py) -- so db.json's
  OWN field table already covers this shape; tools/agx-isa's disassembler
  reports it "undecoded" only because isadb.py's instr_length() byte0=
  0xNb length rule has no branch for byte+2 low-nibble==9 (a narrower,
  disclosed length-rule gap, not a wrong field mapping -- see RESULTS.md).
  This group extends EXP-0101's own producer-independence + register-pair
  quantization methodology (originally run on reg_move_c1/byte+2=0x21) to
  THIS exact byte0=0x2b-decoding family (10 cases). Carrier: carrier.metal.
- H3_BUFFER_SIGNATURE: does reg_move_c1's (src_flag=0) `src_reg` address a
  slot that shifts with the kernel's own bound-buffer count? Three carrier
  variants (1/2/3 float* buffers), reg_move_c1 src_reg swept at {0,2,4,8}
  each (12 cases). Carriers: kernels/carrier_buf{1,2,3}.metal.

Oracle `kind`: "f32" (IEEE-754 float32, falu2/falu2i groups) or "u32" (raw
little-endian uint32, everything else -- reg_move/LOADFWD groups are never
float-interpreted, sidestepping this hardware's confirmed flush-to-zero-on-
denormal behavior for float ALU ops, see PROGRESS.md Milestone 1).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / "tools" / "agx-isa"))
import isadb  # noqa: E402

CARRIER_LEN = 170          # kernels/carrier.metal (byte-identical to EXP-0099/0105)
LOADFWD_CARRIER_LEN = 154  # kernels/loadfwd_carrier.metal
BUF1_CARRIER_LEN = 36      # kernels/carrier_buf1.metal
BUF2_CARRIER_LEN = 42      # kernels/carrier_buf2.metal
BUF3_CARRIER_LEN = 62      # kernels/carrier_buf3.metal

R_IDX = H.R_IDX                  # 15
R_UNWRITTEN = H.R_UNWRITTEN      # 14
R_LOW = H.R_LOW                  # 3
R_HIGH_FIELD = H.R_HIGH_FIELD    # 67

V_LOW_FLOAT = H.imm_value(42.5)  # -> 30.0, ALU-seeded fixed point (EXP-0090/EXP-0099/EXP-0105 convention)
K_ZERO = H.imm_value(0.0)        # -> 0.0

DEFAULT_DISPATCH = {"grid": 1, "tg": 1}
LOADFWD_DISPATCH = {"grid": 4, "tg": 4}


def _f32(v):
    return {"kind": "f32", "value": v}


def _u32(v):
    return {"kind": "u32", "value": v & 0xFFFFFFFF}


# ---------------------------------------------------------------------------
# SEED_CHECK / H1_ALIAS_RECONFIRM / H1_CTRL_BITS_4_6 -- all on carrier.metal
# ---------------------------------------------------------------------------
def _idx0():
    return [H.mov_imm(R_IDX, 0)]


def _store_word(idx_off, data_reg):
    return [H.device_store(R_IDX, idx_off, 0, data_reg, extmode=(data_reg << 1) & 0xFF)]


def _prog(instrs):
    body = b"".join(instrs) + H.stop()
    return H.build_program([body], CARRIER_LEN)


def _case(i, name, group, instrs, oracle_words, notes, expect_match=None, dispatch=None,
          carrier="carrier.metal", carrier_len=CARRIER_LEN, base_slots=None):
    if base_slots is None:
        hexbytes = _prog(instrs)
    else:
        body = b"".join(instrs) + H.stop()
        hexbytes = H.build_program([body], carrier_len)
    H.assert_round_trip(hexbytes)
    return {
        "i": i, "name": name, "group": group,
        "hex": hexbytes.hex(),
        "carrier": carrier,
        "oracle": {str(k): v for k, v in oracle_words.items()},
        "expect_match": expect_match,
        "notes": notes,
        "dispatch": dict(DEFAULT_DISPATCH if dispatch is None else dispatch),
    }


def build_cases():
    cs = []
    i = 0

    def add(name, group, instrs, oracle_words, notes, expect_match=None, dispatch=None,
             carrier="carrier.metal", carrier_len=CARRIER_LEN):
        nonlocal i
        cs.append(_case(i, name, group, instrs, oracle_words, notes, expect_match, dispatch,
                         carrier, carrier_len, base_slots=True))
        i += 1

    def seed_r3():
        return _idx0() + [H.falu2i_raw(R_LOW, R_UNWRITTEN, V_LOW_FLOAT, opflags4=1)]

    # ------------------------------------------------------------------
    # SEED_CHECK
    # ------------------------------------------------------------------
    add("control_r3_falu2i", "SEED_CHECK",
        seed_r3() + [H.falu2i_raw(5, R_LOW, 0.0, opflags4=1)] + _store_word(0, 5),
        {0: _f32(V_LOW_FLOAT)},
        "Seed r3=30.0 via falu2i(srcA=UNWRITTEN,K=30.0). Read it back via "
        "falu2i(srcA_reg=3,K=0.0). Expect 30.0 (r3+0.0).", expect_match=True)

    add("control_unwritten_falu2i", "SEED_CHECK",
        _idx0() + [H.falu2i_raw(5, R_UNWRITTEN, 0.0, opflags4=1)] + _store_word(0, 5),
        {0: _f32(0.0)},
        "srcA_reg=14 (R_UNWRITTEN, never written by ANY case in this "
        "matrix). Re-confirms EXP-0087 MOVE-04's 'unwritten GPR reads "
        "exactly 0.0' for THIS harness/carrier, independently.", expect_match=True)

    add("positive_control_deliberate_mismatch", "SEED_CHECK",
        seed_r3() + [H.falu2i_raw(5, R_LOW, 0.0, opflags4=1)] + _store_word(0, 5),
        {0: _f32(999.0)},
        "Same construction as control_r3_falu2i but an UNREACHABLE oracle "
        "(30.0 != 999.0) -- proves match-detection actually detects "
        "mismatch, not a rubber stamp.", expect_match=False)

    # ------------------------------------------------------------------
    # H1_ALIAS_RECONFIRM -- independent re-confirmation (no FTZ risk)
    # ------------------------------------------------------------------
    add("falu2i_srca_high67_reconfirm", "H1_ALIAS_RECONFIRM",
        seed_r3() + [H.falu2i_raw(5, R_HIGH_FIELD, 0.0, opflags4=1)] + _store_word(0, 5),
        {0: _f32(V_LOW_FLOAT)},
        "Independent re-confirmation of EXP-0099/EXP-0105: srcA_reg field "
        "value 67 (low6=3, r67 NEVER written) reads r3's seeded 30.0, not "
        "a genuinely-unwritten r67's 0.0.", expect_match=True)

    add("falu2_srcb_high67_reconfirm", "H1_ALIAS_RECONFIRM",
        seed_r3() + [H.falu2_raw(5, R_UNWRITTEN, R_HIGH_FIELD, opflags5=0)] + _store_word(0, 5),
        {0: _f32(V_LOW_FLOAT)},
        "Symmetric test on falu2's OTHER packed field (srcB_reg, bits "
        "25-31) via the register-register form: srcB field=67 (low6=3) "
        "reads r3's 30.0 (srcA=UNWRITTEN contributes 0). Extends the "
        "aliasing finding to srcB by independent construction.", expect_match=True)

    # ------------------------------------------------------------------
    # H1_CTRL_BITS_4_6 -- finishes EXP-0105's disclosed gap
    # ------------------------------------------------------------------
    def ctrl_case(name, reg_field, ctrl_bit, note):
        instrs = seed_r3() + [H.falu2_raw(
            5, reg_field, R_UNWRITTEN, opflags5=0, mod_hi4=0, ctrl=(1 << ctrl_bit))]
        oracle = 0.0 if reg_field == R_HIGH_FIELD else V_LOW_FLOAT
        add(name, "H1_CTRL_BITS_4_6", instrs + _store_word(0, 5), {0: _f32(oracle)}, note)

    for bit in (4, 5, 6):
        ctrl_case("ctrl_low_bit%d" % bit, R_LOW, bit,
                   "@ reg=3: candidate ctrl bit%d (instr bit%d), the last "
                   "3 of falu2's 7-bit ctrl field EXP-0105 left UNTESTED. "
                   "Oracle=30.0 is the 'still inert' baseline." % (bit, 32 + bit))
        ctrl_case("ctrl_high_bit%d" % bit, R_HIGH_FIELD, bit,
                   "@ reg=67 (field value): does ctrl bit%d UNLOCK real "
                   "high addressing (oracle=0.0, r67 genuinely unwritten) "
                   "vs staying aliased to r3 (would read 30.0, a "
                   "MISMATCH against this oracle -- the EXP-0105 "
                   "convention)?" % bit)

    # ------------------------------------------------------------------
    # H1_LOADFWD -- device_load-fed plain-8-bit-field consumer (iminmax)
    # ------------------------------------------------------------------
    LOADFWD_A = [1234, 5678, 9, 10]

    def loadfwd_prog(instrs_bytes):
        body = instrs_bytes + H.stop()
        return H.build_program([body], LOADFWD_CARRIER_LEN, pad_dst=13)

    def add_loadfwd(name, instrs, oracle_words, notes, expect_match=None):
        nonlocal i
        hexbytes = loadfwd_prog(instrs)
        H.assert_round_trip(hexbytes)
        cs.append({
            "i": i, "name": name, "group": "H1_LOADFWD", "hex": hexbytes.hex(),
            "carrier": "loadfwd_carrier.metal",
            "oracle": {str(k): v for k, v in oracle_words.items()},
            "expect_match": expect_match, "notes": notes,
            "dispatch": dict(LOADFWD_DISPATCH),
        })
        i += 1

    def loadfwd_singlehop(R):
        return (H.get_sr_raw(1, 0xA0) + H.device_load_a(R) + H.device_load_b()
                + H.loadfwd_iminmax(R) + H.loadfwd_store(2, idx_off=0))

    SINGLEHOP_R = (5, 7, 15, 16, 32, 63, 67, 90, 96, 127)
    SINGLEHOP_EXPECT_SUCCESS = {5, 7, 16, 32, 63, 67, 96, 127}  # per pilot (PROGRESS.md M2)
    for R in SINGLEHOP_R:
        oracle = {k: _u32(v) for k, v in enumerate(LOADFWD_A)}
        expect = R in SINGLEHOP_EXPECT_SUCCESS
        add_loadfwd("loadfwd_singlehop_r%d" % R, loadfwd_singlehop(R), oracle,
                    "device_load(dst_lo|dst_ext9<<2 == %d) -> iminmax(srcA=%d) "
                    "-> store, single hop, gid-indexed 4-thread dispatch. Oracle "
                    "= a[] exactly (identity via max(a,0), b buffer all-zero). "
                    "Pilot-phase observation (PROGRESS.md M2): %s." %
                    (R, R, "MATCHES a[]" if expect else "reads 0 (does NOT "
                     "match a[]) -- an unexplained exception in an otherwise-"
                     "succeeding range"),
                    expect_match=expect)

    # Persistence test: a SECOND, later, independent consumer reading the
    # SAME nominal R -- does the apparent single-hop success survive?
    def loadfwd_persist(R):
        return (H.get_sr_raw(1, 0xA0) + H.device_load_a(R) + H.device_load_b()
                + H.loadfwd_iminmax(R) + H.loadfwd_store(2, idx_off=0)
                + H.loadfwd_iminmax(R) + H.loadfwd_store(2, idx_off=4))

    add_loadfwd("loadfwd_persist_r67", loadfwd_persist(67),
                {k: _u32(v) for k, v in enumerate(LOADFWD_A)} |
                {k + 4: _u32(v) for k, v in enumerate(LOADFWD_A)},
                "R=67 (a single-hop SUCCESS point). word0-3 = first "
                "consumer+store (predict MATCH, replicating singlehop_r67); "
                "word4-7 = a SECOND, later, independently-issued iminmax+store "
                "reading srcA=67 AGAIN (predict MATCH if r67 is a genuine, "
                "persistent GPR; predict MISMATCH/0 if the first success was "
                "ephemeral pipeline forwarding). Pilot observation: word0-3 "
                "MATCH, word4-7 read exactly 0 (persistence FAILS).",
                expect_match=None)

    add_loadfwd("loadfwd_persist_r7", loadfwd_persist(7),
                {k: _u32(v) for k, v in enumerate(LOADFWD_A)} |
                {k + 4: _u32(v) for k, v in enumerate(LOADFWD_A)},
                "R=7 (an ORDINARY LOW register, also a single-hop SUCCESS "
                "point in isolation). Same two-consumer construction as "
                "loadfwd_persist_r67. Pilot observation: BOTH word0-3 AND "
                "word4-7 read 0 -- merely ADDING the second consumer breaks "
                "even the FIRST read, at a register that succeeds when it is "
                "the ONLY consumer (loadfwd_singlehop_r7). This shows the "
                "single-hop 'success' is sensitive to overall program SHAPE, "
                "not a stable address -- refuting a naive 'ephemeral forward "
                "to next instruction' model too, not just persistent access.",
                expect_match=None)

    # Mismatch test: load targets R=67, consumer names srcA=3 (mismatched)
    add_loadfwd("loadfwd_mismatch_load67_read3",
                H.get_sr_raw(1, 0xA0) + H.device_load_a(67) + H.device_load_b()
                + H.loadfwd_iminmax(3) + H.loadfwd_store(2, idx_off=0),
                {k: _u32(v) for k, v in enumerate(LOADFWD_A)},
                "device_load targets R=67 (dst_lo|dst_ext9<<2==67) but the "
                "consumer's OWN srcA field names 3 (mismatched). Oracle = "
                "a[] (the 'consumer field value is irrelevant, pure forward' "
                "prediction). Pilot observation: thread0 (gid=0) MATCHES "
                "a[0]=1234 unexpectedly; threads 1-3 read 0 -- neither "
                "'always forwards regardless of field' nor 'always requires "
                "field match' cleanly explains this; reported as a further, "
                "undissolved facet of the same anomaly, not silently "
                "normalized to either model.", expect_match=None)

    # ------------------------------------------------------------------
    # H2_REGMOVE_C9 -- is byte0=0x2b (reg_move_c9) a real GPR move?
    # ------------------------------------------------------------------
    def move_c9_case(name, src_reg, seed_val=None, note=""):
        pre_instrs = _idx0()
        if seed_val is not None:
            pre_instrs += [H.falu2i_raw(2, R_UNWRITTEN, seed_val, opflags4=1)]
        c9_fields = {"dst": 8, "src_reg": src_reg & 0x7F, "src_flag": 0,
                     "src_class": 0, "op_desc": 0xC0}
        c9_bytes = H.reg_move_c9_raw(8, src_reg)
        post_instrs = [H.device_store(R_IDX, 0, 0, 8, extmode=16)]
        pre_bytes = b"".join(pre_instrs)
        body = pre_bytes + c9_bytes + b"".join(post_instrs) + H.stop()
        hexbytes = H.build_program([body], CARRIER_LEN)
        H.assert_reg_move_c9_program(hexbytes, len(pre_bytes), c9_fields)
        oracle_val = H.f32_bits(seed_val) if seed_val is not None else 0
        expect = False if seed_val is not None else None
        nonlocal i
        cs.append({
            "i": i, "name": name, "group": "H2_REGMOVE_C9", "hex": hexbytes.hex(),
            "carrier": "carrier.metal", "oracle": {"0": _u32(oracle_val)},
            "expect_match": expect, "notes": note, "dispatch": dict(DEFAULT_DISPATCH),
        })
        i += 1

    move_c9_case("move_c9_producer_v1", 2, seed_val=30.0,
                 note="falu2i writes 30.0 to r2 (an ALU-only, HW-VALIDATED "
                 "seeding path, EXP-0090/EXP-0099). reg_move_c9(dst=8,"
                 "src_reg=2,src_flag=0,src_class=0,op_desc=0xC0) -- the "
                 "EXACT field values that reproduce EXP-0087's own "
                 "'undecoded' byte0=0x2b instance '2b0009c0' by "
                 "construction (verified statically in analysis.py). "
                 "Oracle = f32_bits(30.0) with expect_match=False: tests "
                 "whether this family reads r2's ALU-written content "
                 "(EXP-0101's own finding for the sibling reg_move_c1/c0 "
                 "shapes says NO).")
    move_c9_case("move_c9_producer_v2", 2, seed_val=2.0,
                 note="SAME register (r2), a DIFFERENT seeded value (2.0). "
                 "Producer-independence check (EXP-0101 style): if this "
                 "family reads a fixed, per-kernel PRELOADED slot rather "
                 "than the live GPR, move_c9_producer_v1 and _v2's RAW "
                 "observed bytes should be IDENTICAL despite the "
                 "different producer value -- checked post-hoc in "
                 "analysis.py, not by this case's own (necessarily "
                 "MISMATCH-predicting) oracle.")

    for lo in (0, 2, 4, 8):
        for off, tag in ((0, "lo"), (1, "hi")):
            move_c9_case("move_c9_pair_%d_%s" % (lo, tag), lo + off, seed_val=None,
                         note="Register-pair quantization sweep (EXP-0101 "
                         "style): src_reg=%d (pair partner of %d). No ALU "
                         "seeding -- reads whatever this family's src_flag=0 "
                         "addressing naturally exposes for this src_reg. "
                         "Oracle=0 is a placeholder (expect_match=None, "
                         "purely exploratory); the load-bearing check is "
                         "POST-HOC in analysis.py: src_reg=%d and src_reg=%d "
                         "(the pair) should read IDENTICAL raw content if "
                         "EXP-0101's pair-quantization finding extends to "
                         "this family." % (lo + off, lo, lo, lo + 1))

    # ------------------------------------------------------------------
    # H3_BUFFER_SIGNATURE -- reg_move_c1 src_reg vs bound-buffer count
    # ------------------------------------------------------------------
    def h3_case(name, carrier, carrier_len, src_reg):
        instrs = [H.mov_imm(R_IDX, 0), H.reg_move_c1_raw(8, src_reg),
                  H.device_store(R_IDX, 0, 0, 8, extmode=16)]
        add(name, "H3_BUFFER_SIGNATURE", instrs, {0: _u32(0)},
            "carrier=%s (bound-buffer count varies by carrier); "
            "reg_move_c1(dst=8,src_reg=%d,src_flag=0,src_class=2,"
            "op_desc=0) -> store r8 raw. Oracle=0 is a placeholder "
            "(expect_match=None, exploratory); the load-bearing "
            "comparison is POST-HOC in analysis.py: does src_reg=%d's "
            "observed content SHIFT between the buf1/buf2/buf3 carriers "
            "in a way correlated with bound-buffer count (EXP-0101 "
            "sec 2.7's own proposed next step)?" % (carrier, src_reg, src_reg),
            carrier=carrier, carrier_len=carrier_len)

    for src_reg in (0, 2, 4, 8):
        h3_case("h3_buf1_src%d" % src_reg, "carrier_buf1.metal", BUF1_CARRIER_LEN, src_reg)
        h3_case("h3_buf2_src%d" % src_reg, "carrier_buf2.metal", BUF2_CARRIER_LEN, src_reg)
        h3_case("h3_buf3_src%d" % src_reg, "carrier_buf3.metal", BUF3_CARRIER_LEN, src_reg)

    return cs


if __name__ == "__main__":
    cs = build_cases()
    print("n_cases:", len(cs))
    groups = {}
    for c in cs:
        groups.setdefault(c["group"], 0)
        groups[c["group"]] += 1
    for g, n in groups.items():
        print(" ", g, n)
    for c in cs:
        print(c["i"], c["name"], c["group"], len(c["hex"]) // 2, "bytes",
              c["carrier"], c["dispatch"], c["oracle"])
