#!/usr/bin/env python3
"""EXP-0165 A/B gate: the EXP-0148/EXP-0162 metric pair (CLEAN FILES and STRICT
LEFTOVER BYTES over the own-MSL corpus) plus roundtrip_test.py and per-descriptor
firing deltas, run against the live tools/agx-isa and against any number of
candidate trees.

  python3 analysis/ab_gate.py [tree ...]     # default: baseline only
"""
import collections, contextlib, importlib.util, io, json, os, runpy, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
HEXDIR = os.path.join(REPO, "experiments", "EXP-M4-13-full-corpus", "hex")


def load(d):
    d = os.path.abspath(d)
    spec = importlib.util.spec_from_file_location("isadb_%s" % abs(hash(d)),
                                                  os.path.join(d, "isadb.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def corpus(m):
    clean = leftover = files = 0
    firings = collections.Counter()
    for fn in sorted(os.listdir(HEXDIR)):
        if not fn.endswith(".hex"):
            continue
        files += 1
        buf = bytes.fromhex("".join(open(os.path.join(HEXDIR, fn)).read().split()))
        off, n = 0, len(buf)
        while off < n:
            try:
                rec, length = m.decode_one(buf, off)
            except Exception:
                break
            if not length:
                break
            firings[rec["mnemonic"]] += 1
            off += length
        leftover += n - off
        if off == n:
            clean += 1
    return {"files": files, "clean": clean, "leftover": leftover}, firings


def roundtrip(d):
    buf = io.StringIO()
    old = list(sys.path), list(sys.argv)
    sys.path.insert(0, os.path.abspath(d))
    sys.argv = [os.path.join(os.path.abspath(d), "roundtrip_test.py")]
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                runpy.run_path(sys.argv[0], run_name="__main__")
            except SystemExit:
                pass
    finally:
        sys.path, sys.argv = old
    t = buf.getvalue()
    return {"ok": t.count("[OK]"), "fail": t.count("[FAIL]"),
            "crash": t.count("Traceback"), "all_pass": "ALL PASS" in t}


def main():
    trees = {"baseline": os.path.join(REPO, "tools", "agx-isa")}
    for a in sys.argv[1:]:
        trees[os.path.basename(a.rstrip("/"))] = a
    res, base_f = {}, None
    for name, d in trees.items():
        m = load(d)
        met, fir = corpus(m)
        res[name] = {"corpus": met, "roundtrip": roundtrip(d),
                     "firings_total": sum(fir.values())}
        if base_f is None:
            base_f = fir
        else:
            res[name]["firing_delta"] = {
                k: [base_f.get(k, 0), fir.get(k, 0)]
                for k in set(base_f) | set(fir) if base_f.get(k, 0) != fir.get(k, 0)}
    for name in trees:
        r = res[name]
        print("%-12s clean=%d/%d leftover=%d  roundtrip OK=%d FAIL=%d crash=%d ALLPASS=%s tokens=%d"
              % (name, r["corpus"]["clean"], r["corpus"]["files"],
                 r["corpus"]["leftover"], r["roundtrip"]["ok"],
                 r["roundtrip"]["fail"], r["roundtrip"]["crash"],
                 r["roundtrip"]["all_pass"], r["firings_total"]))
        if r.get("firing_delta"):
            print("   firing delta (baseline -> variant):", r["firing_delta"])
    out = os.path.join(EXP, "analysis", "ab_metrics.json")
    json.dump(res, open(out, "w"), indent=1)
    print("wrote", out)


main()
