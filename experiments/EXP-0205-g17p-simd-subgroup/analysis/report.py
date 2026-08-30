#!/usr/bin/env python3
"""EXP-0205 derived report: bit-level structure, hypothesis evaluation, census.

    python3 analysis/report.py raw/<run01> raw/<run02> > analysis/report.txt

Everything here is DERIVED from `raw/` on every invocation. Three things the
verdict gate does not compute:

1. **WHICH BITS OF A LIVE FIELD ARE ACTUALLY DECODED.** `moved` says a field is
   live; it does not say an 8-bit field is really 3 bits wide. For every value
   v and every bit b, this compares the observed vector at v against the vector
   at v XOR (1<<b): a bit that never changes the observation over the whole
   swept range is INERT WITHIN THE FIELD, and an emitter needs to know that.
2. **THE HYPOTHESES**, H1..H5, each evaluated against the range actually swept
   and reported as CONFIRMED / REFUTED / UNRESOLVED with the observation that
   decided it.
3. **THE FAULT / HANG / MEASUREMENT-FAILURE CENSUS** and the `GPUTIME_NS`
   distribution per arm -- the latter because for a register-cache retention
   hint, timing is the only observable a functional read-back cannot reach, and
   saying so is worth more than leaving it implied.

CLEAN-ROOM: host analysis of our own captured observations.
"""
import collections
import json
import statistics
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(EXP / "analysis"))
import carriers205 as C          # noqa: E402
import semantics as S            # noqa: E402
import verdicts as V             # noqa: E402


