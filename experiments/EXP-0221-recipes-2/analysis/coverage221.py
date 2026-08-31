#!/usr/bin/env python3
"""EXP-0221 per-field coverage -- exact numerators and denominators.

FIELD-SWEEP-PROTOCOL section 5: "For every finite domain, report exact
numerators and denominators: encodable values, dispatched values, distinct
actual encodings, legal values, silent/no-effect values, faults, hangs, aliases,
and untested values.  Never report only a percentage."

For every densely swept field this also compares G17P's measured accepted set
with EXP-0141's M4 accepted set -- the PRE-REGISTERED cross-target prediction
(H5) -- and names every value where the two targets disagree.  Reads only
committed raw.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
RUN01 = "g17p-20260831-run01"
RUN02 = "g17p-20260831-run02"

# arm -> (instruction, field, encodable domain size, the EXP-0141 key)
ARMS = {
    "L1-access_desc": ("device_load", "access_desc", 256, "device_load.access_desc"),
    "L1-addr_mode": ("device_load", "addr_mode", 256, "device_load.addr_mode"),
    "L1-reserved7": ("device_load", "reserved7", 256, "device_load.reserved7"),
    "L1-reserved13": ("device_load", "reserved13", 256, "device_load.reserved13"),
    "L1-space": ("device_load", "space", 256, "device_load.space"),
    "L1-elem_size": ("device_load", "elem_size", 256, "device_load.elem_size"),
    "L1-ldform_hi11": ("device_load", "ldform_hi11", 64, "device_load.ldform_hi11"),
    "L1-dst_ext9": ("device_load", "dst_ext9", 128, "device_load.dst_ext9"),
    "L1-dst_lo": ("device_load", "dst_lo", 4, "device_load.dst_lo"),
    "L2-extmode": ("device_load", "extmode", 256, "device_load.extmode"),
    "L3-ld_format": ("device_load", "ld_format", 64, "device_load.ld_format"),
    "L4-index_reg": ("device_load", "index_reg", 256, "device_load.index_reg"),
    "L5-base_slot": ("device_load", "base_slot", 256, "device_load.base_slot"),
    "D1-access_desc": ("device_store", "access_desc", 256, "device_store.access_desc"),
    "D1-addr_mode": ("device_store", "addr_mode", 256, "device_store.addr_mode"),
    "D1-reserved7": ("device_store", "reserved7", 256, "device_store.reserved7"),
    "D1-reserved13": ("device_store", "reserved13", 256, "device_store.reserved13"),
    "D1-elem_size": ("device_store", "elem_size", 256, "device_store.elem_size"),
    "D1-st_format_ext": ("device_store", "st_format_ext", 128,
                         "device_store.st_format_ext"),
    "D1-st_desc_hi": ("device_store", "st_desc_hi", 64, "device_store.st_desc_hi"),
    "D2-space": ("device_store", "space", 256, "device_store.space"),
    "D3-extmode": ("device_store", "extmode", 256, "device_store.extmode"),
    "D4-index_reg": ("device_store", "index_reg", 256, "device_store.index_reg"),
    "D5-st_format": ("device_store", "st_format", 256, "device_store.st_format"),
    "S1-stop.reserved": ("stop", "reserved", 1 << 24, None),
}


def rng(vs):
    vs = sorted(vs)
    out = []
    for v in vs:
        if out and v == out[-1][1] + 1:
            out[-1][1] = v
        else:
            out.append([v, v])
    return ",".join("%d" % a if a == b else "%d-%d" % (a, b) for a, b in out)


def load(run):
    p = os.path.join(EXP, "raw", run, "sweep.jsonl")
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def value_of(rec):
    n = rec["name"]
    for i in range(len(n) - 1, -1, -1):
        if not n[i].isdigit():
            tail = n[i + 1:]
            break
    else:
        tail = ""
    if rec["arm"] == "S1-stop.reserved":
        return int(n.split("_")[-1], 16)
    return int(tail) if tail else None


def main():
    A, B = load(RUN01), load(RUN02)
    byname = {c["name"]: c for c in B}
    out = {}
    for arm, (instr, field, dom, k141) in sorted(ARMS.items()):
        rows = [c for c in A if c["arm"] == arm]
        if not rows:
            continue
        vals, ok, hard, wrong, nowrite = [], [], [], [], []
        enc = set()
        agree = 0
        buckets = collections.Counter()
        for c in rows:
            v = value_of(c)
            vals.append(v)
            for u in c.get("under_test", []):
                enc.add(u["bytes"])
            buckets[c["observed_bucket"]] += 1
            good = (c["observed_bucket"] == "exact")
            (ok if good else wrong).append(v)
            if c["outcome"] in ("fault", "hang", "victim"):
                hard.append(v)
            if c["outcome"] == "no_write":
                nowrite.append(v)
            o = byname.get(c["name"])
            if o is not None and o["observed_bucket"] == c["observed_bucket"]:
                agree += 1
        d = {"instruction": instr, "field": field,
             "encodable_domain": dom, "dispatched": len(rows),
             "distinct_requested_values": len(set(vals)),
             "distinct_actual_encodings": len(enc),
             "exact": len(ok), "not_exact": len(wrong),
             "faults_or_hangs": len(hard), "no_write": len(nowrite),
             "untested": dom - len(set(vals)),
             "cross_run_bucket_agreement": agree,
             "accepted_G17P": rng(ok)[:2000],
             "not_accepted_G17P": rng(wrong)[:2000],
             "fault_values": rng(hard)[:600],
             "observed_buckets": dict(buckets),
             # AN ACCEPTANCE COUNT AND AN ORACLE-COVERAGE COUNT ARE NOT THE SAME
             # NUMBER.  Where the host could not predict a value (`unpredicted`)
             # or where this experiment's frozen model was narrower than the
             # field's real behaviour, `exact` counts how much the ORACLE
             # covered, not how much the hardware accepted.  Saying so is the
             # difference between a measurement and a headline.
             "exact_is_acceptance": buckets.get("unpredicted", 0) == 0,
             "unpredicted": buckets.get("unpredicted", 0)}
        if k141:
            E = json.load(open(os.path.join(EXP, "work", "frozen",
                                            "e141_m4_accepted_sets.json")))
            m4 = set(E.get(k141, {}).get("accepted_all_runs_ok") or [])
            g17 = set(ok)
            d["m4_accepted_count"] = len(m4)
            d["g17p_accepted_count"] = len(g17)
            d["accepted_on_M4_not_G17P"] = rng(sorted(m4 - g17))[:800]
            d["accepted_on_G17P_not_M4"] = rng(sorted(g17 - m4))[:800]
            d["H5_cross_target_identical"] = (m4 == g17) if m4 else None
        out[arm] = d
    # arm T, reported on its own terms
    T = collections.defaultdict(lambda: collections.Counter())
    for c in A:
        if not c["arm"].startswith("T"):
            continue
        T[c["arm"]]["cases"] += 1
        if c.get("codeword_arrived"):
            T[c["arm"]]["codeword_arrived"] += 1
        if c["outcome"] in ("fault", "hang"):
            T[c["arm"]][c["outcome"]] += 1
        if c.get("codeword_prediction_ok") is False:
            T[c["arm"]]["prediction_WRONG"] += 1
        if c.get("codeword_prediction_ok") is True:
            T[c["arm"]]["prediction_ok"] += 1
    out["_arm_T"] = {k: dict(v) for k, v in sorted(T.items())}
    json.dump(out, open(os.path.join(HERE, "coverage.json"), "w"), indent=1,
              sort_keys=True)
    print("%-20s %5s %5s %5s %5s %6s  %s" %
          ("arm", "dom", "disp", "enc", "exact", "fault", "M4==G17P"))
    for arm in sorted(k for k in out if not k.startswith("_")):
        d = out[arm]
        print("%-20s %5d %5d %5d %5d %6d  %s" %
              (arm, d["encodable_domain"], d["dispatched"],
               d["distinct_actual_encodings"], d["exact"], d["faults_or_hangs"],
               d.get("H5_cross_target_identical")))
    print()
    for k, v in out["_arm_T"].items():
        print("%-24s %s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
