#!/usr/bin/env python3
"""EXP-0175 / DEF-0171-1 re-derivation, from EXP-0171's committed raw ONLY.

Claim under test: `ilogic`'s byte0 is `(dst << 4) | 0x0b`, so `db.json`'s 8-bit
match `[[0,8,11]]` is over-fitted to destination r0.

Method (independent of EXP-0171's RESULTS.md):
  * take every `arm == ILOGIC`, `carrier == SYNTH`, `byte_index == 0`, `role == target`
    case from BOTH gated runs;
  * the SYNTH carrier dumps 16 GPRs; the anchor computes 93 & 107 = 73 into r2;
  * for each swept byte0 value v, find which GPRs hold 73 and compare with `v >> 4`;
  * report the mapping for every v, both runs, and the disagreements.

Also probes R1c: does any OTHER low nibble show the same dst<<4 behaviour?

    python3 analysis/rederive_def1.py
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
SRC = os.path.join(REPO, "experiments", "EXP-0171-g17p-ilogic-srca", "raw")
RUNS = ["g17p_20260830_run01", "g17p_20260830_run02"]

AND_RESULT = 93 & 107          # 73 == 0x49, the anchor's computed value
NGPR = 16                      # the SYNTH carrier dumps r0..r15


def collect(run):
    out = {}
    dropped = 0
    with open(os.path.join(SRC, run, "sweep.jsonl")) as fh:
        for line in fh:
            r = json.loads(line)
            if r["arm"] != "ILOGIC" or r["carrier"] != "SYNTH":
                continue
            if r["byte_index"] != 0 or r["role"] != "target":
                continue
            if r.get("invalid_run"):
                dropped += 1
                continue
            out[r["value"]] = r
    return out, dropped


def where_is(rec):
    """GPR indices holding the AND result in this case's dump."""
    obs = rec.get("observed") or {}
    w = (obs.get("words") or [])[:NGPR]
    return [i for i, x in enumerate(w) if x == AND_RESULT]


def main():
    runs = {}
    for run in RUNS:
        recs, dropped = collect(run)
        runs[run] = recs
        print("%s: %d byte0 target cases (%d invalid_run dropped)"
              % (run, len(recs), dropped))

    # --- the claim: low nibble 0x0b => result lands in GPR (v >> 4) -----------
    print("\nlow nibble 0x0b, per destination:")
    print("  %-6s %-8s %-22s %-22s" % ("byte0", "dst=v>>4", RUNS[0], RUNS[1]))
    hits = {r: 0 for r in RUNS}
    misses = []
    per_dst = {}
    for hi in range(16):
        v = (hi << 4) | 0x0b
        cells, ok = [], {}
        for run in RUNS:
            rec = runs[run].get(v)
            if rec is None:
                cells.append("(absent)")
                ok[run] = None
                continue
            loc = where_is(rec)
            cells.append("r%s  %s" % (",r".join(map(str, loc)) or "-", rec["outcome"]))
            ok[run] = (loc == [hi])
            if ok[run]:
                hits[run] += 1
        per_dst[hi] = ok
        flag = "" if all(ok.values()) else "   <-- MISS"
        if not all(ok.values()):
            misses.append(hi)
        print("  0x%02x   r%-7d %-22s %-22s%s" % (v, hi, cells[0], cells[1], flag))
    for run in RUNS:
        print("  %s: %d of 16 destinations landed exactly in r(v>>4)" % (run, hits[run]))
    print("  misses: %s" % (misses or "none"))

    # --- R1c: is 0x0b the discriminator, or do other low nibbles do it too? ---
    print("\nR1c -- every byte0 value whose result lands in exactly r(v>>4):")
    bylow = collections.defaultdict(list)
    for v in range(256):
        both = []
        for run in RUNS:
            rec = runs[run].get(v)
            both.append(rec is not None and where_is(rec) == [v >> 4])
        if all(both):
            bylow[v & 0x0f].append(v)
    for low in sorted(bylow):
        print("  low nibble 0x%x : %d of 16 values  %s"
              % (low, len(bylow[low]), " ".join("0x%02x" % v for v in bylow[low])))

    # --- what else does the anchor's own low nibble 0x3 do? -------------------
    print("\ncontrol -- byte0 values that reproduce the ANCHOR state exactly:")
    anchor = runs[RUNS[0]].get(0x2b)
    same = []
    for v in range(256):
        a = runs[RUNS[0]].get(v)
        b = runs[RUNS[1]].get(v)
        if not (a and b and a.get("observed") and b.get("observed")):
            continue
        if a["observed"].get("digest") == anchor["observed"]["digest"] \
           and b["observed"].get("digest") == runs[RUNS[1]][0x2b]["observed"]["digest"]:
            same.append(v)
    print("  %s" % " ".join("0x%02x" % v for v in same))

    verdict = (hits[RUNS[0]] >= 15 and hits[RUNS[1]] >= 15
               and misses == [15])
    print("\nVERDICT DEF-0171-1: %s" % ("CONFIRMED" if verdict else "NOT CONFIRMED"))
    print("  (15 of 16 required; r15 is unobservable in this carrier by construction --")
    print("   it is the harness's own device_store index register, re-seeded per dump.)")

    out = {"claim": "ilogic byte0 == (dst<<4)|0x0b",
           "runs": RUNS,
           "hits_of_16": hits,
           "misses": misses,
           "low_nibbles_with_dst_behaviour": {str(k): v for k, v in bylow.items()},
           "byte0_values_reproducing_anchor": same,
           "verdict": "CONFIRMED" if verdict else "NOT CONFIRMED"}
    json.dump(out, open(os.path.join(HERE, "def1_rederived.json"), "w"), indent=1)
    return 0 if verdict else 1


sys.exit(main())
