#!/usr/bin/env python3
"""EXP-0101 case matrix. Every case = ONE hand-built AGX program (concat of
isa_helpers.py builders, each a tools/agx-isa isadb.assemble() call), padded
to CARRIER_LEN, spliced over kernels/carrier.metal's compiled `_agc.main`
(offset 0), executed on real M4 hardware via tools/agxtest, and compared to
an independently-computed oracle (Python float literals / isadb's own
imm_encode/imm_decode fixed points / bit-pattern reinterpretations computed
via struct -- never derived from an observed GPU output).

CARRIER_LEN=170, SLOT_OUT=0, SLOT_MEM=1 are re-derived facts about
kernels/carrier.metal WHEN COMPILED WITH --no-fast-math, re-derived fresh by
baseline.py before every capture (never assumed) -- same carrier and
constants as EXP-0099-m4-lifetime-field-model (verbatim-copied kernel; see
kernels/carrier.metal's own header comment for why reuse is safe here).

Register plan: R_IDX=15 (=0, addressing, HW-VALIDATED EXP-0031/EXP-0082),
R_UNWRITTEN=14 (never written, reads 0.0, EXP-0087 MOVE-04), pad_dst=13
(padding sink, EXP-0099 convention). Every case's OWN live registers stay
inside r0-r12, r16, r20 (the two "far" registers are deliberately chosen to
avoid r13-r15 entirely -- an early pilot-phase mistake, corrected here,
would have accidentally targeted device_load's relocated consumer register
at r15 itself, silently corrupting R_IDX for that case's own trailing
device_store; see PROGRESS.md Milestone 3).

Two blockers, two groups:

BLOCKER 1 (LOAD_FIX / LOAD_ADVERSARIAL) -- device_load -> falu2/falu2i.
This experiment's own pilot-phase OWN-SHADER differential census
(analysis/census.py, PROGRESS.md Milestone 2) found, by diffing a
compiler-emitted device_load-then-falu2i sequence against EXP-0099's own
hand-built (and failing) construction, that EXP-M4-13's `dst = dst_lo |
(dst_ext9<<2)` formula for device_load's OWN "destination register" is NOT
the register a later falu2/falu2i must reference. The register a consumer
must use is instead `extmode / 2` (the SAME formula EXP-0090 already
established for device_store's ALU-forwarded-store `extmode` field --
turns out to be the SAME mechanism on the LOAD side, not a store-only
quirk). `dst_lo`/`dst_ext9` remain a SEPARATE, independently-required field
that must be copied from a compiler-observed value for the same
addr_mode/ld_format shape (this experiment's own compiled anchor:
dst_lo=1, dst_ext9=1 for addr_mode=0x44/ld_format=0x11 -- see
isa_helpers.DST_TOKEN_KNOWNGOOD) -- NOT derived from the target register.
LOAD_FIX cases positively validate this rule (extmode relocatable to any
target register 0-127, dst_lo/dst_ext9 held at the known-good token);
LOAD_ADVERSARIAL cases falsify the three most plausible WRONG rules (derive
dst_lo/dst_ext9 from the target register; leave them at an arbitrary
"zero" value; ignore extmode and rely on the naive dst formula instead).

BLOCKER 2 (MOVE_UNIFORM) -- reg_move (EXP-0087's `byte+2=0x01,op_desc=0x08`
encoding) cannot read a GPR written by falu2/falu2i or device_load; it
reads back an exact, reproducible `0x00000100` (EXP-0099's own finding).
This experiment's own pilot phase established, by varying the PRODUCER's
value/family while holding `src_reg` fixed, and separately by varying
`src_reg` while holding the producer fixed, that the observed value depends
ONLY on `src_reg` (in a register-PAIR-quantized way: src_reg and src_reg^1
read identically) and is COMPLETELY INDEPENDENT of what any GPR actually
holds. Cross-checking against `src_flag=1` (documented "uniform/class"
mode, which legibly reads back small distinct integers 1,2,3 at src_reg
1,2,3 for this carrier) and against a THIRD, differently-shaped carrier
(informal pilot only, not gated here -- see PROGRESS.md) shows most probed
`src_flag=0` slots' content depends on the KERNEL's own buffer/argument
signature (consistent with reading a per-kernel PRELOADED/uniform region)
while at least one slot pair (src_reg 2,3) is stable at `0x00000100` across
every carrier tried. **Net: this instruction never addresses the live GPR
file at this encoding, regardless of `src_flag`'s documented meaning --
Blocker 2 is NOT resolved (no working GPR-sourced move was found), but its
failure MECHANISM is now characterized: it reads a fixed, producer-
independent uniform/preload slot, not a corrupted or partial GPR read.**
MOVE_UNIFORM cases capture this: producer-independence (same src_reg, two
different producer values/families -> identical output), the
`src_flag=1` positive control (proves the harness CAN detect real
uniform-content differences), the register-pair-quantization boundary, and
a retest of EXP-0087's own open question about `byte+2=0x21` (docs/isa/
register-move-and-liveness.md section 1.3) against a genuine ALU-computed
source, which this experiment's own pilot phase found reads the SAME fixed
uniform value, not the ALU value -- resolving that 2026-08 open item as
"not a real move" rather than leaving it UNKNOWN.
"""
import struct
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
OUT_WORDS = 8

