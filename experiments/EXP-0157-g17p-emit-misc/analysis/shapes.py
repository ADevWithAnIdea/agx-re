#!/usr/bin/env python3
"""EXP-0157: classify a field's REJECTED values by the SHAPE of the output.

An outcome label ("wrong_value") throws away the information that matters. The
`sfu_marker` result came out of asking a different question: given the eight-row
`fast::sin` oracle, is each row correct, sign-flipped, zero, or something else?
That turns 254 "wrong" values into four exact behavioural classes.

This script does that generically: for one (instr, field, carrier) it prints the
partition of all swept values by output shape, with the exact value-mask rule
for each class where one exists.

Legend: `.` = matches the oracle, `-` = sign-flipped, `0` = zero,
        `p` = still the poison word (unwritten), `x` = something else.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import carriers as C  # noqa: E402

POISON = {(0xDEADBEEF + i) & 0xFFFFFFFF for i in range(64)}


def shape(vals, oracle):
    out = []
    for i, e in enumerate(oracle):
        if e is None or i >= len(vals):
            out.append(" ")
            continue
        o = vals[i]
        if isinstance(o, float) and isinstance(e, (int, float)):
            if abs(o - e) <= max(2e-3, 2e-3 * abs(e)):
                out.append(".")
            elif abs(o + e) <= max(2e-3, 2e-3 * abs(e)):
                out.append("-")
            elif abs(o) < 1e-9:
                out.append("0")
            else:
                out.append("x")
        else:
            out.append("." if o == e else ("0" if o in (0, 0.0) else
                       ("p" if o in POISON else "x")))
    return "".join(out)


def mask_rule(vals):
    m, f = 0xFF, vals[0]
    for v in vals:
        m &= ~(v ^ f) & 0xFF
    return m, f & m


def main():
    run, instr, field, carrier = sys.argv[1:5]
    spec = C.CARRIERS[carrier]
    oidx = sorted(spec["outs"])[0]
    oracle = (spec["oracle"] or {}).get(oidx)
    pat = collections.defaultdict(list)
    for line in open(Path(run) / "sweep.jsonl"):
        r = json.loads(line)
        if r["instr"] != instr or r["field"] != field or r["carrier"] != carrier:
            continue
        vals = r["observed"].get("out%d" % oidx)
        if vals is None:
            pat[("(no output: %s)" % r["outcome"])].append(r["value"])
            continue
        pat[shape(vals, oracle)].append(r["value"])
    print("%s.%s@%s  oracle=%s" % (instr, field, carrier,
          [round(x, 4) if isinstance(x, float) else x for x in (oracle or [])][:8]))
    for sh, vs in sorted(pat.items(), key=lambda kv: -len(kv[1])):
        vs = sorted(vs)
        m, val = mask_rule(vs)
        print("   %-12s n=%-4d rule=%s  e.g. %s"
              % (sh, len(vs), ("(v & 0x%02x) == 0x%02x" % (m, val)) if m else "none",
                 [hex(x) for x in vs[:6]]))


if __name__ == "__main__":
    main()
