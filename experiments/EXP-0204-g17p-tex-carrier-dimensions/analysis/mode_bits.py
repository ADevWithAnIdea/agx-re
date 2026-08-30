#!/usr/bin/env python3
"""mode_bits.py -- EXP-0204: which BITS of tex_sample.mode are live?

Derived from raw/ only, using ONLY values whose observation agrees across the two
gated Amendment-2 runs (which were dispatched in OPPOSITE case order), and only on
arms whose per-value cross-run agreement is 100 %.  Everything below is therefore a
REPRODUCIBILITY-FILTERED liveness map, not a semantic claim.

Reported per arm and per bit:
  n_moved / n_total for that bit set vs clear, and whether the moved set is
  EXACTLY described by a boolean rule over the byte's eight bits.

This exists because the PRE-REGISTERED model -- db.json's enum
{0x00 gather/read/compare, 0x10 filtered sample, 0x20 LOD query} -- was REFUTED by
the sweep (see RESULTS.md), and the honest replacement is a bounded bit map plus a
named successor hypothesis, not a re-labelled enum.
"""
import collections, glob, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "harness"))
import arms as ARMSPEC          # noqa: E402


def load(d):
    out = []
    p = os.path.join(d, "sweep.jsonl")
    if os.path.exists(p):
        for line in open(p, errors="replace"):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def payload(r):
    return json.dumps((r.get("observed") or {}).get("hh"), sort_keys=True)


def main():
    runs = sorted(d for d in glob.glob(os.path.join(HERE, "raw", "g17p_*A2run0[12]"))
                  if os.path.isdir(d))
    assert len(runs) == 2, runs
    per = [collections.defaultdict(dict) for _ in runs]
    base = [dict() for _ in runs]
    for i, d in enumerate(runs):
        for r in load(d):
            if r.get("instr") != "tex_sample":
                continue
            if r.get("field") == "_baseline":
                base[i][r["carrier"]] = payload(r)
            elif r.get("field") == "mode" and r.get("value", -1) >= 0:
                per[i][r["carrier"]][r["value"]] = r
    report = {"_runs": [os.path.basename(d) for d in runs],
              "_rule": "values counted only where BOTH runs agree; arms listed with "
                       "their agreement", "arms": {}}
    for arm in sorted(per[0]):
        a, b = per[0][arm], per[1][arm]
        ba, bb = base[0].get(arm), base[1].get(arm)
        common = sorted(set(a) & set(b))
        agree = [v for v in common if payload(a[v]) == payload(b[v])]
        moved = {v for v in agree
                 if a[v].get("outcome") not in ("fault", "hang", "foreign",
                                                "undecodable", "malformed",
                                                "ledger_mismatch")
                 and payload(a[v]) != ba}
        inert = set(agree) - moved
        bits = {}
        for k in range(8):
            m1 = sum(1 for v in agree if (v >> k) & 1 and v in moved)
            n1 = sum(1 for v in agree if (v >> k) & 1)
            m0 = sum(1 for v in agree if not ((v >> k) & 1) and v in moved)
            n0 = sum(1 for v in agree if not ((v >> k) & 1))
            bits[f"bit{k}(0x{1 << k:02x})"] = {
                "moved_when_set": f"{m1}/{n1}", "moved_when_clear": f"{m0}/{n0}"}
        # exact boolean rule search: is `moved` exactly {v : v & M != 0} for some M?
        exact = None
        for M in range(1, 256):
            if moved == {v for v in agree if v & M}:
                exact = f"moved <=> (mode & 0x{M:02x}) != 0"
                break
        if exact is None:
            for M in range(1, 256):
                for T in (0,):
                    if moved == {v for v in agree if (v & M) != T}:
                        exact = f"moved <=> (mode & 0x{M:02x}) != 0x{T:02x}"
                        break
                if exact:
                    break
        report["arms"][arm] = {
            "agreement": f"{len(agree)}/{len(common)}",
            "moved": f"{len(moved)}/{len(agree)}",
            "inert": f"{len(inert)}/{len(agree)}",
            "exact_boolean_rule": exact,
            "per_bit": bits,
            "baseline_value": next((x["baseline_fields"]["mode"]
                                    for x in ARMSPEC.ARMS if x["id"] == arm), None),
        }
    p = os.path.join(HERE, "analysis", "mode_bits.json")
    json.dump(report, open(p, "w"), indent=1, sort_keys=True)
    print("wrote", p)
    for k, v in sorted(report["arms"].items()):
        print(f"  {k:26s} agree={v['agreement']:9s} moved={v['moved']:9s} "
              f"rule={v['exact_boolean_rule']}")


if __name__ == "__main__":
    main()