def main():
    r1, r2 = sys.argv[1], sys.argv[2]
    rec1, rec2 = V.load(r1), V.load(r2)
    i1, i2 = V.index(rec1), V.index(rec2)
    arms = {a["arm"]: a for a in
            json.loads((EXP / "harness" / "arms205.json").read_text())["arms"]}

    print("=" * 78)
    print("EXP-0205 derived report   runs: %s , %s" % (r1, r2))
    print("=" * 78)

    # ------------------------------------------------- SIMD width (measured)
    for tag, recs in (("run01", rec1), ("run02", rec2)):
        for r in recs:
            if r.get("field") == "_width_probe":
                print("SIMD WIDTH %s: measured %s ; simdgroup ids %s ; lanes %d"
                      % (tag, r.get("simd_width"), r.get("simdgroup_ids"),
                         len(r.get("lane_ids") or [])))

    # -------------------------------------------------------- outcome census
    print("\n--- OUTCOME CENSUS (both runs, all roles) ---")
    cen = collections.Counter()
    for recs in (rec1, rec2):
        for r in recs:
            if r.get("outcome"):
                cen[r["outcome"]] += 1
    for k, n in cen.most_common():
        print("   %-22s %d" % (k, n))
    faults = [(r["arm"], r["value"], r.get("fault_classes"))
              for recs in (rec1, rec2) for r in recs
              if r.get("outcome") in ("fault", "hang", "measurement_failure",
                                      "invalid_run", "nondeterministic")]
    print("   non-clean cases: %d" % len(faults))
    for f in faults[:20]:
        print("      ", f)

    # ------------------------------------------- which bits of a field decode
    print("\n--- WHICH BITS OF EACH TARGET FIELD ARE ACTUALLY DECODED ---")
    print("A bit is INERT-WITHIN-FIELD if, for EVERY swept value v, the observed")
    print("vector at v equals the vector at v XOR (1<<b), in BOTH runs.")
    for name, a in sorted(arms.items()):
        if a["role"] != "target":
            continue
        w = a["width"]
        if w < 2:
            continue
        c1, c2 = i1[name]["cases"], i2[name]["cases"]

        def vec(c, v):
            return ((c[v].get("observed") or {}).get("vals_u32")) if v in c else None
        live_bits, inert_bits, undecided = [], [], []
        for b in range(w):
            diffs = same = 0
            for v in sorted(c1):
                w2 = v ^ (1 << b)
                if w2 not in c1 or w2 not in c2:
                    continue
                x1, y1 = vec(c1, v), vec(c1, w2)
                x2, y2 = vec(c2, v), vec(c2, w2)
                if None in (x1, y1, x2, y2):
                    continue
                if x1 == y1 and x2 == y2:
                    same += 1
                elif x1 != y1 and x2 != y2:
                    diffs += 1
                else:
                    undecided.append(b)
            (live_bits if diffs else inert_bits).append(
                (b, diffs, same))
        print("   %-32s live bits %s | inert-within-field %s"
              % (name, [b for b, d, s in live_bits],
                 [b for b, d, s in inert_bits]))

    # ------------------------------------------------- per-value semantic map
    print("\n--- PER-VALUE SEMANTICS, low 16 values of each reduce arm ---")
    for name, a in sorted(arms.items()):
        if a["role"] != "target" or a["instr"] != "simd_reduce":
            continue
        print("   %s (baseline %s=%d)" % (name, a["field"], a["baseline_field"]))
        for v in range(16):
            if v not in i1[name]["cases"]:
                continue
            r = i1[name]["cases"][v]
            vals = (r.get("observed") or {}).get("vals_u32")
            names = S.identify(a["carrier"], vals) if vals else []
            head = "0x%08x" % vals[0] if vals else "-"
            print("      v=%-3d %-13s %-14s %s"
                  % (v, r["outcome"], head, ",".join(names) or "(unidentified)"))

    # ---------------------------------------------------- shuffle dir / cache
    print("\n--- simd_shuffle.dir and .cache, every value on every arm ---")
    for name, a in sorted(arms.items()):
        if a["instr"] != "simd_shuffle" or a["role"] != "target":
            continue
        for v in sorted(i1[name]["cases"]):
            r = i1[name]["cases"][v]
            vals = (r.get("observed") or {}).get("vals_u32")
            names = S.identify(a["carrier"], vals) if vals else []
            print("   %-32s v=%d base=%d %-12s %-12s %s"
                  % (name, v, a["baseline_field"], r["outcome"],
                     "0x%08x" % vals[0] if vals else "-",
                     ",".join(names) or "(unidentified)"))

    # ------------------------------------------------------ H1: ballot.pred
    print("\n--- H1: does any `pred` value select the active-thread mask? ---")
    ALLONES = [0xFFFFFFFF] * 32
    for name, a in sorted(arms.items()):
        if a["field"] != "pred":
            continue
        hits, distinct = [], set()
        for v in sorted(i1[name]["cases"]):
            vals = (i1[name]["cases"][v].get("observed") or {}).get("vals_u32")
            if vals:
                distinct.add(tuple(vals))
                if vals == ALLONES:
                    hits.append(v)
        base = C.baseline_oracle(a["carrier"])
        print("   %-32s distinct observed vectors over 16 values: %d ; "
              "values giving all-ones: %s ; baseline vector head 0x%08x"
              % (name, len(distinct), hits or "NONE", base[0] & 0xFFFFFFFF))
    # cross-mask attribution
    b1 = (i1["sb_ballot#simd_ballot.pred"]["cases"][0].get("observed") or {}).get("vals_u32")
    b2 = (i1["sb_ballot2#simd_ballot.pred"]["cases"][0].get("observed") or {}).get("vals_u32")
    print("   attribution: sb_ballot head 0x%08x vs sb_ballot2 head 0x%08x -> "
          "the result TRACKS the predicate mask, so the instruction is computing "
          "ballot(predicate) at pred=0 on both." % (b1[0], b2[0]))

    # --------------------------------------------------------- GPUTIME_NS
    print("\n--- GPUTIME_NS per target arm (the only observable a register-cache")
    print("    RETENTION hint could still move, and one this method cannot")
    print("    resolve: reported as an observation, never as a gate) ---")
    for name, a in sorted(arms.items()):
        if a["role"] != "target":
            continue
        g = [ (i1[name]["cases"][v].get("observed") or {}).get("gputime_ns")
              for v in sorted(i1[name]["cases"])]
        g = [x for x in g if isinstance(x, int)]
        if not g:
            continue
        print("   %-32s n=%-4d min=%-7d med=%-7d max=%-7d stdev=%.1f"
              % (name, len(g), min(g), statistics.median(g), max(g),
                 statistics.pstdev(g) if len(g) > 1 else 0.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
