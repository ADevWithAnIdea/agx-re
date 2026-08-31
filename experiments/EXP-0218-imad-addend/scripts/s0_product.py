#!/usr/bin/env python3
"""EXP-0218 step 0 — re-derive (do not assume) the product map on C-G17P.

P = SEED[b5>>2] * SEED[b6>>3], with byte+6 bit0 forcing that source to read 0.
Scored on the populations this experiment will later use as the subtrahend, i.e.
every case whose byte+5 and byte+6 are at the anchor, plus the byte+5 and byte+6
sweeps themselves.  Exact numerators and denominators only.
"""
from __future__ import annotations
import sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0218 import POISON as POISON_G  # 0xDEADBEEF
from lib0218 import (cases_g17p, SEEDS, ANCHOR_G17P, swept_byte, dump, M32)

AN = bytes.fromhex(ANCHOR_G17P)


def prod(raw, seeds):
    i5, i6 = raw[5] >> 2, raw[6] >> 3
    if i5 > 15 or i6 > 15:
        return None
    a = seeds[i5]
    b = 0 if (raw[6] & 1) else seeds[i6]
    return (a * b) & M32


def mode(raw):
    return raw[7] & 3


def main():
    out = {}
    # ---- 0a. anchor-product populations: b5,b6 at anchor, b7 mode 0 --------
    pops = defaultdict(lambda: {"scored": 0, "excluded": Counter(),
                                "hit_P_plus_A_const": 0, "distinct_obs": set()})
    # ---- 0b. the byte+5 / byte+6 sweeps: does the product map reproduce the
    #          destination once the (single, per-K) addend is known?
    # addend for the anchor byte+7 (0x60) is measured, not assumed: take it from
    # the mode 1/2 cases of the same K in the same seed set.
    A_meas = {}
    Kanchor = (AN[7] >> 3) & 0x1F
    for c in cases_g17p():
        raw = c["raw"]
        if c["excl"]:
            continue
        if swept_byte(raw, ANCHOR_G17P) != (7,):
            continue
        if ((raw[7] >> 3) & 0x1F) != Kanchor:
            continue
        if mode(raw) in (1, 2):
            dst = raw[3] >> 1
            A_meas.setdefault((c["sset"], Kanchor), Counter())[c["regs"][dst]] += 1
    out["anchor_addend_measured_from_mode12"] = {
        f"sset{k[0]}_K{k[1]}": dict(v) for k, v in A_meas.items()}

    A_by_sset = {}
    for (ss, k), cnt in A_meas.items():
        vals = list(cnt)
        A_by_sset[ss] = vals[0] if len(vals) == 1 else None
    out["anchor_addend"] = A_by_sset

    # score P on every population
    scores = defaultdict(lambda: {"n": 0, "in_domain": 0, "hit": 0,
                                  "excluded": Counter(), "misses": []})
    for c in cases_g17p():
        raw = c["raw"]
        sb = swept_byte(raw, ANCHOR_G17P)
        key = "byte" + ",".join(str(x) for x in sb) if sb else "anchor"
        S = scores[key]
        if c["excl"]:
            S["excluded"][c["excl"]] += 1
            continue
        if mode(raw) != 0:
            S["excluded"]["b7_mode_drops_product"] += 1
            continue
        seeds = SEEDS[c["sset"]]
        P = prod(raw, seeds)
        S["n"] += 1
        if P is None:
            S["excluded"]["multiplicand_index_out_of_seed_table"] += 1
            continue
        A = A_by_sset.get(c["sset"])
        Kh = (raw[7] >> 3) & 0x1F
        if A is None or Kh != Kanchor:
            S["excluded"]["addend_not_measured_for_this_K"] += 1
            continue
        S["in_domain"] += 1
        dst = raw[3] >> 1
        if dst > 15:
            S["excluded"]["dst_out_of_dump"] += 1
            S["in_domain"] -= 1
            continue
        got = c["regs"][dst]
        if got == POISON_G:
            S["excluded"]["destination_still_poison"] += 1
            S["in_domain"] -= 1
            continue
        if ((P + A) & M32) == got:
            S["hit"] += 1
        elif len(S["misses"]) < 6:
            S["misses"].append({"hex": c["hex"], "sset": c["sset"], "P": P,
                                "A": A, "pred": (P + A) & M32, "got": got,
                                "src": c["src"]})
    out["product_model_scores"] = {k: {"n_cases": v["n"],
                                       "in_domain": v["in_domain"],
                                       "hit": v["hit"],
                                       "excluded": dict(v["excluded"]),
                                       "first_misses": v["misses"]}
                                   for k, v in sorted(scores.items())}
    dump(out, "s0_product.json")
    print("anchor addend per seed set:", A_by_sset, " (K =", Kanchor, ")")
    for k, v in sorted(scores.items()):
        print(f"  {k:14s} cases={v['n']:5d} in_domain={v['in_domain']:5d} "
              f"P*+A hits={v['hit']:5d}  excl={dict(v['excluded'])}")


if __name__ == "__main__":
    main()
