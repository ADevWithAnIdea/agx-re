#!/usr/bin/env python3
"""EXP-0165: independent re-derivation of DEF-0160-1 (falu3/falu3_ext `op`),
DEF-0160-2 (iminmax operand slots) and DEF-0160-4 (half_pack length) from
EXP-0160's immutable raw sweeps.  EXP-0160's own verdicts are not read."""
from __future__ import print_function
import collections, json, struct
from pathlib import Path

E160 = Path(__file__).resolve().parents[2] / "EXP-0160-g17p-last-field"
SI = {1: [10, 21, 34, 47, 58, 65, 71, 83, 94, 101, 113, 119, 125, 127, 3, 0],
      2: [7, 13, 19, 29, 37, 43, 53, 61, 73, 79, 89, 97, 103, 109, 5, 0]}
SF = {1: [5.0, 1.5, 3.0, 0.5, 7.0, 9.0, 11.0, 13.0, 0.25, 18.0, 22.0, 26.0,
          30.0, 0.75, 0.0, 0.0],
      2: [0.25, 0.875, 0.375, 1.75, 0.5, 12.0, 14.0, 16.0, 0.125, 20.0, 24.0,
          28.0, 6.0, 2.5, 0.0, 0.0]}
M32 = 0xFFFFFFFF


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & M32))[0]


def rows(arm, field):
    out = []
    for run in ("g17p_20260830_run01", "g17p_20260830_run02"):
        for l in (E160 / "raw" / run / "sweep.jsonl").open():
            r = json.loads(l)
            if r.get("arm") == arm and r.get("field") == field:
                r["_run"] = run
                out.append(r)
    return out


def exact_masks(acc, rej):
    out = []
    for m in range(256):
        w = {v & m for v in acc}
        if len(w) != 1:
            continue
        w = w.pop()
        if any((v & m) == w for v in rej):
            continue
        out.append(("0x%02X" % m, "0x%02X" % w, bin(m).count("1")))
    return sorted(out, key=lambda t: t[2])


def dead_bits(recs):
    """Bits b such that flipping ONLY b never changes the observed register dump."""
    by = {}
    for r in recs:
        o = (r.get("observed") or {}).get("regs")
        if o:
            by[(r["sset"], r["value"])] = tuple(o)
    dead = []
    for b in range(8):
        same = diff = 0
        for (s, v), o in by.items():
            o2 = by.get((s, v ^ (1 << b)))
            if o2 is None:
                continue
            (same if o == o2 else diff).__int__()
            if o == o2:
                same += 1
            else:
                diff += 1
        dead.append({"bit": b, "pairs_same": same, "pairs_diff": diff,
                     "inert": diff == 0 and same > 0})
    return dead


def reg_map_fit(recs, shift, mask):
    """Does `reg = (v >> shift) & mask` explain WHICH seed the result names?
    Scored on the float min/max carrier by matching r0 to min(seed[x], other)."""
    hits = collections.Counter()
    for r in recs:
        o = (r.get("observed") or {}).get("regs")
        if not o:
            continue
        s = r["sset"]
        got = f32(o[0])
        want_reg = (r["value"] >> shift) & mask
        if want_reg > 15:
            continue
        hits["n"] += 1
        if abs(got - min(SF[s][0], SF[s][want_reg])) < 1e-6:
            hits["min_with_r0"] += 1
        if abs(got - SF[s][want_reg]) < 1e-6:
            hits["equals_that_seed"] += 1
    return dict(hits)


