#!/usr/bin/env python3
"""Human-readable per-field partition summary from one gated run (for RESULTS.md)."""
import collections, json, os, sys
EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rngstr(vals):
    iv = sorted(v for v in vals if isinstance(v, int))
    if not iv: return ""
    out, s, p = [], iv[0], iv[0]
    for x in iv[1:]:
        if x == p + 1: p = x; continue
        out.append((s, p)); s = p = x
    out.append((s, p))
    return ",".join(f"0x{a:02x}" if a == b else f"0x{a:02x}-0x{b:02x}" for a, b in out)


def main(run_id):
    recs = [json.loads(l) for l in open(os.path.join(EXP, "raw", run_id, "sweep.jsonl"))]
    by = collections.OrderedDict()
    for r in recs:
        if "field" not in r or r["field"].startswith("_"): continue
        by.setdefault((r["carrier"], r["instr"], r["field"]), []).append(r)
    for (carrier, instr, field), rs in by.items():
        oc = collections.Counter(r["outcome"] for r in rs)
        print(f"== {instr}.{field}  (carrier {carrier}, {len(rs)} cases)  {dict(oc)}")
        ints = [r for r in rs if isinstance(r["value"], int)]
        if ints:
            part = collections.defaultdict(list)
            for r in ints: part[r["outcome"]].append(r["value"])
            for k in sorted(part): print(f"     {k:12s} {rngstr(part[k])[:150]}")
        else:
            perbyte = collections.defaultdict(collections.Counter)
            for r in rs:
                v = str(r["value"])
                key = v.split("=")[0]
                perbyte[key][r["outcome"]] += 1
            for k in sorted(perbyte): print(f"     {k:12s} {dict(perbyte[k])}")


if __name__ == "__main__":
    main(sys.argv[1])
