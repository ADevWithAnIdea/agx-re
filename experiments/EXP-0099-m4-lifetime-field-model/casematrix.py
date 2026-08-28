#!/usr/bin/env python3
"""EXP-0099 case matrix. Every case = ONE hand-built AGX program (concat of
isa_helpers.py builders, each a tools/agx-isa isadb.assemble() call), padded
to CARRIER_LEN, spliced over kernels/carrier.metal's compiled `_agc.main`
(offset 0), executed on real M4 hardware via tools/agxtest, and compared to
an independently-computed oracle (Python float literals, computed from the
same isadb.imm_encode/imm_decode codec the assembler itself uses -- never
derived from an observed output).

CARRIER_LEN=170 and SLOT_OUT=0/SLOT_MEM=1 are re-derived facts about
kernels/carrier.metal WHEN COMPILED WITH --no-fast-math (the flag
tools/agxtest always passes) -- re-derived fresh by baseline.py before every
capture, never assumed (see PROGRESS.md for the pilot-phase incident: an
earlier, more elaborate carrier measured 770/776 bytes depending on
optimization flags and, independently, silently failed every device_load
splice for reasons not fully isolated -- switched to this deliberately
low-register-pressure carrier, shape-matched to EXP-0090's own
carrier_p2.metal, which is clean).

Register plan: R_IDX=15 (=0, addressing), R_UNWRITTEN=14 (never written,
HW-VALIDATED EXP-0087 reads 0.0). Every case stays inside r0-r13 for its own
live seed/result registers, plus the literal value 67 used as a srcA_reg/
srcB_reg FIELD VALUE (not a register any case ever writes) for the H1
register-identity test -- see PROGRESS.md pilot section: 67's low 6 bits
are also 3, i.e. the SAME low register the case's own control value lives
in, which is what makes the design decisive without needing a working
write to a genuinely-addressed r64+ (see SEEDING NOTE below).

SEEDING NOTE (why no case here seeds a real r64+ value): the pilot phase
found device_load's result cannot be reliably read by a SUBSEQUENT
falu2/falu2i instruction via ANY register or ANY of the 8 candidate "route"
values (this experiment's OWN H4 finding, replicated formally by the
ROUTE_LOAD/ROUTE_ALU/H4_BIT21 groups below) -- so seeding r64+ via
device_load and reading it back via falu2 would confound H1's own test with
H4's unresolved blocker. The SRCA_PAIR/SRCB_PAIR design below sidesteps this
entirely: it never writes to a genuine r64+ register at all. It relies only
on two independently HW-VALIDATED facts: (1) falu2i(srcA=UNWRITTEN, K) is a
reliable ALU-only seed (EXP-0090), and (2) an unwritten register reads
exactly 0.0 (EXP-0087 MOVE-04, reconfirmed by this experiment's own
unwritten_reads_zero case). Encoding a source-register FIELD value of 67
(low 6 bits = 3, bit for weight 64 = 1) and comparing the result to "reads
r3's seeded value" (his retention-flag model, or a 6-bit-only address model)
vs "reads r67's value" (the current db.json 7-bit-index model; since r67 is
never written by any case, that prediction is 0.0) is fully decisive without
needing a working r64+ write.

mem buffer (buffer(1), float32 words) is used ONLY by the H4/H5 groups
(ROUTE_LOAD, H4_STORE_BRIDGE, move_load_sourced), which are specifically
about consuming a device_load result:
  mem[0] = 133.75   (V_HIGH -- used by H4_STORE_BRIDGE)
  mem[1] = -8.5      (V_LOAD -- used by ROUTE_LOAD / move_load_sourced)
V_LOW = 30.0 is the fixed-point of isadb.imm_encode/imm_decode(42.5) -- an
ALU-seeded sentinel (falu2i, srcA=UNWRITTEN), NOT memory-resident. K2 = 20.0
(the later-reader's own immediate, also an exact fixed point) makes the two
predicted outcomes (retained: 30+20=50.0; released/corrupted: 0+20=20.0)
unambiguous and far apart.

Hypothesis mapping: SRCA_PAIR/SRCB_PAIR -> H1 (register-identity, via the
"current read" oracle word) + H2 (complementary-pair, via the "later read"
oracle word). ROUTE_LOAD/ROUTE_ALU/H4_BIT21/H4_STORE_BRIDGE -> H4.
GPR_MOVE_RETRY -> H5. H3 (registers 64-95 addressing) is NOT given its own
hardware group -- see RESULTS.md "H3 scope" section: this experiment's own
H1 result (bit15/31 has NO observed effect on which register is read, in
EITHER direction predicted by the two competing models) leaves H3 an OPEN
question neither model resolves, and time did not permit a further,
separate falu3-based probe (db.json flags that family's field semantics as
weakly-validated / structural-only, itself a multi-case undertaking).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / "tools" / "agx-isa"))
import isadb  # noqa: E402

CARRIER_LEN = 170
SLOT_OUT = 0
SLOT_MEM = 1
OUT_WORDS = 8  # word i lives at byte i*4; device_store's idx_off unit is
               # 16 BYTES = 4 WORDS (EXP-0090's own HW-VALIDATED formula,
               # store_byte_offset = idx*4 + idx_off*16) -- so idx_off=N
               # lands at word index 4*N. Every case here uses idx_off in
               # {0,1} -> words {0,4}.
MEM_WORDS = [133.75, -8.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
V_HIGH = MEM_WORDS[0]
V_LOAD = MEM_WORDS[1]
V_LOW = H.imm_value(42.5)   # -> 30.0, ALU-seeded, not memory-resident
K2 = H.imm_value(20.0)      # -> 20.0, the later-reader's own immediate
V_ALU = H.imm_value(16.0)   # -> 16.0, ALU-seeded control sentinel for ROUTE_ALU

R_IDX = H.R_IDX          # 15
R_UNWRITTEN = H.R_UNWRITTEN  # 14
X_HIGH = 67   # srcA_reg/srcB_reg FIELD VALUE under test: low6=3 (== the
              # register V_LOW lives in), bit-for-weight-64 = 1. No case
              # ever WRITES register 67.


def _seed_common():
    return [H.mov_imm(R_IDX, 0)]


def _seed_low(dst, k):
    """falu2i(srcA=UNWRITTEN, K) -- HW-VALIDATED ALU-only seed (EXP-0090),
    independent of the H4 load-to-ALU blocker."""
    return [H.falu2i_raw(dst, R_UNWRITTEN, k, opflags4=1)]


def _store_word(idx_off, data_reg, extmode=None):
    return [H.device_store(R_IDX, idx_off, SLOT_OUT, data_reg, extmode=extmode)]


def _prog(instrs):
    body = b"".join(instrs) + H.stop()
    return H.build_program([body], CARRIER_LEN)


def _case(i, name, group, instrs, oracle_words, notes, expect_match=None):
    """oracle_words: dict {word_index: expected_float}. word_index i lives
    at byte i*4 (device_store's idx_off unit is 16 bytes = word index 4*idx_off,
    so callers pass idx_off directly as the intended word index // 4 and this
    matrix keeps idx_off in {0,1} throughout, i.e. word indices {0,4})."""
    hexbytes = _prog(instrs)
    H.assert_round_trip(hexbytes)   # CODEX step 10, fail fast at build time
    return {
        "i": i, "name": name, "group": group,
        "hex": hexbytes.hex(),
        "oracle": {str(k): v for k, v in oracle_words.items()},
        "expect_match": expect_match,
        "notes": notes,
    }


def build_cases():
    cs = []
    i = 0

    def add(name, group, instrs, oracle_words, notes, expect_match=None):
        nonlocal i
        cs.append(_case(i, name, group, instrs, oracle_words, notes, expect_match))
        i += 1

    # ------------------------------------------------------------------
    # SEED_CHECK
    # ------------------------------------------------------------------
    add("seed_r3_readback", "SEED_CHECK",
        _seed_common() + _seed_low(3, V_LOW) + _store_word(0, 3),
        {0: V_LOW},
        "ALU-seeding sanity: falu2i(unwritten+K) then direct store.",
        expect_match=True)

    add("unwritten_reads_zero", "SEED_CHECK",
        _seed_common() + _store_word(0, R_UNWRITTEN, extmode=(R_UNWRITTEN << 1) & 0xFF),
        {0: 0.0},
        "Sentinel-register sanity: r14 is never written by any case in this "
        "matrix; EXP-0087 MOVE-04 predicts it reads exactly 0.0.",
        expect_match=True)

    add("positive_control_deliberate_mismatch", "SEED_CHECK",
        _seed_common() + _seed_low(3, V_LOW) + _store_word(0, 3),
        {0: 999.0},
        "Same construction as seed_r3_readback but an oracle chosen to be "
        "UNREACHABLE (30.0 != 999.0) -- proves match-detection actually "
        "detects mismatch, not a rubber stamp.",
        expect_match=False)

    # ------------------------------------------------------------------
    # SRCA_PAIR: H1 (register identity, word0 = the CURRENT read) + H2
    # (complementary pair, word4 = a SEPARATE later reader's result).
    # A = falu2(dst=5, srcA_reg=X, srcB=UNWRITTEN, opflags bit19=B19).
    # B = falu2i(dst=6, srcA_reg=3 [literal, always reads r3], K=20.0,
    #     opflags bit0=1 [natural single/last-use pattern]) -- the SAME
    #     "adjacent" methodology as EXP-0086's decisive case, generalized
    #     to also cross X (H1) against B19 (H2).
    # word0 (A's own result) = the CURRENT-READ oracle: 7-bit-index model
    #   predicts V_LOW for X=3, 0.0 for X=67 (r67 never written).
    # word4 (B's result) = the LATER-READ oracle: retained (B19=0) -> 50.0
    #   (V_LOW+K2); released (B19=1) -> 20.0 (0+K2, EXP-0086 polarity).
    # ------------------------------------------------------------------
    def pair_setup():
        return _seed_common() + _seed_low(3, V_LOW)

    def later_reader():
        return [H.falu2i_raw(6, 3, K2, opflags4=1)]

    for (label, X, b19) in [
        ("low_b19_0", 3, 0),
        ("low_b19_1", 3, 1),
        ("high_b19_0_DECISIVE", X_HIGH, 0),
        ("high_b19_1_DECISIVE", X_HIGH, 1),
    ]:
        opflags5 = b19  # bit20=0, bit21=0 fixed: isolate bit19/bit15 only
        cur_read_7bit_model = V_LOW if X == 3 else 0.0
        later_read = (V_LOW + K2) if b19 == 0 else K2
        add("srca_" + label, "SRCA_PAIR",
            pair_setup()
            + [H.falu2_raw(5, X, R_UNWRITTEN, opflags5, mod_hi4=0xC)]
            + later_reader()
            + _store_word(0, 5) + _store_word(1, 6),
            {0: cur_read_7bit_model, 4: later_read},
            "srcA_reg field=%d (bit-for-weight-64=%d), opflags bit19=%d, "
            "srcB=UNWRITTEN. word0 oracle is the CURRENT db.json 7-bit-index "
            "prediction (explainer's model predicts %.1f for X=67 too). "
            "word4 is the EXP-0086-style later-read oracle assuming the "
            "7-bit-index reading of word0 (retain/release polarity)." % (
                X, (X >> 6) & 1, b19, V_LOW))

    # ------------------------------------------------------------------
    # SRCB_PAIR: same design, srcB side. A = falu2(dst=5, srcA=UNWRITTEN,
    # srcB_reg=Y, opflags bit20=B20 [bit19 fixed=1, a safe baseline for the
    # don't-care srcA]).
    # ------------------------------------------------------------------
    for (label, Y, b20) in [
        ("low_b20_0", 3, 0),
        ("low_b20_1", 3, 1),
        ("high_b20_0_DECISIVE", X_HIGH, 0),
        ("high_b20_1_DECISIVE", X_HIGH, 1),
    ]:
        opflags5 = 1 | (b20 << 1)
        cur_read_7bit_model = V_LOW if Y == 3 else 0.0
        later_read = (V_LOW + K2) if b20 == 0 else K2
        add("srcb_" + label, "SRCB_PAIR",
            pair_setup()
            + [H.falu2_raw(5, R_UNWRITTEN, Y, opflags5, mod_hi4=0xC)]
            + later_reader()
            + _store_word(0, 5) + _store_word(1, 6),
            {0: cur_read_7bit_model, 4: later_read},
            "srcB_reg field=%d (bit-for-weight-64=%d), opflags bit20=%d, "
            "srcA=UNWRITTEN (bit19=1 fixed safe baseline). word0/word4 "
            "oracles as SRCA_PAIR, mirrored to srcB." % (
                Y, (Y >> 6) & 1, b20))

    # ------------------------------------------------------------------
    # ROUTE_LOAD / ROUTE_ALU / H4_BIT21: H4, the named blocker. srcA
    # sourced from device_load (LOAD) vs a prior falu2i (ALU, control).
    # mod_hi bits1-3 (bits45-47) = the claimed "consumer route", swept
    # 0..7. route=6 (mod_hi=0xC) is the ALU-to-ALU-working anchor.
    # ------------------------------------------------------------------
    for route in range(8):
        add("route_load_%d" % route, "ROUTE_LOAD",
            _seed_common()
            + [H.device_load(7, R_IDX, idx_off=1, elem_code=3, base_slot=SLOT_MEM)]
            + [H.falu2_raw(8, 7, R_UNWRITTEN, opflags5=1, mod_hi4=H.route_mod_hi(route))]
            + _store_word(0, 8),
            {0: V_LOAD},
            "srcA=r7 (written by device_load, mem[1]=%.2f), route=%d "
            "(mod_hi=0x%x), opflags5=1 (bit19=1,bit20=0, EXP-0090's own "
            "'one real + don't-care' working pattern)." % (V_LOAD, route, H.route_mod_hi(route)),
            expect_match=None)

    for route in range(8):
        add("route_alu_%d" % route, "ROUTE_ALU",
            _seed_common() + _seed_low(9, V_ALU)
            + [H.falu2_raw(10, 9, R_UNWRITTEN, opflags5=1, mod_hi4=H.route_mod_hi(route))]
            + _store_word(0, 10),
            {0: V_ALU},
            "srcA=r9 (written by falu2i, ALU producer), route=%d "
            "(mod_hi=0x%x) -- control replicate of the explainer's own claim "
            "that route does not affect an all-ALU-sourced operand." % (route, H.route_mod_hi(route)),
            expect_match=True)

    add("route_load_6_bit21", "H4_BIT21",
        _seed_common()
        + [H.device_load(7, R_IDX, idx_off=1, elem_code=3, base_slot=SLOT_MEM)]
        + [H.falu2_raw(8, 7, R_UNWRITTEN, opflags5=(1 | (1 << 2)), mod_hi4=H.route_mod_hi(6))]
        + _store_word(0, 8),
        {0: V_LOAD},
        "Same as route_load_6 but opflags bit21=1 (explainer's 'destination "
        "publication' bit, set on the CONSUMING instruction).")

    add("route_alu_6_bit21", "H4_BIT21",
        _seed_common() + _seed_low(9, V_ALU)
        + [H.falu2_raw(10, 9, R_UNWRITTEN, opflags5=(1 | (1 << 2)), mod_hi4=H.route_mod_hi(6))]
        + _store_word(0, 10),
        {0: V_ALU},
        "ALU-sourced control for route_load_6_bit21.",
        expect_match=True)

    add("h4_store_bridge_regstore", "H4_BIT21",
        _seed_common()
        + [H.device_load(X_HIGH, R_IDX, idx_off=0, elem_code=3, base_slot=SLOT_MEM)]
        + _store_word(0, X_HIGH, extmode=(X_HIGH << 1) & 0xFF),
        {0: V_HIGH},
        "device_load(dst=67, mem[0]=133.75) then a REGISTER-NAMED store "
        "(addr_mode=0x54, extmode=2*67=134) -- extends EXP-0090's own "
        "extmode=2*data_reg formula past its previously-tested range. A "
        "SEPARATE data point for the same load-consumption blocker as "
        "ROUTE_LOAD, via the store path instead of the ALU path.")

    # ------------------------------------------------------------------
    # GPR_MOVE_RETRY: H5, retry EXP-0090 P4's blocker (reg_move reading a
    # GPR written by falu2i) under independent candidate fixes.
    # ------------------------------------------------------------------
    add("move_baseline_fail_replicate", "GPR_MOVE_RETRY",
        _seed_common() + [H.falu2i_raw(2, R_UNWRITTEN, V_LOW, opflags4=1)]
        + [H.reg_move(3, 2)] + _store_word(0, 3),
        {0: V_LOW},
        "Replicates EXP-0090 P4's exact failing shape: falu2i writes r2, "
        "reg_move(dst=3,src=2), opflags=1 (EXP-0090's own default, bit21=0/"
        "unpublished per the explainer's model). Predicted (per EXP-0090) "
        "to MISMATCH (read 0).",
        expect_match=False)

    add("move_load_sourced", "GPR_MOVE_RETRY",
        _seed_common() + [H.device_load(2, R_IDX, idx_off=1, elem_code=3, base_slot=SLOT_MEM)]
        + [H.reg_move(3, 2)] + _store_word(0, 3),
        {0: V_LOAD},
        "Same reg_move, r2 written by device_load instead of falu2i -- "
        "closes EXP-0090's own explicitly-flagged open question ('whether "
        "reg_move can read a GPR written by device_load ... remains "
        "UNKNOWN').")

    add("move_bit21_set", "GPR_MOVE_RETRY",
        _seed_common() + [H.falu2i_raw(2, R_UNWRITTEN, V_LOW, opflags4=3)]
        + [H.reg_move(3, 2)] + _store_word(0, 3),
        {0: V_LOW},
        "Candidate fix 1: producer's opflags bit21=1 (falu2i opflags=3) -- "
        "'destination publication' hypothesis: does a later, DIFFERENT-"
        "FAMILY consumer (reg_move) require the producer to mark its "
        "result published, unlike ALU-to-ALU forwarding (EXP-0090 P1, "
        "which never set this bit and worked)?")

    add("move_padding", "GPR_MOVE_RETRY",
        _seed_common() + [H.falu2i_raw(2, R_UNWRITTEN, V_LOW, opflags4=1)]
        + [H.mov_imm(13, 0)] * 4 + [H.reg_move(3, 2)] + _store_word(0, 3),
        {0: V_LOW},
        "Candidate fix 2: 4 padding instructions between producer and "
        "reg_move -- tests a pipeline-timing explanation instead of a "
        "field-encoding explanation.")

    add("move_bit21_and_padding", "GPR_MOVE_RETRY",
        _seed_common() + [H.falu2i_raw(2, R_UNWRITTEN, V_LOW, opflags4=3)]
        + [H.mov_imm(13, 0)] * 4 + [H.reg_move(3, 2)] + _store_word(0, 3),
        {0: V_LOW},
        "Candidate fix 3: bit21=1 AND 4 padding instructions combined.")

    return cs


if __name__ == "__main__":
    cs = build_cases()
    print("n_cases:", len(cs))
    for c in cs:
        print(c["i"], c["name"], c["group"], len(c["hex"]) // 2, "bytes", c["oracle"])
