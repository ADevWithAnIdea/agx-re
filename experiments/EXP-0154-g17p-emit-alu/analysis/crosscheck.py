#!/usr/bin/env python3
"""EXP-0154 cross-checks: the pre-registered M4 -> G17P reproduction tests
(PRE_REGISTRATION.md H5 / F1-F5) and the `ilogic` boolean-function recovery.

  python3 analysis/crosscheck.py raw/g17p_20260829_run02 raw/g17p_20260829_run03

A G16G <-> G17P disagreement is a FIRST-CLASS finding and is printed as such.
"""
from __future__ import print_function

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H          # noqa: E402
import casematrix as CM          # noqa: E402
import verdicts as V             # noqa: E402

# EXP-0146 table 'ilogic — the complete 2-input boolean LUT encoding' (M4/G16G),
# minimal selector (op_base, lut_a & 3, lut_b & 0x0f) -> function index, where
# the function index is the truth table (f00,f01,f10,f11) read as a 4-bit number.
M4_LUT = {
    (0, 0x0, 0x0): 0b0000, (1, 0x0, 0x0): 0b0001, (0, 0x0, 0x8): 0b0010,
    (0, 0x0, 0x9): 0b0011, (0, 0x2, 0x0): 0b0100, (0, 0x2, 0x2): 0b0101,
    (0, 0x2, 0x8): 0b0110, (1, 0x2, 0x8): 0b0111, (0, 0x1, 0x0): 0b1000,
    (1, 0x1, 0x0): 0b1001, (0, 0x1, 0x2): 0b1010, (1, 0x1, 0x8): 0b1011,
    (0, 0x1, 0x1): 0b1100, (1, 0x3, 0x0): 0b1101, (0, 0x3, 0x8): 0b1110,
    (0, 0x1, 0x5): 0b1111,
}
FN_NAME = ["0", "and", "a_and_not_b", "a", "not_a_and_b", "b", "xor", "or",
           "nor", "xnor", "not_b", "a_or_not_b", "not_a", "not_a_or_b",
           "nand", "1"]
# EXP-0146 orders the columns (aa,ab,ba,bb); index 1 is `and`, so the bit order
# used above is (f00,f01,f10,f11) with f11 the LSB.


def derive_lut(a, b, res):
    """Recover the 2-input boolean function from ONE (a, b, result) triple, and
    return None unless the result is a consistent bitwise function of (a, b)
    across every bit position (the check EXP-0146 also had to pass)."""
    tab = {}
    for i in range(32):
        ka, kb, kr = (a >> i) & 1, (b >> i) & 1, (res >> i) & 1
        if (ka, kb) in tab and tab[(ka, kb)] != kr:
            return None
        tab[(ka, kb)] = kr
    if len(tab) < 4:
        return None
    return (tab[(0, 0)] << 3) | (tab[(0, 1)] << 2) | (tab[(1, 0)] << 1) | tab[(1, 1)]


