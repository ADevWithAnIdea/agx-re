#!/usr/bin/env python3
"""EXP-0162 analysis of the three compute arms (G17P run01).

Reads only raw/*/sweep.jsonl (append-only evidence) and derives:
  * the bf16 rounding verdict, per competing model, per semantic vector;
  * the per-byte accepted-value rules for all 18 previously-untested fields;
  * the dst register map for the three `dst` fields EXP-0144 left untested.
No GPU is consulted.
"""
import collections, json, sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
RAW = EXP / "raw"


def load(arm, run="g17p_20260829_run01"):
    p = RAW / ("%s__%s" % (run, arm)) / "sweep.jsonl"
    return [json.loads(l) for l in open(p)]


def byte_rules(recs, byte_index):
    """Return (accepted_values, outcome histogram) for one swept byte."""
    ok, hist = [], collections.Counter()
    for d in recs:
        if d.get("kind") != "sweep" or d.get("byte") != byte_index:
            continue
        hist[d["outcome"]] += 1
        if d["outcome"] == "ok":
            ok.append(d["value"])
    return sorted(ok), dict(hist)


def bitrule(vals, width=8):
    """Smallest fixed-bit description that exactly covers `vals` over 0..255,
    or None if the set is not a fixed-bits/don't-care set."""
    if not vals:
        return None
    s = set(vals)
    ones = (1 << width) - 1
    for v in s:
        ones &= v
    zeros = (1 << width) - 1
    for v in s:
        zeros &= (~v) & ((1 << width) - 1)
    fixed = ones | zeros
    ref = next(iter(s))
    cover = [v for v in range(1 << width) if (v & fixed) == (ref & fixed)]
    if set(cover) == s:
        return {"fixed_mask": "0x%02x" % fixed, "fixed_value": "0x%02x" % (ref & fixed),
                "n": len(s), "exact": True}
    return {"fixed_mask": "0x%02x" % fixed, "fixed_value": "0x%02x" % (ref & fixed),
            "n": len(s), "exact": False,
            "note": "accepted set is NOT a fixed-bits set; %d values covered by the mask"
                    % len(cover)}


