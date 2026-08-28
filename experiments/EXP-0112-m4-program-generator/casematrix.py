#!/usr/bin/env python3
"""EXP-0112 case matrix: builds the FULL, deterministic (seed -> identical
result, always) corpus this experiment validates. Every case is ONE
generated AGX9 program (MAIN_DAG/REGBOUNDARY/IADD_ANCHOR: `carrier="dag"`,
spliced over kernels/carrier_dag.metal; CF: `carrier="cf"`, spliced over
kernels/carrier_cf.metal), executed on real M4 hardware, compared to an
independently host-computed oracle.

RECURRENCE (frozen at pre-registration, PRE_REGISTRATION.md SS3):
  - MAIN_DAG: for i in range(100): seed=i, n_nodes=SIZE_CYCLE[i % len(SIZE_CYCLE)].
    generator.generate_dag(seed, n_nodes) is a pure function of (seed,
    n_nodes) -- see generator.py. If the resulting oracle contains a NaN or
    +-Inf (an accidental float32-overflow confound, not a hardware
    finding -- see generator.py's MEM_WORDS docstring), seed is
    deterministically bumped by +100000, +200000, ... until clean; the
    bump count is recorded in the case's `notes` field.
  - REGBOUNDARY/IADD_ANCHOR/CF/ADVERSARIAL: fixed, explicit, hand-enumerated
    lists (below) -- deterministic by construction, not RNG-driven.

This file, once frozen (hash recorded in PRE_REGISTRATION.md/
CAPTURE_CONTRACT.json), IS "the generator run" for CODEX step 2's "freeze
before generating" requirement: `build_cases()` is a pure function of this
file + generator.py + families.py + cf.py + isa_helpers.py + tools/agx-isa
(read-only) -- calling it twice, or on two different days, produces
byte-identical output as long as none of those files change.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generator as G   # noqa: E402
import families as F    # noqa: E402
import cf as CF          # noqa: E402

DAG_CARRIER_LEN = G.DAG_CARRIER_LEN
CF_CARRIER_LEN = CF.CARRIER_LEN


def _clean(oracle):
    return all(math.isfinite(v) for v in oracle.values())


SIZE_CYCLE = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24, 26, 28, 30, 32, 35]


def build_main_dag_cases():
    out = []
    for i in range(100):
        n_nodes = SIZE_CYCLE[i % len(SIZE_CYCLE)]
        seed = i
        bumps = 0
        while True:
            hexstr, oracle, meta = G.build_dag_program(seed, n_nodes, DAG_CARRIER_LEN,
                                                          base_slot_out=G.SLOT_OUT, base_slot_in=G.SLOT_MEM)
            if _clean(oracle):
                break
            bumps += 1
            seed = i + bumps * 100000
            if bumps > 20:
                raise RuntimeError("MAIN_DAG case %d: could not find a clean seed after 20 bumps" % i)
        oracle_str = {str(k): v for k, v in oracle.items()}
        out.append({
            "name": "dag_%03d_n%d" % (i, n_nodes), "group": "MAIN_DAG", "carrier": "dag",
            "hex": hexstr, "oracle": oracle_str, "expect_match": True,
            "notes": "seed=%d n_nodes=%d max_live=%d n_stores=%d seed_bumps=%d" %
                     (seed, n_nodes, meta["max_live_registers"], meta["n_stores"], bumps),
        })
    return out


# R sweep: min, a dense run around the suspected 64-bit-boundary (per
# EXP-0099's register-field finding in a DIFFERENT addressing context),
# and the far end -- min/max/first-invalid-on-each-side coverage of the
# 7-bit extmode-target field, per the coordinator's scope reinforcement.
REG_SWEEP = [0, 1, 2, 3, 7, 15, 16, 20, 31, 32, 47, 48, 61, 62, 63, 64, 65, 66, 67, 68,
             79, 80, 95, 96, 111, 112, 126, 127]
REG_POISON_TARGETS = [64, 65, 67, 79]   # R values whose (R mod 64) target we pre-poison
                                          # (mod 64 = 0,1,3,15 -- all within falu2i's 4-bit
                                          # dst-nibble range, so the poison write is itself
                                          # a legal, independently-constructible instruction)


POISON_K = 30.0   # the documented max-representable falu2i minifloat immediate (EXP-0090) --
                   # used directly (not via an out-of-range value relying on clamping) so the
                   # poison signal is an intentional, exactly-representable constant.


def build_regboundary_cases():
    """R < 64: expect_match=True (positive construction; EXP-0101's own
    tested range was only {0,3,7,16,20} -- this is a dense 15-point sweep
    across the FULL sub-64 range). R >= 64: expect_match=False -- an
    informal pilot run of this exact sweep (PROGRESS.md) found this
    generator's naive full-7-bit extrapolation of EXP-0101's own rule
    ("R may be any value 0-127") FALSIFIED starting exactly at 64: R in
    [64,112] reads back 0.0 for a non-poisoned target (later shown by the
    poison cases below to be ALIASING to r(R mod 64), not a true
    zero-read), and R in {126,127} FAULTS the command buffer outright (a
    SECOND, different failure mode at the top of the 7-bit range). The
    frozen predictions below encode that pilot finding, per this project's
    standing convention of updating expect_match from an informal
    pre-freeze pilot run (EXP-0101 RESULTS.md's own convention)."""
    out = []
    for i, R in enumerate(REG_SWEEP):
        idx_off = 200 + (i * 7) % 100      # varied, arbitrary, avoids colliding with the "specials" region (idx<8)
        hexstr, expected = F.build_regboundary_program(G.MEM_WORDS, R, idx_off)
        expect = R < 64
        out.append({
            "name": "regb_R%03d" % R, "group": "REGBOUNDARY", "carrier": "dag",
            "hex": hexstr, "oracle": {"0": expected}, "expect_match": expect,
            "notes": ("R=%d idx_off=%d (positive construction, no poison); pilot finding: "
                      "R<64 correct, R in [64,112] silently reads r(R mod 64) (0.0 here "
                      "since nothing else wrote it), R in {126,127} FAULTS the command "
                      "buffer" % (R, idx_off)),
        })
    for R in REG_POISON_TARGETS:
        target = R & 0x3F
        idx_off = 300 + R
        hexstr, expected = F.build_regboundary_program(G.MEM_WORDS, R, idx_off, poison_reg=target, poison_k=POISON_K)
        out.append({
            "name": "regb_R%03d_poison_r%d" % (R, target), "group": "REGBOUNDARY", "carrier": "dag",
            "hex": hexstr, "oracle": {"0": expected}, "expect_match": False,
            "notes": ("R=%d idx_off=%d poison_reg=r%d=%.1f -- discriminates aliasing "
                      "(observed==%.1f, the CONFIRMED pilot outcome) vs silent-zero "
                      "(observed==0.0) vs correct bridge (observed==loaded value, "
                      "the pre-registered but falsified prediction)" %
                      (R, idx_off, target, POISON_K, POISON_K)),
        })
    return out


IADD_K_SWEEP = [0, 1, 2, 63, 64, 65, 100, 127, 128, 129, 200, 255]


def build_iadd_cases():
    out = []
    for i, K in enumerate(IADD_K_SWEEP):
        idx_off = i % len(G.IMEM_WORDS)
        hexstr, expected = F.build_iadd_program(G.IMEM_WORDS, K, idx_off)
        out.append({
            "name": "iadd_K%03d" % K, "group": "IADD_ANCHOR", "carrier": "dag",
            "hex": hexstr, "oracle": {"0": expected}, "expect_match": True,
            "notes": "K=%d (raw srcB_imm=(K<<1)&0xFF=%d, effective addend=%d) idx_off=%d" %
                     (K, (K << 1) & 0xFF, ((K << 1) & 0xFF) >> 1, idx_off),
        })
    return out


CF_CASES = [
    # (a_val, n_val, cond_override, name_suffix)
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
        out.append({
            "name": "cf_%s" % suffix, "group": "CF", "carrier": "cf",
            "hex": hexstr, "oracle": {"0": out0}, "expect_match": True,
            "cf_a": a_val, "cf_n": n_val,
            "notes": "a=%s n=%d cond=%s meta=%r" % (a_val, n_val, cond, meta),
        })
    return out


def build_adversarial_cases():
    out = []
    hexstr, correct = F.build_adv_missing_mods(G.MEM_WORDS, 400)
    out.append({"name": "adv_missing_mods_0xC0", "group": "ADVERSARIAL", "carrier": "dag",
                "hex": hexstr, "oracle": {"0": correct}, "expect_match": False,
                "notes": "falu2i consumes a load-sourced operand with mods=0 instead of the "
                         "EXP-0101-required 0xC0 -- predicts silent-zero of the load operand"})
    hexstr, correct = F.build_adv_wrong_dsttoken(G.MEM_WORDS, 401)
    out.append({"name": "adv_wrong_dst_token", "group": "ADVERSARIAL", "carrier": "dag",
                "hex": hexstr, "oracle": {"0": correct}, "expect_match": False,
                "notes": "device_load dst_lo/dst_ext9 forced to (0,0) instead of the verbatim "
                         "(1,1) token -- EXP-0101 adversarial finding predicts corruption"})
    # NOTE (found during THIS experiment's own dry-run validation, kept as
    # a first-class result -- see RESULTS.md "opflags/carrier-dependence"):
    # a decisive re-derivation swept falu2 register-register opflags over
    # ALL FOUR raw values {0,1,2,3} on kernels/carrier_dag.metal, in TWO
    # shapes (load-bridged operands, AND an EXACT re-creation of EXP-0090's
    # own adjacent-const-producer shape) -- every one of the 8 runs
    # returned the CORRECT sum, never a silently-zeroed srcB. This directly
    # CONTRADICTS EXP-0090's own finding_1 (opflags=2 silently zeroes srcB,
    # re-derived on kernels/carrier_p1.metal). The only variable changed
    # was the CARRIER FILE. This is consistent with this project's
    # already-documented "carrier-dependent splice behavior" caveat
    # (EXP-0099 PROGRESS.md Milestone 3) extended to a NEW field (opflags)
    # and NEW carrier pair -- not independently root-caused here (out of
    # this experiment's scope). Consequence: `expect_match=True` below
    # (matches what THIS carrier actually and reproducibly does), not the
    # originally-planned adversarial `False` -- an honest oracle beats a
    # falsified prediction. The generator's OWN policy (always opflags=3
    # for both-real falu2) remains unconditionally safe regardless of which
    # of the two carrier behaviors is "true" hardware behavior, so this
    # finding does not weaken any MAIN_DAG result.
    hexstr, correct = F.build_adv_opflags1_bothreal(G.MEM_WORDS, 402, 403)
    out.append({"name": "adv_opflags1_bothreal_carrier_dependent", "group": "ADVERSARIAL", "carrier": "dag",
                "hex": hexstr, "oracle": {"0": correct}, "expect_match": True,
                "notes": "falu2 register-register, both operands real, opflags forced to 1 "
                         "(bit0 only): on kernels/carrier_dag.metal this reproducibly gives "
                         "the CORRECT sum, contradicting EXP-0090 finding_1's opflags=2 "
                         "result (established on a DIFFERENT carrier, carrier_p1.metal) -- "
                         "see the loud comment above and RESULTS.md"})
    hexstr, correct = F.build_adv_liveness_flip(G.MEM_WORDS, 404)
    out.append({"name": "adv_liveness_flip", "group": "ADVERSARIAL", "carrier": "dag",
                "hex": hexstr, "oracle": {"0": correct}, "expect_match": False,
                "notes": "first (non-last) read of a twice-read register wrongly marked "
                         "last-use=1 -- EXP-0086/EXP-0090 predicts the second (real last) "
                         "read silently sees 0"})
    # positive control: a genuinely CORRECT construction, deliberately compared
    # against an UNREACHABLE oracle -- proves match-detection is not a rubber
    # stamp (mirrors EXP-0101's positive_control_deliberate_mismatch).
    hexstr, correct = F.build_regboundary_program(G.MEM_WORDS, 5, 450)
    out.append({"name": "positive_control_deliberate_mismatch", "group": "ADVERSARIAL", "carrier": "dag",
                "hex": hexstr, "oracle": {"0": correct + 12345.0}, "expect_match": False,
                "notes": "genuinely CORRECT R=5 bridge construction, compared against a "
                         "deliberately wrong oracle (correct+12345.0) -- must MISMATCH"})
    return out


def build_cases():
    cases = (build_main_dag_cases() + build_regboundary_cases() + build_iadd_cases() +
             build_cf_cases() + build_adversarial_cases())
    for i, c in enumerate(cases):
        c["i"] = i
    return cases


if __name__ == "__main__":
    cs = build_cases()
    from collections import Counter
    print("total cases:", len(cs))
    print(Counter(c["group"] for c in cs))
    print("expect_match=False count:", sum(1 for c in cs if not c["expect_match"]))
    names = [c["name"] for c in cs]
    assert len(names) == len(set(names)), "duplicate case name"
    assert [c["i"] for c in cs] == list(range(len(cs)))
    print("OK")
