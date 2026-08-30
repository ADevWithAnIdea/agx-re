#!/usr/bin/env python3
"""EXP-0200 AMENDMENT A5 analysis -- the hardware instruction-boundary map.

  python3 analysis/scan200.py raw/<scan01> raw/<scan02rev>

A `stop` (`0e 00 00 00`, `_instruction: hardware-run`, whose 24-bit body is
HW-proven free filler) halts the thread that executes it. Write one at offset X
and read the poisoned buffer:

  `not_written`  sentinel intact, result slot still poison -> halted after the
                 sentinel store
  `invalid_run`  nothing written at all -> halted before the sentinel store
  anything else  the program reached its result store

**The claim is one-sided on purpose. A halt PROVES the region is fetched and
executed and that X is an instruction boundary the hardware honours.** The
converse is weaker: no halt at X can mean X is interior to a longer instruction,
or that the region is not executed, or that `0e` there happened to be a benign
operand. Both directions are reported; only the positive one is load-bearing.

`not_written` carries a known confound -- a fill can also suppress the result
store by clobbering its address register or its predicate. That confound
weakens an isolated `not_written`; it does NOT weaken the boundary map, because
the map is read from the PATTERN of halting offsets (a run of halts 2, 4, 6, 10
bytes apart is an instruction-length sequence; a store-address clobber is not
periodic).

WHAT THIS ANSWERS. The gated transparency pair found a `stop` written into a
natural compact-word occurrence left the carrier at its exact oracle at 61 of 65
holes, while target 1 has an illegal `dst` at one of those same offsets faulting
the command buffer 64/256 times. This map decides between the two explanations:
if offsets AROUND the occurrence halt while the occurrence itself does not, the
region IS executed and the occurrence is INTERIOR to a longer instruction.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
HALT = ("not_written", "invalid_run")


def scan(path):
    d = {}
    for ln in open(path):
        ln = ln.strip()
        if not ln:
            continue
        r = json.loads(ln)
        if r.get("fill_id") == "S_stop":
            d[(r["carrier"], r["hole_off"])] = r
    return d


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    a = scan(Path(sys.argv[1]) / "sweep.jsonl")
    b = scan(Path(sys.argv[2]) / "sweep.jsonl")
    shared = sorted(set(a) & set(b))
    agree = [k for k in shared if a[k]["outcome"] == b[k]["outcome"]]
    halt = sorted(k for k in shared
                  if a[k]["outcome"] in HALT and b[k]["outcome"] in HALT)
    out = {"_generated_by": "analysis/scan200.py",
           "_runs": [sys.argv[1], sys.argv[2]],
           "shared_offsets": len(shared),
           "cross_run_agreeing_offsets": len(agree),
           "cross_run_agreement_pct": round(100.0 * len(agree) / max(1, len(shared)), 3),
           "halting_offsets_in_both_runs": len(halt),
           "carriers": {}, "holes": {}}
    print("scan cross-run: %d/%d offsets agree (%.2f %%); %d halt in BOTH runs"
          % (len(agree), len(shared), out["cross_run_agreement_pct"], len(halt)))

    for c in sorted({k[0] for k in shared}):
        hs = sorted(o for (cc, o) in halt if cc == c)
        tried = sorted(o for (cc, o) in shared if cc == c)
        gaps = [hs[i + 1] - hs[i] for i in range(len(hs) - 1)]
        out["carriers"][c] = {"offsets_dispatched": len(tried),
                              "halting_offsets": hs,
                              "halt_gaps": gaps,
                              "n_halts": len(hs)}
        print("  %-9s %4d offsets dispatched, %3d halt; gaps %s"
              % (c, len(tried), len(hs), gaps[:14]))

    arms = json.loads((EXP / "harness" / "arms200.json").read_text())["arms"]
    print("\n  natural compact-word occurrence -> is it a boundary the hardware honours?")
    for t in sorted((x for x in arms if x["kind"] == "transparency"),
                    key=lambda x: (x["carrier"], x["off"])):
        c, o = t["carrier"], t["off"]
        if c not in out["carriers"]:
            continue
        hs = out["carriers"][c]["halting_offsets"]
        prev = max([x for x in hs if x < o], default=None)
        nxt = min([x for x in hs if x > o], default=None)
        rec = {"carrier": c, "off": o, "len": t["len"],
               "orig_bytes": t.get("orig_bytes"),
               "descriptor": t["covers"][0] if t.get("covers") else None,
               "stop_halts_here": (c, o) in set(halt),
               "prev_halting_offset": prev, "next_halting_offset": nxt,
               "enclosing_span": (nxt - prev) if (prev is not None
                                                 and nxt is not None) else None,
               "interior_to_enclosing_span": (prev is not None and nxt is not None
                                              and prev < o < nxt
                                              and (c, o) not in set(halt))}
        out["holes"][t["arm"]] = rec
    p = EXP / "analysis" / "boundary_map.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))

    hh = [r for r in out["holes"].values() if r["stop_halts_here"]]
    ii = [r for r in out["holes"].values() if r["interior_to_enclosing_span"]]
    print("\n  %d of %d natural occurrences ARE a boundary the hardware honours"
          % (len(hh), len(out["holes"])))
    print("  %d are INTERIOR to an enclosing span bounded by two halting offsets"
          % len(ii))
    for r in sorted(ii, key=lambda r: (r["carrier"], r["off"])):
        if r["enclosing_span"] and r["enclosing_span"] <= 16:
            print("    %-9s +%-6d %-9s interior to [%d, %d)  span=%d bytes"
                  % (r["carrier"], r["off"], r["orig_bytes"],
                     r["prev_halting_offset"], r["next_halting_offset"],
                     r["enclosing_span"]))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
