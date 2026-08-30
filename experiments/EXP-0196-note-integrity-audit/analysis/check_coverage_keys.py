#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 -- check the MACHINE-READABLE coverage claims (`values_dispatched`,
`distinct_bytes`) that 174 validation.json rows carry, against committed raw.

tools/agx-isa/validate_labels.py reads these two numbers and reports THIN /
UNDER-COVERED rows from them, but it never opens a raw file -- the numbers are
taken on trust.  This recomputes them: for each row, the maximum over
(cited experiment, run, arm/carrier) of the number of distinct `value`s and
distinct `bytes` recorded for (instr, field).

A raw count BELOW the claim is a possible over-claim; a raw count ABOVE it is
normal (the row reports one arm, the raw holds several) and is reported
separately rather than as a defect.

Read-only.  Writes analysis/coverage_keys_check.json.
"""
import collections, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")

_scan = {}


def scan(expdir):
    if expdir in _scan:
        return _scan[expdir]
    vals = collections.defaultdict(set)
    byts = collections.defaultdict(set)
    for p in sorted(glob.glob(os.path.join(EXPS, expdir, "raw", "**", "*.jsonl"),
                              recursive=True)):
        run = os.path.relpath(p, os.path.join(EXPS, expdir))
        for ln in open(p, "rb"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            f = r.get("field")
            if not isinstance(f, str) or f.startswith("__"):
                continue
            base = f.split("@")[0]
            k = (r.get("instr"), base, run, r.get("arm"), r.get("carrier"))
            _v = r.get("value")
            vals[k].add(_v if not isinstance(_v, (list, dict)) else json.dumps(_v, sort_keys=True))
            if r.get("bytes"):
                byts[k].add(r["bytes"])
    _scan[expdir] = (vals, byts)
    return _scan[expdir]


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    out, agg = {}, collections.Counter()
    for m, entry in sorted(val["instructions"].items()):
        for f, r in sorted(entry.items()):
            if not isinstance(r, dict):
                continue
            nv, nb = r.get("values_dispatched"), r.get("distinct_bytes")
            if nv is None and nb is None:
                continue
            key = "%s.%s" % (m, f)
            best_v = best_b = 0
            where = None
            for ev in (r.get("evidence") or []):
                for d in sorted(glob.glob(os.path.join(EXPS, ev.split("/")[0] + "*"))):
                    if not os.path.isdir(d):
                        continue
                    vals, byts = scan(os.path.basename(d))
                    for k, s in vals.items():
                        if k[0] == m and k[1] == f:
                            if len(s) > best_v:
                                best_v, where = len(s), [os.path.basename(d)] + list(k[2:])
                            best_b = max(best_b, len(byts.get(k, ())))
            verdict = "NO-RAW" if best_v == 0 else (
                "SUPPORTED" if (nv is None or best_v >= nv) and (nb is None or best_b >= nb)
                else "RAW-BELOW-CLAIM")
            agg[verdict] += 1
            out[key] = {"label": r.get("label"), "evidence": r.get("evidence"),
                        "claim_values_dispatched": nv, "claim_distinct_bytes": nb,
                        "raw_max_values": best_v, "raw_max_bytes": best_b,
                        "where": where, "verdict": verdict}
    json.dump(out, open(os.path.join(HERE, "coverage_keys_check.json"), "w"),
              indent=1, sort_keys=True)
    print(agg)
    for k, v in sorted(out.items()):
        if v["verdict"] == "RAW-BELOW-CLAIM":
            print("  %-32s claim v=%s b=%s   raw v=%d b=%d  %s"
                  % (k, v["claim_values_dispatched"], v["claim_distinct_bytes"],
                     v["raw_max_values"], v["raw_max_bytes"], v["where"]))


if __name__ == "__main__":
    main()