MEM_WORDS = [133.75, -8.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
V_HIGH = MEM_WORDS[0]
V_LOAD = MEM_WORDS[1]
V_LOW = H.imm_value(42.5)     # -> 30.0, ALU-seeded via falu2i(UNWRITTEN, K)
V_ALT = H.imm_value(2.0)      # -> 2.0, exact fixed point, a DIFFERENT ALU-seeded value
K_SMALL = H.imm_value(1.5)    # small immediate used to prove real arithmetic happened

R_IDX = H.R_IDX               # 15
R_UNWRITTEN = H.R_UNWRITTEN   # 14
DST_TOK = H.DST_TOKEN_KNOWNGOOD   # (1, 1) -- the one HW-confirmed-valid device_load dst_lo/dst_ext9 pair


def _bits(u32):
    return struct.unpack("<f", struct.pack("<I", u32 & 0xFFFFFFFF))[0]


# Blocker 2's own observed, reproducible bit patterns -- computed here via
# plain struct reinterpretation of a literal 32-bit constant, NOT derived
# from (nor equal to, by construction) any value this experiment's own
# programs ever WRITE to a register. Used as ORACLES (predictions to be
# checked against fresh hardware reads under the two-run gate), not as
# after-the-fact curve-fitting: PROGRESS.md records that these constants
# were established during the pilot phase, before this matrix was frozen.
UNIFORM_0x100 = _bits(0x00000100)          # src_reg in {2,3} (any producer/value/family)
UNIFORM_PAIR01 = _bits(0x0001C600)         # src_reg in {0,1}, THIS carrier
UNIFORM_PAIR45 = _bits(0x0001C500)         # src_reg in {4,5}, THIS carrier
UNIFORM_SRCFLAG1_1 = _bits(1)              # src_flag=1, src_reg=1
UNIFORM_SRCFLAG1_2 = _bits(2)              # src_flag=1, src_reg=2
UNIFORM_SRCFLAG1_3 = _bits(3)              # src_flag=1, src_reg=3


def _seed_common():
    return [H.mov_imm(R_IDX, 0)]


def _seed_alu(dst, k):
    """falu2i(srcA=UNWRITTEN, K) -- HW-VALIDATED ALU-only seed (EXP-0090),
    independent of either blocker."""
    return [H.falu2i_raw(dst, R_UNWRITTEN, k, opflags4=1)]


def _load_fixed(target_reg, idx_off=1):
    """device_load with extmode=2*target_reg (this experiment's own H1
    fix) and dst_lo/dst_ext9 held at the known-good token."""
    return [H.device_load_fixed(R_IDX, idx_off=idx_off, elem_code=3, base_slot=SLOT_MEM,
                                 extmode=2 * target_reg, dst_lo=DST_TOK[0], dst_ext9=DST_TOK[1])]


def _store_word(idx_off, data_reg):
    return [H.device_store(R_IDX, idx_off, SLOT_OUT, data_reg)]


def _prog(instrs):
    body = b"".join(instrs) + H.stop()
    return H.build_program([body], CARRIER_LEN)


def _case(i, name, group, instrs, oracle_words, notes, expect_match=None):
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
    # SEED_CHECK -- sanity + positive-control (proves match-detection isn't
    # a rubber stamp)
    # ------------------------------------------------------------------
    add("seed_r2_readback", "SEED_CHECK",
        _seed_common() + _seed_alu(2, V_LOW) + _store_word(0, 2),
        {0: V_LOW},
        "ALU-seeding sanity: falu2i(unwritten+K) then direct store.",
        expect_match=True)

    add("unwritten_reads_zero", "SEED_CHECK",
        _seed_common() + _store_word(0, R_UNWRITTEN),
        {0: 0.0},
        "Sentinel-register sanity: r14 is never written by any case in "
        "this matrix; EXP-0087 MOVE-04 predicts it reads exactly 0.0.",
        expect_match=True)

    add("positive_control_deliberate_mismatch", "SEED_CHECK",
        _seed_common() + _seed_alu(2, V_LOW) + _store_word(0, 2),
        {0: 999.0},
        "Same construction as seed_r2_readback but an oracle chosen to be "
        "UNREACHABLE (30.0 != 999.0) -- proves match-detection actually "
        "detects mismatch, not a rubber stamp.",
        expect_match=False)

    # ------------------------------------------------------------------
    # LOAD_FIX (Blocker 1, positive results) -- device_load's extmode
    # field, relocated to progressively more adversarial target registers,
    # with dst_lo/dst_ext9 held at the known-good token throughout.
    # ------------------------------------------------------------------
    add("route_load_replicate_fail_route6", "LOAD_REPLICATE",
        _seed_common()
        + [H.device_load_fixed(R_IDX, idx_off=1, elem_code=3, base_slot=SLOT_MEM,
                                extmode=0, dst_lo=7 & 3, dst_ext9=(7 >> 2) & 0x7F)]
        + [H.falu2_raw(8, 7, R_UNWRITTEN, opflags5=1, mod_hi4=0xC)]
        + _store_word(0, 8),
        {0: V_LOAD},
        "EXACT replication of EXP-0099's own ROUTE_LOAD (route=6) "
        "construction: device_load with extmode=0 (its old, WRONG default) "
        "and dst_lo/dst_ext9 derived from the target register 7 via the "
        "old naive formula (the isa_helpers.device_load() convention every "
        "prior experiment used) -- reproduces the documented blocker "
        "before this experiment's own fix is applied.",
        expect_match=False)

    add("fix_extmode_reg7_falu2", "LOAD_FIX",
        _seed_common()
        + _load_fixed(7)
        + [H.falu2_raw(8, 7, R_UNWRITTEN, opflags5=1, mod_hi4=0xC)]
        + _store_word(0, 8),
        {0: V_LOAD},
        "THE decisive fix, same falu2 register-register shape as "
        "EXP-0099's own ROUTE_LOAD: extmode=2*7=14 (this experiment's own "
        "H1 formula), dst_lo/dst_ext9 held at the known-good token (1,1) "
        "instead of being derived from register 7. Directly reverses the "
        "preceding replicate case.",
        expect_match=True)

    add("fix_extmode_reg7_falu2i", "LOAD_FIX",
        _seed_common()
        + _load_fixed(7)
        + [H.falu2i_raw(9, 7, K_SMALL, opflags4=1, mods=0xC0)]
        + _store_word(0, 9),
        {0: V_LOAD + K_SMALL},
        "Same fix, via falu2i (register + immediate) instead of falu2 "
        "(register-register) -- the form the compiler's own multiload "
        "census (analysis/census.py) actually emits, INCLUDING its "
        "mods=0xC0 tail field (the compiler's own v0/multiload anchors "
        "always emit mods in {0xC0,0x20,0x40,0x00,0xA0} depending on "
        "context; 0xC0 is what census_load_add.metal itself emits). "
        "K_SMALL added so a correct result requires REAL arithmetic on the "
        "loaded value, not merely a pass-through. A pilot-phase run of "
        "this EXACT case with isa_helpers' naive mods=0 DEFAULT failed "
        "(read K_SMALL alone, i.e. srcA read as 0) -- see the following "
        "adversarial case and PROGRESS.md Milestone 3.",
        expect_match=True)

    add("adversarial_falu2i_mods_naive_default", "LOAD_ADVERSARIAL",
        _seed_common()
        + _load_fixed(7)
        + [H.falu2i_raw(9, 7, K_SMALL, opflags4=1, mods=0)]
        + _store_word(0, 9),
        {0: V_LOAD + K_SMALL},
        "IDENTICAL to fix_extmode_reg7_falu2i except mods=0 (the naive "
        "isa_helpers.falu2i_raw() default, i.e. 'just don't set the field') "
        "instead of the compiler-observed 0xC0. Falsifies 'mods is "
        "don't-care once extmode/dst_lo/dst_ext9 are right': this pilot-"
        "phase discovery (mods bits 6 AND 7 must BOTH be set; either bit "
        "alone still fails, structurally the same shape as EXP-0090's own "
        "'opflags must be 3, not 1' finding for falu2's two-real-operand "
        "form) is a THIRD required field for falu2i-consumed loads, on top "
        "of extmode and the dst_lo/dst_ext9 token.",
        expect_match=False)

    add("fix_extmode_reg3", "LOAD_FIX",
        _seed_common() + _load_fixed(3)
        + [H.falu2_raw(8, 3, R_UNWRITTEN, opflags5=1, mod_hi4=0xC)]
        + _store_word(0, 8),
        {0: V_LOAD},
        "Generalization: relocate the consumer register to r3 (a LOW "
        "register, unlike the r7 anchor) via extmode alone.",
        expect_match=True)

    add("fix_extmode_reg16", "LOAD_FIX",
        _seed_common() + _load_fixed(16)
        + [H.falu2_raw(8, 16, R_UNWRITTEN, opflags5=1, mod_hi4=0xC)]
        + _store_word(0, 8),
        {0: V_LOAD},
        "Generalization: relocate to r16, the first register requiring "
        "the FULL 7-bit srcA_reg field (beyond falu2's own 4-bit dst-"
        "nibble range) -- r15 deliberately avoided (that is R_IDX; loading "
        "into it would corrupt this same program's own addressing).",
        expect_match=True)

    add("fix_extmode_reg20", "LOAD_FIX",
        _seed_common() + _load_fixed(20)
        + [H.falu2_raw(8, 20, R_UNWRITTEN, opflags5=1, mod_hi4=0xC)]
        + _store_word(0, 8),
        {0: V_LOAD},
        "Generalization: relocate to r20, confirming the formula holds "
        "well past the low-register range every prior hand-built "
        "experiment (EXP-0090/EXP-0099) confined itself to.",
        expect_match=True)

    # ------------------------------------------------------------------
    # LOAD_ADVERSARIAL (Blocker 1, falsification of the 3 most plausible
    # WRONG rules)
    # ------------------------------------------------------------------
    add("adversarial_extmode_unchanged_srcA_mismatch", "LOAD_ADVERSARIAL",
        _seed_common()
        + [H.device_load_fixed(R_IDX, idx_off=1, elem_code=3, base_slot=SLOT_MEM,
                                extmode=0, dst_lo=DST_TOK[0], dst_ext9=DST_TOK[1])]
        + [H.falu2_raw(8, 3, R_UNWRITTEN, opflags5=1, mod_hi4=0xC)]
        + _store_word(0, 8),
        {0: V_LOAD},
        "extmode left at 0 (its correct value for target r0) but the "
        "consumer's srcA_reg set to 3 (mismatched) -- a plain field "
        "mismatch must fail; this is the mechanism, not 'route'.",
        expect_match=False)

    add("adversarial_dstfields_naive_formula", "LOAD_ADVERSARIAL",
        _seed_common()
        + [H.device_load_fixed(R_IDX, idx_off=1, elem_code=3, base_slot=SLOT_MEM,
                                extmode=2 * 3, dst_lo=3 & 3, dst_ext9=(3 >> 2) & 0x7F)]
        + [H.falu2_raw(8, 3, R_UNWRITTEN, opflags5=1, mod_hi4=0xC)]
        + _store_word(0, 8),
        {0: V_LOAD},
        "extmode CORRECTLY set (2*3=6) but dst_lo/dst_ext9 computed from "
        "the target register via the old naive formula (3,0) instead of "
        "being copied from the known-good token (1,1) -- falsifies 'derive "
        "dst_lo/dst_ext9 from the target register' as a repair strategy.",
        expect_match=False)

    add("adversarial_dstfields_zero_extmode_correct", "LOAD_ADVERSARIAL",
        _seed_common()
        + [H.device_load_fixed(R_IDX, idx_off=1, elem_code=3, base_slot=SLOT_MEM,
                                extmode=2 * 3, dst_lo=0, dst_ext9=0)]
        + [H.falu2_raw(8, 3, R_UNWRITTEN, opflags5=1, mod_hi4=0xC)]
        + _store_word(0, 8),
        {0: V_LOAD},
        "extmode CORRECTLY set (2*3=6) but dst_lo/dst_ext9=(0,0) (an "
        "arbitrary, not-copied value) -- falsifies 'dst_lo/dst_ext9 is "
        "don't-care as long as extmode is right'.",
        expect_match=False)

    add("adversarial_dstfields_zero_extmode_unchanged", "LOAD_ADVERSARIAL",
        _seed_common()
        + [H.device_load_fixed(R_IDX, idx_off=1, elem_code=3, base_slot=SLOT_MEM,
                                extmode=0, dst_lo=0, dst_ext9=0)]
        + [H.falu2_raw(8, 0, R_UNWRITTEN, opflags5=1, mod_hi4=0xC)]
        + _store_word(0, 8),
        {0: V_LOAD},
        "extmode left at 0 (its CORRECT value for target r0) but "
        "dst_lo/dst_ext9 changed away from the known-good token (1,1) to "
        "(0,0) -- falsifies 'dst_lo/dst_ext9 is universally don't-care'; "
        "even with extmode already correct, disturbing dst_lo/dst_ext9 "
        "alone breaks the load.",
        expect_match=False)

    add("control_dst_nibble_independent_of_srcA", "LOAD_ADVERSARIAL",
        _seed_common() + _load_fixed(16)
        + [H.falu2_raw(8, 16, R_UNWRITTEN, opflags5=1, mod_hi4=0xC)]
        + _store_word(0, 8),
        {0: V_LOAD},
        "Consumer reads r16 (low 4 bits = 0) but the ALU's OWN dst nibble "
        "is 8 (deliberately NOT matching r16's low bits) -- confirms "
        "falu2's dst nibble is an independent low-register (0-15) write "
        "target, not required to alias the source's low bits (an early "
        "pilot-phase over-theory this case exists to falsify; see "
        "PROGRESS.md Milestone 2).",
        expect_match=True)

    # ------------------------------------------------------------------
    # MOVE_UNIFORM (Blocker 2, negative result + mechanism characterization)
    # ------------------------------------------------------------------
    add("move_replicate_baseline", "MOVE_UNIFORM",
        _seed_common() + _seed_alu(2, V_LOW)
        + [H.reg_move(3, 2)] + _store_word(0, 3),
        {0: UNIFORM_0x100},
        "Replicates EXP-0099's own move_baseline_fail_replicate: falu2i "
        "writes V_LOW=30.0 to r2, reg_move(dst=3,src=2) -- predicted "
        "(per EXP-0099 + this experiment's own pilot) to read back the "
        "exact denormal bit pattern 0x00000100, not V_LOW.",
        expect_match=True)

    add("move_producer_independence_altvalue", "MOVE_UNIFORM",
        _seed_common() + _seed_alu(2, V_ALT)
        + [H.reg_move(3, 2)] + _store_word(0, 3),
        {0: UNIFORM_0x100},
        "SAME construction as move_replicate_baseline, but the producer "
        "writes a DIFFERENT value (V_ALT=2.0, not V_LOW=30.0) to r2 -- "
        "decisive: if reg_move genuinely read r2, this MUST differ from "
        "the baseline case. Predicting the IDENTICAL 0x00000100 output.",
        expect_match=True)

    add("move_loadsourced_independence", "MOVE_UNIFORM",
        _seed_common() + _load_fixed(2)
        + [H.reg_move(3, 2)] + _store_word(0, 3),
        {0: UNIFORM_0x100},
        "SAME reg_move, but r2 is written by a (this experiment's own H1 "
        "FIXED, genuinely working) device_load instead of falu2i -- "
        "extends producer-independence across producer FAMILY too, on a "
        "load path now independently proven functional (unlike EXP-0099's "
        "own analogous case, which used the pre-fix, non-working load).",
        expect_match=True)

    for (n, sr) in [(0, 0), (1, 1)]:
        add("move_srcreg_pair01_r%d" % sr, "MOVE_UNIFORM",
            _seed_common() + _seed_alu(2, V_LOW)
            + [H.reg_move(3, sr)] + _store_word(0, 3),
            {0: UNIFORM_PAIR01},
            "src_reg=%d (src_flag=0, GPR mode), unrelated to the producer "
            "register (r2) -- register-PAIR-quantization probe: predicts "
            "src_reg=0 and src_reg=1 read IDENTICAL content on this "
            "carrier." % sr,
            expect_match=True)

    for (n, sr) in [(0, 4), (1, 5)]:
        add("move_srcreg_pair45_r%d" % sr, "MOVE_UNIFORM",
            _seed_common() + _seed_alu(2, V_LOW)
            + [H.reg_move(3, sr)] + _store_word(0, 3),
            {0: UNIFORM_PAIR45},
            "src_reg=%d -- second pair, a DIFFERENT stable value from the "
            "(0,1) pair and from the (2,3) pair's 0x00000100." % sr,
            expect_match=True)

    add("move_srcreg_8_reads_zero", "MOVE_UNIFORM",
        _seed_common() + _seed_alu(2, V_LOW)
        + [H.reg_move(3, 8)] + _store_word(0, 3),
        {0: 0.0},
        "src_reg=8 -- outside this carrier's populated preload region "
        "(matches EXP-0087 MOVE-04's 'far above range reads 0' pattern).",
        expect_match=True)

    for (sr, oracle, lbl) in [(1, UNIFORM_SRCFLAG1_1, "1"), (2, UNIFORM_SRCFLAG1_2, "2"),
                               (3, UNIFORM_SRCFLAG1_3, "3")]:
        add("move_srcflag1_positive_control_%s" % lbl, "MOVE_UNIFORM",
            _seed_common() + _seed_alu(2, V_LOW)
            + [H.reg_move(3, sr, src_flag=1)] + _store_word(0, 3),
            {0: oracle},
            "src_flag=1 (documented 'uniform/class' mode), src_reg=%s -- "
            "POSITIVE CONTROL: proves the harness and this instruction CAN "
            "read genuinely different, small, easily-distinguished content "
            "as src_reg varies (the literal integer %s as raw bits) -- "
            "match-detection here is not a rubber stamp; the GPR-mode "
            "cases' producer-independence is a real finding, not a broken "
            "test." % (sr, lbl),
            expect_match=True)

    add("move_srcclass_0x21_alu_sourced", "MOVE_UNIFORM",
        _seed_common() + _seed_alu(2, V_LOW)
        + [H.reg_move_var(3, 2, src_class=2, op_desc=8)] + _store_word(0, 3),
        {0: UNIFORM_0x100},
        "Retests EXP-0087's own open question (docs/isa/register-move-and-"
        "liveness.md section 1.3: byte+2=0x21, i.e. src_class=2, 'UNKNOWN "
        "-- do not rely on it') against a genuine ALU-computed r2=V_LOW=30 "
        "-- EXP-0087 could not distinguish 'real move' from 'lucky no-op' "
        "because its own carrier's r12 had no other writer. Here, if this "
        "were a real move it would read V_LOW=30.0; predicting it instead "
        "reads the SAME 0x00000100 as src_class=0 -- resolving the open "
        "question as 'reads the uniform file like src_class=0, not a real "
        "move' rather than leaving it UNKNOWN.",
        expect_match=True)

    add("move_opdesc_sweep_zero", "MOVE_UNIFORM",
        _seed_common() + _seed_alu(2, V_LOW)
        + [H.reg_move_var(3, 2, src_class=0, op_desc=0)] + _store_word(0, 3),
        {0: 0.0},
        "op_desc=0 (byte+3), src_class=0 -- EXP-0087's own byte+2/op_desc "
        "sweep found nearly every non-(src_class=0,op_desc=8) combination "
        "is a silent zero; this extends that finding to op_desc specifically "
        "on an ALU-sourced (rather than EXP-0087's uniform-sourced) carrier.",
        expect_match=True)

    add("positive_control_deliberate_mismatch_move", "SEED_CHECK",
        _seed_common() + _seed_alu(2, V_LOW)
        + [H.reg_move(3, 2)] + _store_word(0, 3),
        {0: 999.0},
        "Same construction as move_replicate_baseline but an oracle "
        "chosen to be UNREACHABLE -- proves match-detection for the "
        "MOVE_UNIFORM group specifically is not a rubber stamp either.",
        expect_match=False)

    return cs


if __name__ == "__main__":
    cs = build_cases()
    print("n_cases:", len(cs))
    for c in cs:
        print(c["i"], c["name"], c["group"], len(c["hex"]) // 2, "bytes", c["oracle"], "expect_match=", c["expect_match"])
