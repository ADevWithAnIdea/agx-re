#!/usr/bin/env python3
"""EXP-0203 OFFLINE model fit, from EXP-0180's COMMITTED raw (our own prior evidence).

Purpose: derive the candidate arithmetic models for the `half_alu_fma12` 12-byte form so
they can be FROZEN in PRE_REGISTRATION.md before any new device work.  No device is
touched; the only inputs are our own committed JSONL observations.

CLEAN-ROOM: reads our own raw observations only.  No Apple binary is inspected.
"""
import json
import struct
import sys
from pathlib import Path

R = Path("/Users/user/asahi_re/public/agx-re/experiments/EXP-0180-g17p-halfalu-rerecord/raw")


def f16(b):
    return struct.unpack("<e", struct.pack("<H", b & 0xFFFF))[0]


def bits16(x):
    return struct.unpack("<H", struct.pack("<e", float(x)))[0]


def lane(word, half):
    return (word >> (16 * half)) & 0xFFFF


def hsel(regs, h):
    r = (h & 0x7F) >> 1
    if r >= 16:
        return None
    return lane(regs[r], h & 1)


def load(run, arm, field):
    out = []
    for line in open(R / run / "sweep.jsonl"):
        rec = json.loads(line)
        if rec.get("arm") == arm and rec.get("field") == field:
            out.append(rec)
    return out


def main():
    run = sys.argv[1] if len(sys.argv) > 1 else "g17p_run02"
    recs = load(run, "F12_FMA", "dst")   # == byte+1 sweep (stale name; now `srcA`)
    print("records:", len(recs))
    by_carrier = {}
    for r in recs:
        by_carrier.setdefault(r["carrier"], []).append(r)
    for cid, rs in sorted(by_carrier.items()):
        print("\n=== carrier", cid, len(rs))
        r0 = rs[0]
        blk = bytes.fromhex(r0["bytes"])
        print("  base bytes:", r0["anchor"], "-> swept byte+1")
        # models to test, evaluated against the OBSERVED pre-dump
        names = ["a*b+c", "abs(a)*b+c", "a*b", "a+b", "abs(a)*b", "c", "a"]
        score = {n: 0 for n in names}
        tot = 0
        difftbl = {}
        for rec in rs:
            o = rec.get("observed")
            if not o or rec["outcome"] in ("fault", "hang", "measurement_failed", "invalid_run"):
                continue
            pre, post = o["pre"], o["post"]
            b = bytes.fromhex(rec["bytes"])
            ha, hb, hc = b[1], b[3], b[5]
            a, bb, c = hsel(pre, ha), hsel(pre, hb), hsel(pre, hc)
            if a is None or bb is None or c is None:
                continue
            dst = b[0] >> 4
            got = lane(post[dst], 0)
            tot += 1
            av, bv, cv = f16(a), f16(bb), f16(c)
            cand = {"a*b+c": av * bv + cv, "abs(a)*b+c": abs(av) * bv + cv,
                    "a*b": av * bv, "a+b": av + bv, "abs(a)*b": abs(av) * bv,
                    "c": cv, "a": av}
            for n, v in cand.items():
                try:
                    if bits16(v) == got:
                        score[n] += 1
                except (OverflowError, ValueError):
                    pass
            # also record whether the HIGH half of dst was preserved
            difftbl.setdefault("hi_preserved", 0)
            if lane(post[dst], 1) == lane(pre[dst], 1):
                difftbl["hi_preserved"] += 1
            # which OTHER registers changed
            ch = tuple(i for i in range(16) if post[i] != pre[i])
            difftbl.setdefault(("changed", ch), 0)
            difftbl[("changed", ch)] = difftbl.get(("changed", ch), 0) + 1
        print("  usable:", tot)
        for n in names:
            print("    %-12s %d/%d" % (n, score[n], tot))
        for k, v in sorted(difftbl.items(), key=lambda x: str(x[0])):
            print("   ", k, v)


if __name__ == "__main__":
    main()
