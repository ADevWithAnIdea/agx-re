#!/usr/bin/env python3
"""EXP-0219 desk step B0: characterise tex_sample.mode instability OFFLINE
from EXP-0213's three committed quiet orders (B1 forward, B2 reverse,
B3 shuffle213), before any dispatch.

Reads ONLY committed raw. Writes nothing into raw/.
"""
import json, sys, collections
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
RAW = EXP.parents[0] / "EXP-0204-g17p-tex-carrier-dimensions" / "raw"

ORDERS = ["g17p_e0213_B1", "g17p_e0213_B2", "g17p_e0213_B3"]
ARMS = ["tex_sample_mscmp_0", "tex_sample_mscmp_1", "tex_sample_msfilt_0",
        "tex_sample_msfixl_0", "tex_sample_msfixl_1", "tex_sample_msgath_0",
        "tex_sample_mslodq_0", "tex_sample_mslodq_1",
        "tex_sample_msread_0", "tex_sample_msread_1"]

def load(rid, arm):
    p = RAW / ("%s_%s" % (rid, arm)) / "sweep.jsonl"
    if not p.exists():
        return None
    return [json.loads(l) for l in p.open()]

out = {}
for arm in ARMS:
    per = {}
    for o in ORDERS:
        recs = load(o, arm)
        if recs is None:
            per[o] = None
            continue
        d = {}
        for r in recs:
            if r.get("field") != "mode":
                continue
            d[r["value"]] = r
        per[o] = d
    if any(v is None for v in per.values()):
        out[arm] = {"error": "missing order"}
        continue
    vals = sorted(set().union(*[set(v.keys()) for v in per.values()]))
    unstable = []
    for v in vals:
        payloads = []
        for o in ORDERS:
            r = per[o].get(v)
            payloads.append(json.dumps(r["observed"].get("probe"), sort_keys=True) if r else None)
        if len(set(payloads)) > 1:
            outc = [per[o][v]["outcome"] for o in ORDERS]
            unstable.append({"value": v, "outcomes": outc,
                             "n_distinct": len(set(payloads))})
    # bit statistics over unstable values
    bits = collections.Counter()
    for u in unstable:
        for b in range(8):
            if u["value"] >> b & 1:
                bits[b] += 1
    out[arm] = {"n_values": len(vals), "n_unstable": len(unstable),
                "unstable_values": [u["value"] for u in unstable],
                "bit_counts_among_unstable": dict(sorted(bits.items())),
                "outcomes": collections.Counter(
                    tuple(u["outcomes"]) for u in unstable).most_common()}

# cross-arm: is bit6 necessary AND sufficient?
summary = {}
for arm, d in out.items():
    if "unstable_values" not in d:
        continue
    uv = set(d["unstable_values"])
    b6 = set(v for v in range(256) if v & 0x40)
    summary[arm] = {
        "n_unstable": len(uv),
        "all_have_bit6": all(v & 0x40 for v in uv),
        "frac_of_bit6_set_unstable": "%d/%d" % (len(uv & b6), len(b6)),
        "unstable_without_bit6": sorted(uv - b6),
    }
print(json.dumps({"per_arm": out, "summary": summary}, indent=1))