def main():
    rep = {}

    # ------------- DEF-0160-1 : falu3 / falu3_ext `op` ---------------------
    for arm, ins in (("F3_OP", "falu3"), ("F3E_OP", "falu3_ext")):
        rs = rows(arm, "op")
        acc = sorted({r["value"] for r in rs if r["outcome"] == "ok"})
        rej = sorted({r["value"] for r in rs} - set(acc))
        # per-value function identification, required to agree in BOTH seed sets
        obs = collections.defaultdict(dict)
        for r in rs:
            o = (r.get("observed") or {}).get("regs")
            if o:
                obs[r["value"]][r["sset"]] = f32(o[0])
        blk = bytes.fromhex(rs[0]["bytes"])
        # anchor operand registers: falu3 srcA=byte+1, srcB=byte+3, srcC=byte+5,
        # each packed (reg<<1)|is32 (db.json's own committed model)
        a, b, c = blk[1] >> 1, blk[3] >> 1, blk[5] >> 1
        FN = {"a+b": lambda A, B, C: A + B, "a*b": lambda A, B, C: A * B,
              "a*b+a": lambda A, B, C: A * B + A, "a*b+c": lambda A, B, C: A * B + C,
              "-b": lambda A, B, C: -B, "0": lambda A, B, C: 0.0,
              "a": lambda A, B, C: A, "b": lambda A, B, C: B,
              "c": lambda A, B, C: C, "a+c": lambda A, B, C: A + C}
        fn_of = {}
        for v, d in sorted(obs.items()):
            if set(d) != {1, 2}:
                continue
            names = []
            for nm, f in FN.items():
                ok = all(abs(d[s] - f(SF[s][a], SF[s][b], SF[s][c]))
                         <= 1e-5 * max(1.0, abs(f(SF[s][a], SF[s][b], SF[s][c])))
                         for s in (1, 2))
                if ok:
                    names.append(nm)
            fn_of[v] = names
        by_opsel = collections.defaultdict(set)
        for v, names in fn_of.items():
            by_opsel[v & 7].add(tuple(sorted(names)))
        rep["%s.op" % ins] = {
            "anchor": rs[0]["bytes"], "srcA_reg": a, "srcB_reg": b, "srcC_reg": c,
            "accepted": acc, "exact_masks": exact_masks(acc, rej),
            "function_by_low3_bits": {k: sorted(map(list, v))
                                      for k, v in sorted(by_opsel.items())},
            "faults": sorted({r["value"] for r in rs
                              if r["outcome"] in ("fault", "hang")}),
            "dead_bits": dead_bits(rs)}

    # ------------- DEF-0160-2 : iminmax byte+5 ------------------------------
    rs = rows("IMINMAX_SRCB", "srcB")
    acc = sorted({r["value"] for r in rs if r["outcome"] == "ok"})
    rej = sorted({r["value"] for r in rs} - set(acc))
    blk = bytes.fromhex(rs[0]["bytes"])
    rep["iminmax.byte+5"] = {
        "anchor": rs[0]["bytes"],
        "accepted": acc, "exact_masks": exact_masks(acc, rej),
        "dead_bits": dead_bits(rs),
        "reg_map_v_shr_1": reg_map_fit(rs, 1, 0x3F),
        "reg_map_v_shr_2": reg_map_fit(rs, 2, 0x3F),
        "reg_map_v_raw": reg_map_fit(rs, 0, 0x0F),
        "baseline_is_min_of_r0_r2": None}
    # is the unmutated result min(seed[0], seed[2])?
    for r in rs:
        if r["outcome"] != "ok":
            continue
        o = (r.get("observed") or {}).get("regs")
        if o:
            s = r["sset"]
            rep["iminmax.byte+5"]["baseline_is_min_of_r0_r2"] = (
                abs(f32(o[0]) - min(SF[s][0], SF[s][2])) < 1e-6)
            rep["iminmax.byte+5"]["baseline_r0"] = f32(o[0])
            rep["iminmax.byte+5"]["min_r0_r2"] = min(SF[s][0], SF[s][2])
            rep["iminmax.byte+5"]["anchor_byte1"] = blk[1]
            rep["iminmax.byte+5"]["anchor_byte3"] = blk[3]
            break

    # ------------- DEF-0160-4 : half_pack splice controls -------------------
    ctl = {}
    for f in ("__split_at0_r6", "__split_at2_r6", "__split_at2_r7",
              "__split_at0and2", "__falsifier_byte0"):
        for r in rows("HALFPACK_SRC", f):
            ctl.setdefault(f, []).append(
                {"sset": r["sset"], "bytes": r["bytes"], "outcome": r["outcome"],
                 "r6": (r.get("observed") or {}).get("regs", [None] * 8)[6],
                 "r7": (r.get("observed") or {}).get("regs", [None] * 8)[7]})
    rep["half_pack.splice_controls"] = ctl
    hp = rows("HALFPACK_SRC", "src")
    rep["half_pack.byte+2"] = {"dead_bits": dead_bits(hp),
                               "accepted": sorted({r["value"] for r in hp
                                                   if r["outcome"] == "ok"})}
    print(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
