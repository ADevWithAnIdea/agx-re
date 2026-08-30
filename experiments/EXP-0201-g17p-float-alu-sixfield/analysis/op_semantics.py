#!/usr/bin/env python3
"""EXP-0201 refined operation map for `falu3.op` / `falu3_ext.op` byte+2.

    python3 analysis/op_semantics.py raw/<run> [...]   -> analysis/op_semantics.json

An analysis program may change; its input raw files and hashes may not. This one
reads only the immutable per-case records and reports the BIT PATTERNS the
hardware produced for each operation class, because two of the refinements below
are invisible to a value-level comparison:

  * `+0.0` and `-0.0` compare equal as floats but are different results for an
    operation whose sign follows an operand;
  * `NaN != NaN`, so a class that produces NaN looks like a mismatch against
    every candidate unless the comparison is done on bits.

The refinement this finds is emitter-relevant: `db.json`'s published map calls
the low-3 class 5 a **constant zero**. It is not. It is a **multiply by zero**:
its sign follows srcB, and an infinite srcB yields NaN. An implementer told
"this returns 0" would emit a NaN into a shader that feeds it an infinity.
"""
import collections
import glob
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
import carriers201 as C          # noqa: E402

ARMS = {"f3_fma#0/falu3.op": (C.F3_A, C.F3_B, C.F3_C),
        "f3_fma_x#0/falu3.op": (C.F3X_A, C.F3X_B, C.F3X_C),
        "f3e_sat#0/falu3_ext.op": (C.FE_A, C.FE_B, C.FE_C),
        "f3e_sat_x#0/falu3_ext.op": (C.FEX_A, C.FEX_B, C.FEX_C)}


def bits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def mulzero(b):
    """0.0 * b, evaluated on the host with IEEE-754 semantics."""
    out = []
    for y in b:
        try:
            out.append(bits(0.0 * y))
        except Exception:                                       # noqa: BLE001
            out.append(bits(float("nan")))
    return out


def main():
    dirs = sys.argv[1:]
    if not dirs:
        print(__doc__)
        return 2
    recs = []
    for d in dirs:
        run = os.path.basename(os.path.normpath(d))
        for f in sorted(glob.glob(os.path.join(d, "sweep.jsonl"))):
            for ln in open(f, errors="replace"):
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                r["_run"] = run
                recs.append(r)
    out = {}
    for arm, (a, b, c) in ARMS.items():
        rs = [r for r in recs if r.get("arm") == arm and r.get("field") == "op"]
        if not rs:
            continue
        cand = {
            "0.0*b (multiply by zero)": mulzero(b),
            "constant +0.0": [bits(0.0)] * 8,
            "-b": [bits(-y) for y in b],
            "a*b+c": [bits(x * y + z) for x, y, z in zip(a, b, c)],
        }
        by_class = collections.defaultdict(collections.Counter)
        for r in rs:
            if r.get("outcome") in ("fault", "hang", "invalid_run",
                                    "measurement_failure", "nondeterministic"):
                by_class[r["value"] & 7]["HARD:" + r["outcome"]] += 1
                continue
            got = tuple((r.get("observed") or {}).get("vals_u32") or [])
            named = None
            for k, v in cand.items():
                if got == tuple(v):
                    named = k
                    break
            by_class[r["value"] & 7][named or "unclassified"] += 1
        # the exact observed word vector for each low-3 class, at a value with
        # bits 6/7 clear (the corruptor-free region measured on run01)
        sample = {}
        for r in rs:
            v = r["value"]
            if v & 0xC0:
                continue
            k = v & 7
            if k not in sample and r.get("observed", {}).get("vals_u32"):
                sample[k] = ["0x%08x" % w for w in r["observed"]["vals_u32"]]
        out[arm] = {"low3_classes": {str(k): dict(v) for k, v in sorted(by_class.items())},
                    "sample_u32_by_low3_bits67_clear": {str(k): v for k, v in sorted(sample.items())},
                    "srcB": [repr(y) for y in b]}
    json.dump(out, open(os.path.join(HERE, "op_semantics.json"), "w"), indent=1)
    for arm, e in out.items():
        print("==", arm)
        print("   srcB =", e["srcB"])
        for k, v in e["low3_classes"].items():
            print("   low3=%s  %s" % (k, dict(v)))
        for k, v in e["sample_u32_by_low3_bits67_clear"].items():
            print("   low3=%s -> %s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
