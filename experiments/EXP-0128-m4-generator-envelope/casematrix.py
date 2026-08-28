#!/usr/bin/env python3
"""EXP-0128 frozen case matrix. `build_cases()` is a pure function (no RNG,
every case explicitly enumerated) -- deterministic by construction, so
calling it twice in-process (or on two different days) always produces the
byte-identical corpus verify.py's --selftest checks for.

Groups:
  IADD_REG          -- item (c), iadd2 register-mode (d[dst]=r0 (+/-) r_N).
  LOADSTORE_DIRECT  -- item (a), device_load->device_store addr_mode=0x56.

See PRE_REGISTRATION.md SS3 for the frozen sweep design and SS4 for the
pass criterion.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import families as F  # noqa: E402


def build_cases():
    cases = []

    def add(name, group, mode, hexstr, oracle, expect_match, notes):
        cases.append({
            "i": len(cases), "name": name, "group": group, "carrier": "dag",
            "mode": mode, "hex": hexstr, "oracle": oracle,
            "expect_match": expect_match, "notes": notes,
        })

    # -----------------------------------------------------------------
    # IADD_REG -- N=0..15 sweep, dst=40+N, r0=20+N, rN=60+N. All seed
    # values kept in mov_imm's HW-VALIDATED SAFE range 0..127 (this
    # experiment's own pilot-phase finding, PROGRESS.md Milestone 1a:
    # imm8>=128 silently reads back 0 in general, and was additionally
    # observed to HANG the command buffer when combined with N=0's
    # self-read encoding -- isa_helpers.mov_imm hard-rejects imm8>=128 for
    # exactly this reason, so this matrix cannot silently regress).
    # -----------------------------------------------------------------
    for N in range(16):
        r0val = 20 + N
        rNval = 60 + N if N != 0 else r0val  # N==0 self-reads r0; rNval unused as a separate seed
        dst = 40 + N
        hexstr, expected = F.build_iadd_reg_positive(N, dst, r0val, rNval)
        add("iadd_reg_N%02d_dst%d" % (N, dst), "IADD_REG", "int", hexstr,
            {"0": expected}, True,
            "positive: d[%d] = r0(%d) + r%d(%d), formula srcB_imm=4*N -- HW-VALIDATED "
            "this experiment's pilot phase (PROGRESS.md M1), N=0..15 full mov_imm-seedable range" %
            (dst, r0val, N, rNval))

    # dst boundary probes (ties item b/write-side into item c's own family)
    hexstr, expected = F.build_iadd_reg_positive(5, 90, 21, 65)
    add("iadd_reg_dst_high90", "IADD_REG", "int", hexstr, {"0": expected}, True,
        "dst=90: iadd2's dst is a full 7-bit register field (db.json/EXP-0020: "
        "reaches the whole addressable GPR file, up to 96) -- unlike falu2/falu2i's "
        "4-bit dst nibble; this case reinforces that WRITE-side addressing for "
        "iadd2 is not bound by the mod-64 aliasing item (b) documents for the "
        "PACKED source-operand register field family (falu2/falu2i's srcA_reg/"
        "srcB_reg, and this experiment's own newly-decoded iadd2 srcB field, "
        "N<=15 tested).")
    hexstr, expected = F.build_iadd_reg_positive(5, 110, 21, 65)
    add("iadd_reg_dst_probe110", "IADD_REG", "int", hexstr, {"0": expected}, False,
        "EXPLORATORY probe beyond EXP-0020's own documented ~96-register ceiling "
        "(dst=110). expect_match=False is a CAUTIOUS prediction (fault or "
        "misroute), not a HW-VALIDATED claim -- this experiment has no positive "
        "evidence dst=110 works OR fails; recorded as an open boundary probe, "
        "not a confirmed rule either way. A pass here would be a genuine "
        "positive surprise, disclosed either way.")

    # subtract polarity (addsub=0) -- HW-VALIDATED THIS EXPERIMENT: for this
    # tail shape, addsub=0 computes rN - r0 (SECOND operand minus FIRST),
    # not the naive "srcA-srcB"=r0-rN db.json's own semantics note would
    # suggest by analogy with the anchor's immediate-mode shape -- see
    # families.py build_iadd_reg_positive's own docstring/comment.
    hexstr, expected = F.build_iadd_reg_positive(3, 56, 27, 63, addsub=0)
    add("iadd_reg_sub_N03", "IADD_REG", "int", hexstr, {"0": expected}, True,
        "addsub=0 (subtract): d[56] = r3(63) - r0(27) = 36 -- NOT r0-r3 "
        "(=-36) as a naive srcA-srcB reading would predict; HW-VALIDATED "
        "polarity for this specific register-mode tail shape (opc_tail="
        "0x17/0x05).")
    hexstr, expected = F.build_iadd_reg_positive(10, 57, 34, 70, addsub=0)
    add("iadd_reg_sub_N10", "IADD_REG", "int", hexstr, {"0": expected}, True,
        "addsub=0: d[57] = r10(70) - r0(34) = 36 -- second independent "
        "confirmation of the rN-r0 polarity.")

    # adversarial: wrong srcB_reg_hi -- DISCLOSED PILOT-PHASE SURPRISE (kept
    # as a pre-registered expect_match=False prediction per this project's
    # standing convention, e.g. EXP-0112's own "carrier-dependent opflags"
    # case): informal pre-freeze pilot testing found this construction
    # actually MATCHES (reg_hi=8 does NOT corrupt the read; d[58]=r0+r2
    # correctly, same as reg_hi=0) -- this REFUTES the "reg_hi is a
    # load-bearing register-select bit" hypothesis the case was built to
    # test, and is consistent with this experiment's own natural-compiler
    # differential-compilation recon (PROGRESS.md M1), where reg_hi varied
    # 0/8/16/32/64 across genuinely correct compiled instances. The
    # prediction is left at its originally pre-registered value
    # (expect_match=False) rather than silently corrected -- see
    # RESULTS.md for the disclosed discrepancy.
    hexstr, correct = F.build_iadd_reg_adversarial_reghi(2, 58, 26, 62, reg_hi_bad=8)
    add("iadd_reg_adv_wrong_reghi", "IADD_REG", "int", hexstr, {"0": correct}, False,
        "ADVERSARIAL (prediction): srcB_reg_hi forced to 8 instead of the "
        "value (0) every positive case above uses, N=2/dst=58 otherwise "
        "unchanged -- originally predicted a WRONG (not r0+r2) result. "
        "DISCLOSED PILOT FINDING (not corrected before freeze): this "
        "actually MATCHES -- reg_hi=8 does not corrupt the read. See notes "
        "above and RESULTS.md.")

    # positive control (deliberate mismatch, proves match-detection isn't a rubber stamp)
    hexstr, bogus = F.build_iadd_reg_positive_control_mismatch(7, 59, 31, 67)
    add("iadd_reg_positive_control_mismatch", "IADD_REG", "int", hexstr, {"0": bogus}, False,
        "POSITIVE CONTROL: a genuinely correct construction (d[59]=r0+r7), "
        "compared against a deliberately unreachable oracle (correct+123456) "
        "-- MUST mismatch; proves the harness detects a real correct answer as "
        "wrong when the ORACLE itself is wrong, not just when the hardware is.")

    # -----------------------------------------------------------------
    # LOADSTORE_DIRECT -- same-index round trips, cross-index pairs,
    # chained multi-pair, adversarial idx_off!=0, positive control.
    # -----------------------------------------------------------------
    for idx in range(8):
        hexstr, word_idx, correct = F.build_loadstore_pair(idx, idx)
        add("ls_direct_same_idx%d" % idx, "LOADSTORE_DIRECT", "float", hexstr,
            {str(word_idx): correct}, True,
            "positive: load word %d, store to word %d (same index reg value on "
            "both sides) via addr_mode=0x56 direct forward, idx_off=0 fixed both "
            "sides -- EXP-0090 finding_3 base mechanism." % (idx, idx))

    for load_idx, store_idx in [(2, 5), (0, 7), (7, 0), (3, 3)]:
        hexstr, word_idx, correct = F.build_loadstore_pair(load_idx, store_idx)
        add("ls_direct_cross_L%d_S%d" % (load_idx, store_idx), "LOADSTORE_DIRECT", "float",
            hexstr, {str(word_idx): correct}, True,
            "positive: load word %d, store to word %d -- INDEPENDENT index-register "
            "values on load vs store side (this experiment's own pilot-phase "
            "generalization, PROGRESS.md M2)." % (load_idx, store_idx))

    hexstr, oracle = F.build_loadstore_chained([(1, 3), (4, 6)])
    add("ls_direct_chained_2pair_a", "LOADSTORE_DIRECT", "float", hexstr, oracle, True,
        "positive: TWO independent load-store pairs in ONE program (1->3, 4->6) -- "
        "chaining HW-VALIDATED this experiment's pilot phase, unlike iadd2 "
        "register-mode's own chaining hazard (see item c negative).")
    hexstr, oracle = F.build_loadstore_chained([(0, 2), (5, 7)])
    add("ls_direct_chained_2pair_b", "LOADSTORE_DIRECT", "float", hexstr, oracle, True,
        "positive: a second, independently-chosen chained 2-pair program (0->2, 5->7).")

    hexstr, word_idx, correct = F.build_loadstore_adversarial_idxoff(2, 4, "store")
    add("ls_direct_adv_idxoff_store", "LOADSTORE_DIRECT", "float", hexstr,
        {str(word_idx): correct}, False,
        "ADVERSARIAL: store-side idx_off forced to 1 (instead of the required 0) "
        "-- predicts a WRONG (not the forwarded mem[2]) result, per this "
        "experiment's own pilot-phase finding (idx_off!=0 -> silent zero).")
    hexstr, word_idx, correct = F.build_loadstore_adversarial_idxoff(2, 4, "load")
    add("ls_direct_adv_idxoff_load", "LOADSTORE_DIRECT", "float", hexstr,
        {str(word_idx): correct}, False,
        "ADVERSARIAL: load-side idx_off forced to 1 instead of 0 -- predicts a "
        "WRONG (not mem[2]) result forwarded to word 4.")

    hexstr, word_idx, bogus = F.build_loadstore_positive_control_mismatch(6, 1)
    add("ls_direct_positive_control_mismatch", "LOADSTORE_DIRECT", "float", hexstr,
        {str(word_idx): bogus}, False,
        "POSITIVE CONTROL: a genuinely correct load(6)->store(1) construction "
        "compared against a deliberately unreachable oracle (correct+999.0) -- "
        "MUST mismatch.")

    return cases


if __name__ == "__main__":
    cs = build_cases()
    print("total cases:", len(cs))
    from collections import Counter
    print(Counter(c["group"] for c in cs))
    print(Counter(c["expect_match"] for c in cs))
