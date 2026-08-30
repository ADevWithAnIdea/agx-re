#!/usr/bin/env python3
"""EXP-0165: independent re-derivation of DEF-0160-6 / -3 / -7 (imad), solved
from scratch with BOTH multiplicand registers left free.

Model under test:   r0 = m(desc) * (seed[srcA] * seed[srcB]) + A(desc)   mod 2^32
  * srcA is claimed by DEF-0160-6 to be (byte+6) >> 3,
  * A(desc) is claimed by DEF-0160-3 to be seed-INDEPENDENT and selected (not
    carried) by byte+7,
  * byte+8 (`mulsel`) is claimed by DEF-0160-7 not to affect A.

The solver never assumes which register srcB is: it searches all 16x16 register
pairs and both m in {0,1}, and requires the SAME (srcA, srcB, m, A) to satisfy
BOTH seed sets simultaneously.  Nothing is read from EXP-0160's verdicts.
"""
from __future__ import print_function
import collections, json
from pathlib import Path

E160 = Path(__file__).resolve().parents[2] / "EXP-0160-g17p-last-field"
S = {1: [10, 21, 34, 47, 58, 65, 71, 83, 94, 101, 113, 119, 125, 127, 3, 0],
     2: [7, 13, 19, 29, 37, 43, 53, 61, 73, 79, 89, 97, 103, 109, 5, 0]}
M32 = 0xFFFFFFFF


def recs(field):
    out = []
    for run in ("g17p_20260830_run01", "g17p_20260830_run02"):
        for l in (E160 / "raw" / run / "sweep.jsonl").open():
            r = json.loads(l)
            if r.get("arm") == "IMAD_SRCC" and r.get("field") == field:
                r["_run"] = run
                out.append(r)
    return out


def pairs(field, keybytes):
    """{(byte values...) -> {sset: r0}} for cleanly observed cases."""
    by = collections.defaultdict(dict)
    for r in recs(field):
        o = (r.get("observed") or {}).get("regs")
        if not o or r.get("outcome") in ("fault", "hang"):
            continue
        blk = bytes.fromhex(r["bytes"])
        by[tuple(blk[i] for i in keybytes)][r["sset"]] = o[0]
    return {k: v for k, v in by.items() if set(v) == {1, 2}}


def solve(o1, o2):
    """All (m, a, b, A) with r0 = m*seed[a]*seed[b] + A in BOTH seed sets."""
    hits = []
    for m in (0, 1):
        if m == 0:
            if (o1 & M32) == (o2 & M32):
                hits.append((0, None, None, o1 & M32))
            continue
        for a in range(16):
            for b in range(16):
                A1 = (o1 - S[1][a] * S[1][b]) & M32
                A2 = (o2 - S[2][a] * S[2][b]) & M32
                if A1 == A2:
                    hits.append((1, a, b, A1))
    return hits


def main():
    rep = {}
    anc = recs("__falsifier_byte0")
    rep["anchor_bytes"] = anc[0]["bytes"] if anc else None

    # ---------------- DEF-0160-6 : byte+6 -> srcA register -----------------
    tab = pairs("__2d_desc_lo", (6, 7))
    rep["n_2d_desc_lo_points"] = len(tab)
    sol = {k: solve(*[v[1], v[2]]) for k, v in tab.items()}
    rep["n_with_no_solution"] = sum(1 for v in sol.values() if not v)

    # Intersect the (srcA, srcB) candidates over every desc, per `lo` value.
    per_lo = collections.defaultdict(list)
    for (lo, desc), hits in sol.items():
        cand = {(a, b) for (m, a, b, A) in hits if m == 1}
        if cand:
            per_lo[lo].append(cand)
    rule, fits, misses = {}, 0, []
    for lo in sorted(per_lo):
        inter = set.intersection(*per_lo[lo])
        as_ = sorted({a for a, b in inter})
        bs_ = sorted({b for a, b in inter})
        want = lo >> 3
        ok = (want in as_)
        rule["0x%02X" % lo] = {"n_desc_points": len(per_lo[lo]),
                               "srcA_candidates": as_, "srcB_candidates": bs_,
                               "predicted_srcA_reg_lo_shr_3": want,
                               "fits": ok}
        fits += ok
        if not ok:
            misses.append(("0x%02X" % lo, as_, want))
    rep["byte6_srcA_rule_reg_eq_lo_shr_3"] = {
        "fits": fits, "total": len(rule), "misses": misses, "detail": rule}

    # ---------------- DEF-0160-3 : addend is desc-selected, seed-free ------
    add = collections.defaultdict(set)
    for (lo, desc), hits in sol.items():
        for (m, a, b, A) in hits:
            if m == 1 and a == (lo >> 3):
                add[desc].add(A)
    rep["addend_by_srcC_desc"] = {"0x%02X" % d: sorted(v) for d, v in sorted(add.items())}
    rep["addend_is_single_valued_per_desc"] = all(len(v) == 1 for v in add.values())
    rep["addend_is_seed_independent"] = True   # enforced by construction in solve()

    # bits 3..7 select the addend; bits 0,1 the mode; bit 2 inert?
    bit2 = {}
    for d in sorted(add):
        other = d ^ 0x04
        if other in add:
            bit2["0x%02X vs 0x%02X" % (d, other)] = (add[d] == add[other])
    rep["srcC_desc_bit2_inert_pairs"] = bit2
    rep["srcC_desc_bit2_inert"] = all(bit2.values()) if bit2 else None

    # ---------------- DEF-0160-7 : mulsel does not change the addend -------
    mt = pairs("__2d_desc_mul", (6, 7, 8))
    per = collections.defaultdict(lambda: collections.defaultdict(set))
    for (lo, desc, mul), v in mt.items():
        for (m, a, b, A) in solve(v[1], v[2]):
            if m == 1 and a == (lo >> 3):
                per[desc][mul].add(A)
    rep["mulsel_addend_by_desc"] = {
        "0x%02X" % d: {"0x%02X" % k: sorted(x) for k, x in sorted(t.items())}
        for d, t in sorted(per.items())}
    rep["mulsel_does_not_change_addend"] = {
        "0x%02X" % d: len({tuple(sorted(x)) for x in t.values()}) == 1
        for d, t in sorted(per.items())}

    # ---------------- fault rule (v & 3) == 3 ------------------------------
    flt, other = set(), set()
    for r in recs("srcC_desc"):
        (flt if r["outcome"] in ("fault", "hang") else other).add(r["value"])
    rep["srcC_desc_faults"] = {
        "n_fault_values": len(flt),
        "all_faults_have_v_and_3_eq_3": all((v & 3) == 3 for v in flt),
        "no_non_fault_has_v_and_3_eq_3": all((v & 3) != 3 for v in other - flt)}
    print(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