def main():
    out = {}

    # ---------------- Arm A: cvt_bf16 ------------------------------------
    a = load("cvt_bf16")
    sem = [d for d in a if d.get("kind") == "semantic"]
    models = collections.Counter()
    per_model_fail = collections.defaultdict(list)
    for d in sem:
        for m, ok in d["models"].items():
            if ok:
                models[m] += 1
            else:
                per_model_fail[m].append({"vec_index": d["value"], "v0": d["vec"][0],
                                          "observed_bf16": "0x%04x" % (d["observed"]["w"][0] & 0xFFFF)
                                          if d["observed"]["w"] else None,
                                          "outcome": d["outcome"]})
    out["bf16_rounding"] = {
        "vectors": len(sem),
        "model_pass_counts": dict(models),
        "refuters_per_model": {m: v for m, v in per_model_fail.items()},
        "verdict": ("RNE" if models.get("RNE") == len(sem) else "NOT-RNE"),
    }

    # ---------------- byte rules for all three arms ----------------------
    FIELDS = {
      "cvt_bf16":        {0: "dst(byte0 hi nibble)", 1: "srcw", 2: "opsel", 3: "src",
                          4: "fmt", 5: "b5", 6: "dir", 7: "b7"},
      "cvt_f2h_dst":     {0: "dst(byte0 hi nibble)", 1: "srcfmt", 2: "opsel", 3: "src",
                          4: "dhalf", 5: "tail"},
      "packed_half2_hi": {0: "dst(byte0 hi nibble)", 1: "srcA", 2: "opsel", 3: "srcB",
                          4: "mods[7:0]", 5: "mods[15:8]"},
    }
    out["byte_rules"] = {}
    for arm, fmap in FIELDS.items():
        recs = load(arm)
        arm_out = {}
        for bi, fname in fmap.items():
            if bi == 0:
                dstv = [d for d in recs if d.get("kind") == "sweep" and d["field"] == "dst"]
                lonib = [d for d in recs if d.get("kind") == "sweep"
                         and d["field"] == "byte0_lonib"]
                # which output slot changed, per high-nibble value
                slots = {}
                for d in dstv:
                    w = d["observed"]["w"]
                    slots[d["value"] >> 4] = {"outcome": d["outcome"], "w": w[:6]}
                arm_out[fname] = {
                    "coverage": "byte0 high nibble dense 0..15 (low nibble held at anchor)",
                    "per_value": slots,
                    "outcomes": dict(collections.Counter(d["outcome"] for d in dstv)),
                    "byte0_low_nibble_offmatch": {("0x%02x" % d["value"]): d["outcome"]
                                                  for d in lonib},
                }
                continue
            ok, hist = byte_rules(recs, bi)
            arm_out[fname] = {"byte": bi, "n_ok": len(ok), "outcomes": hist,
                              "accepted": ["0x%02x" % v for v in ok][:64],
                              "bit_rule": bitrule(ok)}
        out["byte_rules"][arm] = arm_out

    # ---------------- Arm B: the packed_half2_hi synthesis ----------------
    b = load("packed_half2_hi")
    bsem = [d for d in b if d.get("kind") == "semantic"]
    out["packed_half2_hi_synthesis"] = {
        "vectors": [{"vec_index": d["value"],
                     "hi_expect": "0x%04x" % d["ph2_hi_expect"],
                     "hi_observed": ("0x%04x" % d["ph2_hi_observed"])
                                    if d["ph2_hi_observed"] is not None else None,
                     "lo_expect_if_both": "0x%04x" % d["ph2_lo_expect"],
                     "lo_observed": ("0x%04x" % d["ph2_lo_observed"])
                                    if d["ph2_lo_observed"] is not None else None,
                     "hi_lane_correct": d["hi_lane_correct"],
                     "both_lanes_correct": d["both_lanes_correct"],
                     "hi_only_zero_low": d["hi_only_zero_low"],
                     "hi_only_poison_low": d["hi_only_poison_low"]}
                    for d in bsem],
    }
    v = out["packed_half2_hi_synthesis"]["vectors"]
    out["packed_half2_hi_synthesis"]["verdict"] = (
        "HIGH-LANE-ONLY, low lane written as ZERO"
        if v and all(x["hi_lane_correct"] and x["hi_only_zero_low"] for x in v)
        else "NOT high-lane-only" if v and any(x["both_lanes_correct"] for x in v)
        else "INCONCLUSIVE")

    # ---------------- Arm C: cvt_f2h_dst semantics ------------------------
    c = load("cvt_f2h_dst")
    csem = [d for d in c if d.get("kind") == "semantic"]
    out["cvt_f2h_dst_semantics"] = {"vectors": len(csem),
                                    "all_match_ieee_rne": all(d["outcome"] == "ok" for d in csem),
                                    "outcomes": dict(collections.Counter(d["outcome"] for d in csem))}

    # ---------------- health --------------------------------------------
    out["health"] = {}
    for arm in FIELDS:
        recs = load(arm)
        bl = [d for d in recs if d.get("kind") == "baseline"]
        done = [d for d in recs if d.get("kind") == "done"]
        out["health"][arm] = {
            "baselines": len(bl), "baselines_ok": sum(1 for d in bl if d["outcome"] == "ok"),
            "cases": done[0]["cases"] if done else None,
            "elapsed_s": done[0]["elapsed_s"] if done else None,
            "hangs": done[0]["hangs"] if done else None,
            "outcomes": dict(collections.Counter(d["outcome"] for d in recs
                                                 if d.get("kind") == "sweep")),
            "total_discarded_victim_or_sentinel":
                sum(d.get("discarded", 0) for d in recs if "discarded" in d),
        }

    print(json.dumps(out, indent=1))


main()
