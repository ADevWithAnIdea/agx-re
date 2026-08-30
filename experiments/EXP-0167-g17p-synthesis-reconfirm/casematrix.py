#!/usr/bin/env python3
"""EXP-0158 case matrix (G17P): the FULL, deterministic corpus this experiment
validates.  Every case is ONE generated AGX9 program spliced over one of our
own compiled carrier kernels and executed on the A18 Pro, compared to an
independently host-computed oracle, and read back out of a POISONED buffer
behind an integrity SENTINEL.

`build_cases()` is a PURE function of this file + generator.py + families.py +
cf.py + synth.py + frozen_pilot.py + the PINNED work/isadb_pinned snapshot.
Calling it twice, on two machines, on two days, produces byte-identical output
as long as none of those files change.  Their hashes are recorded in
CAPTURE_CONTRACT.json.

GROUPS
  MAIN_DAG (100)   the EXACT 100 DAG shapes EXP-0112 ran (same RNG stream),
                   re-emitted with every field COMPUTED instead of copied, and
                   with the don't-care fields deliberately set OFF-NATURAL.
  DAG_INLINE (24)  a subset of the same shapes with every float constant moved
                   into `falu2`'s inline 8-bit immediate (EXP-0138) -- an
                   operand EXP-0112 did not know existed.
  REGBOUNDARY      the device_load -> ALU bridge destination register R swept,
                   INCLUDING R = 63 and R = 64, with poison controls.
  INLINEIMM        all 64 inline-immediate codes, dense, plus fmul and
                   srcB_neg arms.
  IADD_SYNTH       iadd2 REGISTER mode, fully synthesised (EXP-0128/EXP-0139).
  IADD_ANCHOR_COPIED  EXP-0112's immediate-mode anchor, retained and tagged
                   COPIED so the "still needs a donor" count is honest.
  CF               EXP-0090's P3 skeleton, retained and tagged COPIED for the
                   same reason.  NOTE: CF is the ONE family with no integrity
                   sentinel -- the 152-byte CF carrier cannot hold the extra
                   16 bytes, and lengthening a carrier is not semantically
                   neutral (EXP-0140).  Stated, not silently skipped.
  ADVERSARIAL      deliberate violations of the newly computed rules; each is
                   pre-registered to FAIL, so a pass would falsify the rule.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import synth as S       # noqa: E402
import generator as G   # noqa: E402
import families as F    # noqa: E402
import cf as CF         # noqa: E402
import frozen_pilot as FP  # noqa: E402

DAG_CARRIER_LEN = G.DAG_CARRIER_LEN
CF_CARRIER_LEN = CF.CARRIER_LEN
OUT_WORDS = 260                       # covers the sentinel at word 252


def _clean(oracle):
    return all(math.isfinite(v) for v in oracle.values())


SIZE_CYCLE = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24, 26,
              28, 30, 32, 35]


def _case(name, group, carrier, hexstr, oracle, expect_match, notes, meta=None,
          oracle_bits=None, **kw):
    """`oracle` is a per-word FLOAT expectation; `oracle_bits` is a per-word RAW
    32-BIT expectation, used by the integer families.  A negative integer result
    has a bit pattern IEEE-754 reads as NaN, and NaN != NaN, so comparing an
    integer result as a float reports a false failure -- the pilot's P9 arm hit
    exactly that.  A case carries one or the other, never both."""
    c = {"name": name, "group": group, "carrier": carrier, "hex": hexstr,
         "oracle": {str(k): v for k, v in (oracle or {}).items()},
         "oracle_bits": {str(k): int(v) for k, v in (oracle_bits or {}).items()},
         "expect_match": expect_match, "notes": notes,
         "sentinel": carrier == "dag"}
    if meta is not None:
        c["prov"] = {"counts": meta["prov_counts"], "copied": meta["copied_fields"],
                     "carrier": meta["carrier_fields"], "pilot": meta["pilot_fields"]}
    c.update(kw)
    return c


# ---------------------------------------------------------------------------
def build_main_dag_cases(imm_mode="falu2i", n=100, group="MAIN_DAG", prefix="dag"):
    out = []
    for i in range(n):
        n_nodes = SIZE_CYCLE[i % len(SIZE_CYCLE)]
        seed = i
        bumps = 0
        while True:
            hexstr, oracle, meta = G.build_dag_program(
                seed, n_nodes, DAG_CARRIER_LEN, base_slot_out=G.SLOT_OUT,
                base_slot_in=G.SLOT_MEM, imm_mode=imm_mode)
            if _clean(oracle):
                break
            bumps += 1
            seed = i + bumps * 100000
            if bumps > 20:
                raise RuntimeError("%s case %d: no clean seed after 20 bumps" % (group, i))
        out.append(_case(
            "%s_%03d_n%d" % (prefix, i, n_nodes), group, "dag", hexstr, oracle, True,
            "seed=%d n_nodes=%d max_live=%d n_stores=%d seed_bumps=%d imm_mode=%s "
            "offnatural_fields=%d" % (seed, n_nodes, meta["max_live_registers"],
                                      meta["n_stores"], bumps, imm_mode,
                                      meta["n_offnatural"]),
            meta))
    return out


# ---------------------------------------------------------------------------
# REGBOUNDARY: EXP-0141's destination rule gives the generator a FREE CHOICE of
# R that EXP-0112 never had (it could only reuse the one captured dst token).
# 63 and 64 are the dispatch's named boundary pair.
# ---------------------------------------------------------------------------
REG_SWEEP = [0, 1, 2, 3, 7, 15, 16, 20, 31, 32, 47, 48, 60, 61, 62, 63,
             64, 65, 66, 67, 68, 79, 80, 95, 96, 111, 112]
REG_FAULT_SWEEP = [126, 127]          # EXP-0112 recorded CMDBUF_ERROR here
REG_POISON_TARGETS = [63, 64, 65, 67, 79]


POISON_K = 30.0


def build_regboundary_cases():
    out = []
    for i, R in enumerate(REG_SWEEP):
        idx_off = 200 + (i * 7) % 100
        hexstr, expected, meta = F.build_regboundary_program(G.MEM_WORDS, R, idx_off,
                                                             salt="rb%d" % R)
        out.append(_case(
            "regb_R%03d" % R, "REGBOUNDARY", "dag", hexstr, {0: expected}, R < 64,
            "R=%d idx_off=%d. PRE-REGISTERED: R<=63 delivers the loaded value "
            "(EXP-0141 destination rule, extmode=2*R with bit0 a don't-care); "
            "R>=64 must NOT deliver it -- extmode bit7 is then set, which "
            "EXP-0141 says silently zeroes the write, and the consumer's 6-bit "
            "srcA_reg field independently aliases to r(R mod 64). The poison "
            "cases below discriminate the two." % (R, idx_off), meta))
    for R in REG_FAULT_SWEEP:
        idx_off = 150 + R
        hexstr, expected, meta = F.build_regboundary_program(G.MEM_WORDS, R, idx_off,
                                                             salt="rbf%d" % R)
        out.append(_case(
            "regb_R%03d_faultarm" % R, "REGBOUNDARY", "dag", hexstr, {0: expected}, False,
            "R=%d -- EXP-0112 (M4) recorded CMDBUF_ERROR at 126/127. Re-run here "
            "on G17P; a fault verdict requires majority-of-3 per "
            "FIELD-SWEEP-PROTOCOL section 7." % R, meta))
    for R in REG_POISON_TARGETS:
        target = R & 0x3F
        idx_off = 300 + R
        hexstr, expected, meta = F.build_regboundary_program(
            G.MEM_WORDS, R, idx_off, salt="rbp%d" % R, poison_reg=target, poison_k=POISON_K)
        out.append(_case(
            "regb_R%03d_poison_r%d" % (R, target), "REGBOUNDARY", "dag", hexstr,
            {0: expected}, R < 64,
            "R=%d idx_off=%d poison_reg=r%d=%.1f. R=63 is a CONTROL: 63 mod 64 == 63, "
            "so the poison write and the load target are the SAME register and the "
            "load must overwrite the poison -> expect the loaded value. For R>=64 "
            "the poison must survive (%.1f) if the mechanism is consumer-side "
            "aliasing, and must read 0.0 if it is a pure silent zero."
            % (R, idx_off, target, POISON_K, POISON_K), meta))
    # the documented DON'T CARE, exercised on purpose: extmode bit0
    for R in (5, 63):
        for lsb in (0, 1):
            idx_off = 400 + R + lsb
            hexstr, expected, meta = F.build_regboundary_program(
                G.MEM_WORDS, R, idx_off, salt="rbl%d_%d" % (R, lsb),
                extmode_override=((R << 1) | lsb))
            out.append(_case(
                "regb_R%03d_extlsb%d" % (R, lsb), "REGBOUNDARY", "dag", hexstr,
                {0: expected}, True,
                "extmode = 2*R | %d -- EXP-0141 says extmode bit0 is a DON'T CARE. "
                "A compiler never sets it; this generator does." % lsb, meta))
    return out


# ---------------------------------------------------------------------------
# INLINEIMM -- the operand EXP-0112 did not have
# ---------------------------------------------------------------------------
def build_inline_imm_cases():
    out = []
    for k in range(64):
        hexstr, expected, meta = F.build_inline_imm_program(k, salt="ii%d" % k)
        out.append(_case(
            "inl_k%02d" % k, "INLINEIMM", "dag", hexstr, {0: expected}, True,
            "falu2 inline 8-bit float immediate, code k=%d -> %s (EXP-0138 SS3 "
            "magnitude model; sign convention frozen from this experiment's own "
            "pilot, INLINE_NEG0_SIGN=%s). DENSE: all 64 codes."
            % (k, meta["imm_value"], FP.INLINE_NEG0_SIGN), meta))
    for k in (0, 8, 24, 32, 48, 56, 63):
        hexstr, expected, meta = F.build_inline_imm_program(k, salt="iim%d" % k, op="fmul")
        out.append(_case(
            "inl_mul_k%02d" % k, "INLINEIMM", "dag", hexstr, {0: expected}, True,
            "inline immediate under fmul (opsel=5) rather than fadd -- proves the "
            "operand class is orthogonal to the opcode. k=%d -> %s"
            % (k, meta["imm_value"]), meta))
    if FP.INLINE_NEG_WORKS:
        for k in (2, 16, 32, 48, 63):
            hexstr, expected, meta = F.build_inline_imm_program(
                k, salt="iin%d" % k, srcB_neg=1)
            out.append(_case(
                "inl_neg_k%02d" % k, "INLINEIMM", "dag", hexstr, {0: expected}, True,
                "srcB_neg=1 applied to an INLINE immediate -- an extrapolation "
                "confirmed by this experiment's own pilot (arm P5). k=%d -> %s"
                % (k, meta["imm_value"]), meta))
    return out


# ---------------------------------------------------------------------------
# IADD_SYNTH -- replaces EXP-0112's verbatim anchor
# ---------------------------------------------------------------------------
IADD_SYNTH_CASES = [
    # (A, B, N, dst_reg, addsub)
    (10, 7, 1, 2, 1), (10, 7, 1, 2, 0), (0, 0, 1, 3, 1), (127, 127, 2, 4, 1),
    (1, 126, 3, 5, 1), (100, 27, 5, 6, 0), (5, 0, 0, 7, 1), (63, 64, 9, 8, 1),
    (33, 44, 13, 9, 0), (127, 1, 15, 10, 1), (11, 22, 1, 0, 1), (11, 22, 1, 63, 1),
    (11, 22, 1, 64, 1), (11, 22, 1, 95, 1), (77, 13, 6, 32, 0), (7, 120, 4, 47, 1),
]


def build_iadd_synth_cases():
    out = []
    for (A, B, N, D, sub) in IADD_SYNTH_CASES:
        hexstr, expected, meta = F.build_iadd_synth_program(
            A, B, N, D, sub, salt="is%d_%d_%d_%d_%d" % (A, B, N, D, sub))
        out.append(_case(
            "iaddsyn_A%d_B%d_N%d_D%d_%s" % (A, B, N, D, "add" if sub else "sub"),
            "IADD_SYNTH", "dag", hexstr, None, True,
            "iadd2 REGISTER mode, fully synthesised: srcA is a format byte that "
            "always reads r0 (EXP-0128 SS1.2); srcB_imm=4*N selects r%d; "
            "addsub=%d gives %s; dst=(reg<<1)|1 with reg=%d < 96 (EXP-0139). "
            "EXP-0112 could not build this at all -- it reused one captured "
            "immediate-mode anchor." % (N, sub, "r0+rN" if sub else "rN-r0", D), meta,
            oracle_bits={0: expected}))
    return out


IADD_K_SWEEP = [0, 1, 2, 63, 64, 65, 100, 127, 128, 129, 200, 255]


def build_iadd_anchor_cases():
    out = []
    for i, K in enumerate(IADD_K_SWEEP):
        idx_off = i % len(G.IMEM_WORDS)
        hexstr, expected, meta = F.build_iadd_anchor_program(
            G.IMEM_WORDS, K, idx_off, salt="ia%d" % K)
        out.append(_case(
            "iaddanchor_K%03d" % K, "IADD_ANCHOR_COPIED", "dag", hexstr, None,
            True,
            "RETAINED COPY. K=%d (raw srcB_imm=(K<<1)&0xFF=%d, effective addend=%d). "
            "EXP-0139's dense masks were established on the REGISTER-mode carrier "
            "and do not describe this immediate-mode tail (this anchor's "
            "opc_tail2=4 fails EXP-0139's v&0x05==0x05 rule yet executes), so no "
            "rule is available and the tail stays COPIED."
            % (K, (K << 1) & 0xFF, ((K << 1) & 0xFF) >> 1), meta,
            oracle_bits={0: expected}))
    return out


CF_CASES = [
    (50.0, 3, None, "trip3_false_arm"),
    (150.0, 5, None, "trip5_true_arm"),
    (100.01, 0, None, "trip0_boundary_true"),
    (99.9, 0, None, "trip0_boundary_false"),
    (10.0, 60, None, "trip60_true_arm"),
    (150.0, 5, 7, "cond7_guard_skipped"),
    (50.0, 0, None, "trip0_false_arm"),
    (200.0, 1, None, "trip1_true_arm"),
    (-50.0, 10, None, "negative_start_false_arm"),
    (33.5, 45, None, "trip45_arithmetic"),
    (98.0, 2, None, "trip2_boundary_false"),
    (34.0, 45, None, "trip45_boundary_true"),
]


def build_cf_cases():
    out = []
    for a_val, n_val, cond, suffix in CF_CASES:
        hexstr, out0, meta = CF.build_cf_program(a_val, n_val, cond_override=cond)
        out.append(_case(
            "cf_%s" % suffix, "CF", "cf", hexstr, {0: out0}, True,
            "RETAINED COPY (no rule for the control-flow operand fields). "
            "a=%s n=%d cond=%s. NO integrity sentinel: the 152-byte CF carrier "
            "cannot hold one and lengthening a carrier is not semantically "
            "neutral (EXP-0140)." % (a_val, n_val, cond),
            meta, cf_a=a_val, cf_n=n_val))
    return out


# ---------------------------------------------------------------------------
def build_adversarial_cases():
    out = []
    for bad in (0, 2, 3):
        hexstr, correct, meta = F.build_adv_dst_lo(G.MEM_WORDS, 500 + bad,
                                                   bad, salt="advdl%d" % bad)
        out.append(_case(
            "adv_dst_lo_%d" % bad, "ADVERSARIAL", "dag", hexstr, {0: correct}, False,
            "device_load dst_lo forced to %d. EXP-0141's EXACT rule is "
            "dst_lo & 0x03 == 0x01, so this must NOT deliver the loaded value. "
            "If it does, the destination rule this whole experiment rests on is "
            "wrong." % bad, meta))
    hexstr, correct, meta = F.build_adv_dst_ext9_even(G.MEM_WORDS, 510, salt="advde")
    out.append(_case(
        "adv_dst_ext9_even", "ADVERSARIAL", "dag", hexstr, {0: correct}, False,
        "device_load dst_ext9 forced to 2 (bit0 clear). EXP-0141: bit0 must be 1; "
        "all 64 even values silently zero.", meta))
    hexstr, correct, meta = F.build_adv_extmode_bit7(G.MEM_WORDS, 511, salt="advb7")
    out.append(_case(
        "adv_extmode_bit7", "ADVERSARIAL", "dag", hexstr, {0: correct}, False,
        "device_load extmode bit7 forced set with R=7. EXP-0141: bit7 set means "
        "r64+, which silently zeroes.", meta))
    hexstr, correct, meta = F.build_adv_missing_mods(G.MEM_WORDS, 512, salt="advmm")
    out.append(_case(
        "adv_missing_mods_0xC0", "ADVERSARIAL", "dag", hexstr, {0: correct}, False,
        "falu2i consumes a load-sourced operand with mods=0 instead of the "
        "EXP-0101 H1 required 0xC0 -- predicts a silent zero of the load operand.",
        meta))
    hexstr, correct, meta = F.build_adv_liveness_flip(G.MEM_WORDS, 513, salt="advlf")
    out.append(_case(
        "adv_liveness_flip", "ADVERSARIAL", "dag", hexstr, {0: correct}, False,
        "first (non-last) read of a twice-read register wrongly marked last-use=1 "
        "-- EXP-0086/EXP-0090 predict the second (real last) read silently sees 0.",
        meta))
    hexstr, correct, meta = F.build_adv_iadd_dst96(50, 25, 1, salt="advid")
    out.append(_case(
        "adv_iadd_dst_reg96", "ADVERSARIAL", "dag", hexstr, None, False,
        "iadd2 dst register 96 -- EXP-0139 found reg >= 96 faults reproducibly.",
        meta, oracle_bits={0: correct}))
    # inline-immediate adversarials: the source-class model must be load-bearing
    hexstr, correct, meta = F.build_inline_imm_program(
        48, salt="advic0", srcB_class_override=0)
    out.append(_case(
        "adv_inline_class0", "ADVERSARIAL", "dag", hexstr, {0: correct}, False,
        "the inline-immediate operand with srcB_class forced to 0 (GPR class): the "
        "index must then be read as a REGISTER (aliasing r48, unwritten -> 0.0), "
        "not as an immediate. EXP-0138's source-class model predicts this.", meta))
    hexstr, correct, meta = F.build_inline_imm_program(
        48, salt="advit0", srcB_top_override=0)
    out.append(_case(
        "adv_inline_top0", "ADVERSARIAL", "dag", hexstr, {0: correct}, False,
        "the inline-immediate operand with srcB bit6 cleared: index 48 is then a "
        "UNIFORM-register index, not an immediate (EXP-0138: 0..63 uniform, "
        "64..127 immediate). Must not deliver the immediate's value.", meta))
    # positive control: correct construction vs an unreachable oracle
    hexstr, correct, meta = F.build_regboundary_program(G.MEM_WORDS, 5, 450, salt="pc")
    out.append(_case(
        "positive_control_deliberate_mismatch", "ADVERSARIAL", "dag", hexstr,
        {0: correct + 12345.0}, False,
        "a genuinely CORRECT R=5 bridge construction compared against a "
        "deliberately unreachable oracle (correct+12345.0) -- must MISMATCH, which "
        "proves the match test is not a rubber stamp.", meta))
    return out


DAG_INLINE_N = 24


def build_cases():
    cases = (build_main_dag_cases() +
             build_main_dag_cases(imm_mode="inline", n=DAG_INLINE_N,
                                  group="DAG_INLINE", prefix="dagi") +
             build_regboundary_cases() +
             build_inline_imm_cases() +
             build_iadd_synth_cases() +
             build_iadd_anchor_cases() +
             build_cf_cases() +
             build_adversarial_cases())
    for i, c in enumerate(cases):
        c["i"] = i
    return cases


if __name__ == "__main__":
    from collections import Counter
    cs = build_cases()
    print("total cases:", len(cs))
    print(Counter(c["group"] for c in cs))
    print("expect_match=False:", sum(1 for c in cs if not c["expect_match"]))
    zero_copied = [c for c in cs if c.get("prov") and not c["prov"]["copied"]]
    print("cases with ZERO copied fields:", len(zero_copied), "of", len(cs))
    print("cases with zero copied AND zero pilot fields:",
          sum(1 for c in zero_copied if not c["prov"]["pilot"]))
    names = [c["name"] for c in cs]
    assert len(names) == len(set(names)), "duplicate case name"
    assert [c["i"] for c in cs] == list(range(len(cs)))
    print("OK")