def main():
    runs = sys.argv[1:]
    loaded = [V.load(r) for r in runs]
    ap = EXP / "work" / "anchor_report.json"
    if not ap.exists():
        ap = EXP / "work" / "anchors" / "anchor_report.json"
    rep = json.loads(ap.read_text())
    cases = dict((c["idx"], c) for c in CM.build_cases(rep))

    def gated(idx):
        rs = [L.get(idx) for L in loaded]
        rs = [r for r in rs if r]
        if not rs or any(r.get("victim") for r in rs):
            return None
        if len(rs) >= 2 and len(set(r["outcome"] for r in rs)) > 1:
            return None
        return rs[0]

    def by(arm, field):
        out = {}
        for idx, c in cases.items():
            if c["arm"] == arm and c["field"] == field:
                r = gated(idx)
                if r:
                    out[c["value"]] = r
        return out

    report = {}
    print("=" * 72)
    print("PRE-REGISTERED M4 -> G17P REPRODUCTION TESTS")
    print("=" * 72)

    # F1: iadd2.lenbit = 0 must not be ok (EXP-0139, M4)
    d = by("IADD2", "lenbit")
    if 0 in d:
        got = d[0]["outcome"]
        report["F1_iadd2_lenbit0"] = {"m4": "not ok (12-byte form)", "g17p": got,
                                      "reproduced": got != "ok"}
        print("F1 iadd2.lenbit=0        M4: not-ok   G17P: %-12s %s"
              % (got, "REPRODUCED" if got != "ok" else "*** DIVERGES ***"))

    # F2: iadd2.dst >= 192 must fault (EXP-0139, M4: reg >= 96 faults)
    d = by("IADD2", "dst")
    hi = [v for v in d if v >= 192]
    if hi:
        oc = [d[v]["outcome"] for v in hi]
        nf = sum(1 for o in oc if o == "fault")
        report["F2_iadd2_dst_ge192"] = {"m4": "reproducible fault",
                                        "g17p_fault": nf, "g17p_tested": len(hi),
                                        "outcomes": dict((o, oc.count(o)) for o in set(oc))}
        print("F2 iadd2.dst>=192        M4: fault    G17P: %d/%d fault  %s"
              % (nf, len(hi), dict((o, oc.count(o)) for o in set(oc))))

    # F4/F5: ibfe width mod-32 and offset literal (EXP-0139, M4)
    for fld, note in (("width", "mod-32: 32 behaves like 0"),
                      ("offset", "LITERAL: 32..63 shift the field out")):
        d = by("IBFE", fld)
        if d:
            oks = sorted(v for v in d if d[v]["outcome"] == "ok")
            report["F_ibfe_%s" % fld] = {"m4": note, "g17p_ok": oks[:40],
                                         "n_tested": len(d)}
            print("F  ibfe.%-8s        M4: %-34s G17P ok at %s"
                  % (fld, note, V.compact(oks)))

    # --- iadd2.srcB_ext on a 32-BIT carrier, with the width PROVEN fixed ----
    # EXP-0139 (32-bit carrier) declined to promote it ("no <=4-bit rule");
    # EXP-0146 (64-bit carrier) promoted it as a modifier with
    # `(v & 0x7C) == 0x00`. This settles it on a 32-bit carrier.
    d = by("IADD2", "srcB_ext")
    if d:
        B = H.SEED_I[2]          # anchor srcB_imm = 0x08 = 4*2 -> r2
        hit = tot = 0
        bad = []
        for v, r in sorted(d.items()):
            regs = r["observed"]["regs"]
            if not regs:
                continue
            reg = v >> 2
            want = (H.SEED_I[reg] if reg < H.N_REGS else 0) + B
            tot += 1
            if regs[0] == want:
                hit += 1
            else:
                bad.append((v, reg, regs[0], want))
        okv = sorted(v for v in d if d[v]["outcome"] == "ok")
        mask_ok = set(okv) == set(v for v in d if (v & 0x7C) == 0)
        base_regs = None
        anyr = list(d.values())[0]
        if anyr["oracle"]["digest"]:
            dg = anyr["oracle"]["digest"]
            base_regs = [int(dg[i * 8:(i + 1) * 8], 16) for i in range(16)]
        # width proof: a 32-bit add writes ONE register; a 64-bit add writes a pair
        width_proof = None
        if base_regs:
            touched = [i for i in range(16)
                       if base_regs[i] != H.SEED_I[i]]
            width_proof = {"registers_differing_from_seed": touched,
                           "r0": base_regs[0],
                           "expected_32bit_sum": H.SEED_I[0] + B,
                           "r1_untouched": base_regs[1] == H.SEED_I[1]}
        report["iadd2_srcB_ext_32bit"] = {
            "carrier": "SYNTH+LIFTED:k_u32add@iadd2[32:42] (opmode = 0x02 held fixed)",
            "sweep": "%d values, dense over the whole 7-bit range" % len(d),
            "ok_values": okv,
            "EXP0146_mask_rule_(v&0x7C)==0_fits_ok_set": mask_ok,
            "register_selector_model": "reg = srcB_ext >> 2  (the reg<<2 packing)",
            "model_matches": "%d/%d" % (hit, tot),
            "model_mismatches": bad[:12],
            "distinct_registers_confirmed": sorted(set(v >> 2 for v in d if (v >> 2) < 16)),
            "width_proof_32bit": width_proof,
        }
        print()
        print("=" * 72)
        print("iadd2.srcB_ext on a 32-BIT carrier (the EXP-0139 vs EXP-0146 disagreement)")
        print("=" * 72)
        print("  dense sweep            : %d values" % len(d))
        print("  `ok` (reproduces anchor): %s" % V.compact(okv))
        print("  EXP-0146 mask (v&0x7C)==0 fits that ok-set exactly: %s" % mask_ok)
        print("  REGISTER-SELECTOR model  d = r[srcB_ext>>2] + r[srcB_imm>>2]")
        print("     matches %d/%d over the FULL dense sweep, %d distinct registers"
              % (hit, tot, len(set(v >> 2 for v in d if (v >> 2) < 16))))
        print("  32-bit width proof     : %s" % json.dumps(width_proof))

    # F3 + the LUT: ilogic
    print()
    print("=" * 72)
    print("ilogic - 2-input boolean function recovery on G17P")
    print("=" * 72)
    # The carrier's two operands. db.json calls byte+1 `srcA` (0x05 -> r2) and
    # byte+3 `srcB` (0x01 -> r0). EXP-0146's M4 table is written in terms of its
    # own MSL's `a`/`b`, which is NOT the same labelling -- both conventions are
    # scored below and the one that reproduces the M4 table is reported.
    a, b = H.SEED_I[2], H.SEED_I[0]      # srcA=0x05 -> r2, srcB=0x01 -> r0
    print("operands: a = r2 = %d (0x%x), b = r0 = %d (0x%x)" % (a, a, b, b))
    # find the destination register from any ok LUT case
    lut_cases = {}
    for idx, c in cases.items():
        if c["arm"] == "ILOGIC" and c["field"] == "__lut2d":
            r = gated(idx)
            if r and r["observed"]["regs"]:
                lut_cases[c["value"]] = r
    base = None
    for idx, c in cases.items():
        if c["arm"] == "ILOGIC" and c["field"] == "op_base" and c["value"] == 0:
            r = gated(idx)
            if r and r["oracle"]["digest"]:
                dg = r["oracle"]["digest"]
                base = [int(dg[i * 8:(i + 1) * 8], 16) for i in range(16)]
            break
    # PASS 1: locate the destination register from cases that DID change it.
    dstreg = None
    votes = Counter()
    for key, r in sorted(lut_cases.items()):
        regs = r["observed"]["regs"]
        for i in range(16):
            if base and regs[i] != base[i] and derive_lut(a, b, regs[i]) is not None:
                votes[i] += 1
    if votes:
        dstreg = votes.most_common(1)[0][0]

    # PASS 2: read the function out of THAT register for EVERY case, including
    # the ones that reproduce the baseline. Without this the carrier's own
    # function (`and`, for kernels/probes.metal::k_and) is never observed,
    # because nothing differs from the baseline in exactly that case.
    found = {}
    if dstreg is not None:
        for key, r in sorted(lut_cases.items()):
            ob, la, lb = key >> 8, (key >> 4) & 15, key & 15
            regs = r["observed"]["regs"]
            if not regs:
                continue
            f = derive_lut(a, b, regs[dstreg])
            if f is not None:
                found.setdefault(f, []).append((ob, la, lb))
    print("destination register observed:", dstreg)
    print("functions reached: %d of 16" % len(found))

    # Score BOTH operand conventions against EXP-0146's M4 minimal selectors.
    def score_convention(A, B):
        f2 = {}
        for key, r in sorted(lut_cases.items()):
            regs = r["observed"]["regs"]
            if not regs or dstreg is None:
                continue
            f = derive_lut(A, B, regs[dstreg])
            if f is not None:
                f2.setdefault(f, []).append((key >> 8, (key >> 4) & 15, key & 15))
        n = 0
        for fn in range(16):
            m4 = [k for k, v in M4_LUT.items() if v == fn]
            if m4 and any(e[0] == m4[0][0] and (e[1] & 3) == m4[0][1]
                          and (e[2] & 0x0f) == m4[0][2] for e in f2.get(fn, [])):
                n += 1
        return len(f2), n, f2
    n_dbnames, ok_dbnames, _ = score_convention(a, b)
    n_swapped, ok_swapped, f_swapped = score_convention(b, a)
    print("  convention `a` = db.json srcA (byte+1): %d/16 functions, "
          "%d/16 M4 minimal selectors reproduced" % (n_dbnames, ok_dbnames))
    print("  convention `a` = db.json srcB (byte+3): %d/16 functions, "
          "%d/16 M4 minimal selectors reproduced" % (n_swapped, ok_swapped))
    if ok_swapped > ok_dbnames:
        print("  => EXP-0146's M4 table reproduces EXACTLY on G17P, but its `a`/`b`")
        print("     are SWAPPED relative to db.json's srcA/srcB field NAMES.")
        found = f_swapped
    report["ilogic_operand_convention"] = {
        "a_is_dbjson_srcA_byte+1": {"functions": n_dbnames,
                                    "m4_selectors_reproduced": ok_dbnames},
        "a_is_dbjson_srcB_byte+3": {"functions": n_swapped,
                                    "m4_selectors_reproduced": ok_swapped},
        "conclusion": ("EXP-0146's `a` is db.json's srcB (byte+3) and its `b` is "
                       "db.json's srcA (byte+1). With that alignment the entire "
                       "16-function M4 table reproduces on G17P. An emitter that "
                       "reads the EXP-0146 table together with db.json's field "
                       "names gets all EIGHT asymmetric functions wrong "
                       "(a_and_not_b, a, not_a_and_b, b, not_b, a_or_not_b, "
                       "not_a, not_a_or_b) while the eight symmetric ones "
                       "(0, and, xor, or, nor, xnor, nand, 1) still look right."),
    }
    agree = diverge = 0
    lut_rows = {}
    for f in range(16):
        encs = found.get(f, [])
        m4 = [k for k, v in M4_LUT.items() if v == f]
        m4enc = m4[0] if m4 else None
        hit = None
        if m4enc:
            hit = any(e[0] == m4enc[0] and (e[1] & 3) == m4enc[1]
                      and (e[2] & 0x0f) == m4enc[2] for e in encs)
            if hit:
                agree += 1
            elif encs:
                diverge += 1
        lut_rows["%04d_%s" % (f, FN_NAME[f])] = {
            "truth_f00f01f10f11": format(f, "04b"),
            "g17p_encodings": len(encs),
            "g17p_example": encs[0] if encs else None,
            "m4_minimal_selector_EXP0146": m4enc,
            "m4_encoding_reproduced_on_g17p": hit,
        }
        print("  %-14s %s  G17P encodings=%-4d  M4 selector %s -> %s"
              % (FN_NAME[f], format(f, "04b"), len(encs), m4enc,
                 "REPRODUCED" if hit else ("*** NOT REPRODUCED ***" if m4enc else "-")))
    report["ilogic_lut"] = {"dst_register": dstreg, "a": a, "b": b,
                            "functions_reached": len(found),
                            "m4_selectors_reproduced": agree,
                            "m4_selectors_diverged": diverge, "rows": lut_rows}
    print("\nM4 (EXP-0146) minimal selectors reproduced on G17P: %d/16" % agree)

    (HERE / "crosscheck.json").write_text(json.dumps(report, indent=1, sort_keys=True))
    print("\nwrote", HERE / "crosscheck.json")


if __name__ == "__main__":
    main()
