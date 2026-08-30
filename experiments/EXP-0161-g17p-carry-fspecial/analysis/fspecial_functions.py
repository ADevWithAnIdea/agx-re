#!/usr/bin/env python3
"""EXP-0161: what FUNCTION does each fspecial selector value actually compute?

The sweeps record, for every field value, the whole 12-element output vector the
carrier produced. Because the input vector is authored and known, each output
vector can be matched OFFLINE against a library of host-computed candidate
functions. This turns `fnclass` / `fnsel` / `precsel` / `roundmode` / `fn_hi`
from "these N values are accepted" into a MAP from encoding to semantics --
which is what an emitter needs.

No GPU time; pure analysis of raw/g17p_20260829_run0*/sweep.jsonl.
"""
from __future__ import print_function

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import cases as CM  # noqa: E402

F = CM.F_IN


def _safe(fn):
    def g(x):
        try:
            return fn(x)
        except Exception:
            return float("nan")
    return g


CANDIDATES = {
    "rsqrt(x)": _safe(lambda x: 1.0 / math.sqrt(x)),
    "sqrt(x)": _safe(math.sqrt),
    "rcp(1/x)": _safe(lambda x: 1.0 / x),
    "log2(x)": _safe(math.log2),
    "exp2(x)": _safe(lambda x: 2.0 ** x),
    "floor(x)": _safe(math.floor),
    "ceil(x)": _safe(math.ceil),
    "trunc(x)": _safe(math.trunc),
    "rint(x)": _safe(lambda x: float(round(x))),
    "x (identity)": _safe(lambda x: x),
    "-x": _safe(lambda x: -x),
    "-log2(x)": _safe(lambda x: -math.log2(x)),
    "2^-x": _safe(lambda x: 2.0 ** (-x)),
    "1/sqrt-est": None,          # placeholder: matched loosely below
    "0.0": _safe(lambda x: 0.0),
}


def match(vec, tol=1e-4):
    out = []
    for name, fn in CANDIDATES.items():
        if fn is None:
            continue
        want = [fn(x) for x in F]
        ok = True
        for g, w in zip(vec, want):
            if w != w or g != g:
                ok = False
                break
            if abs(g - w) > tol * max(1.0, abs(w)):
                ok = False
                break
        if ok:
            out.append(name)
    return out


def all_nan(vec):
    return all(g != g for g in vec)


def loose(vec, fn, rel=0.02):
    """A LOW-PRECISION match: the ~7.5-8 mantissa-bit estimate datapath rather
    than the refined one.

    NOTE (bug found and fixed during analysis, 2026-08-30): the first version
    of this function returned True for an ALL-NaN vector, because every
    `abs(nan - w) > rel*abs(w)` comparison is False in IEEE semantics. That
    made 128 `roundmode` values look like a low-precision estimate when the
    hardware was in fact returning NaN for every input. The NaN guard below is
    the fix, and the corrected reading is in RESULTS.md."""
    for g, x in zip(vec, F):
        if g != g:
            return False
        w = fn(x)
        if w != w or abs(g - w) > rel * abs(w):
            return False
    return True


def main():
    recs = []
    for nm in ("g17p_20260829_run01", "g17p_20260829_run02"):
        p = EXP / "raw" / nm / "sweep.jsonl"
        if p.exists():
            for l in open(str(p)):
                r = json.loads(l)
                if r["arm"] in ("D_FSPEC_INPLACE", "D2_FSPEC_LOG2"):
                    recs.append((nm, r))
    fmap = defaultdict(lambda: defaultdict(set))
    unmatched = Counter()
    for nm, r in recs:
        o = r.get("observed") or {}
        v = o.get("out")
        if not v:
            continue
        vec = [float(x) for x in v]
        m = match(vec)
        if not m and all_nan(vec):
            m = ["NaN for every input"]
        if not m:
            for nm2, fn2 in (("rsqrt(x)", lambda x: 1.0 / math.sqrt(x)),
                             ("log2(x)", math.log2),
                             ("rcp(1/x)", lambda x: 1.0 / x)):
                if loose(vec, _safe(fn2)):
                    m = ["%s [LOW-PRECISION estimate, <=2%% rel]" % nm2]
                    break
        key = "%s.%s" % (r["arm"], r["field"])
        if m:
            for name in m:
                fmap[key][name].add(r["value"])
        else:
            unmatched[key] += 1
    out = {}
    for key in sorted(fmap):
        out[key] = {}
        for fn, vals in sorted(fmap[key].items()):
            vs = sorted(vals)
            out[key][fn] = {"n": len(vs),
                            "values": vs if len(vs) <= 48 else vs[:48] + ["..."]}
    doc = {"_meta": {"input_vector": F, "tolerance_rel": 1e-4,
                     "carriers": {"D_FSPEC_INPLACE": "fast::rsqrt (0xaf, fnclass 1)",
                                  "D2_FSPEC_LOG2": "fast::log2 (0x2f, fnclass 2)"},
                     "unmatched_cases": dict(unmatched),
                     "note": "a value appears under a function iff the WHOLE 12-element "
                             "output vector matched that host-computed function"},
            "function_map": out}
    (EXP / "analysis" / "fspecial_function_map.json").write_text(
        json.dumps(doc, indent=1, sort_keys=True))
    for k in sorted(out):
        print("==", k)
        for fn, d in sorted(out[k].items()):
            print("   %-42s n=%-4d %s" % (fn, d["n"], d["values"][:24]))
    print("unmatched:", dict(unmatched))


if __name__ == "__main__":
    main()
