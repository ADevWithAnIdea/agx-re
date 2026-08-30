#!/usr/bin/env python3
"""EXP-0183 A/B gate. BOTH halves run in a subprocess (see corpus_probe.py's
docstring for DEF-0175-2). Compares any number of candidate agx-isa trees against
the live `tools/agx-isa`.

  python3 analysis/ab_gate.py [tree ...]
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
HEXDIR = os.path.join(REPO, "experiments", "EXP-M4-13-full-corpus", "hex")
PROBE = os.path.join(HERE, "corpus_probe.py")


def corpus(d):
    r = subprocess.run([sys.executable, PROBE, HEXDIR], cwd=d,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"error": (r.stdout + r.stderr)[-3000:]}
    return json.loads(r.stdout.strip().splitlines()[-1])


def roundtrip(d):
    r = subprocess.run([sys.executable, os.path.join(d, "roundtrip_test.py")],
                       cwd=d, capture_output=True, text=True)
    t = r.stdout + r.stderr
    return {"ok": t.count("[OK]"), "fail": t.count("[FAIL]"),
            "crash": t.count("Traceback"), "all_pass": "ALL PASS" in t,
            "exit": r.returncode,
            "fail_lines": [l for l in t.splitlines() if "[FAIL]" in l][:40],
            "tail": t[-1500:] if (r.returncode or "ALL PASS" not in t) else ""}


def main():
    trees = {"baseline": os.path.join(REPO, "tools", "agx-isa")}
    for a in sys.argv[1:]:
        trees[os.path.basename(a.rstrip("/"))] = os.path.abspath(a)
    res, base = {}, None
    for name, d in trees.items():
        c = corpus(d)
        res[name] = {"tree": d, "corpus": c, "roundtrip": roundtrip(d)}
        if base is None:
            base = c
        elif "firings" in c and "firings" in base:
            res[name]["firing_delta"] = {
                k: [base["firings"].get(k, 0), c["firings"].get(k, 0)]
                for k in set(base["firings"]) | set(c["firings"])
                if base["firings"].get(k, 0) != c["firings"].get(k, 0)}
            res[name]["files_newly_dirty"] = sorted(
                f for f, v in c["per_file"].items()
                if v[0] != v[1] and base["per_file"].get(f, [0, 0])[0] ==
                base["per_file"].get(f, [0, 1])[1])
            res[name]["files_newly_clean"] = sorted(
                f for f, v in c["per_file"].items()
                if v[0] == v[1] and base["per_file"].get(f, [0, 1])[0] !=
                base["per_file"].get(f, [0, 1])[1])
    for name in trees:
        r = res[name]
        c, t = r["corpus"], r["roundtrip"]
        if "error" in c:
            print("%-14s CORPUS CRASH: %s" % (name, c["error"][:400]))
            continue
        print("%-14s clean=%d/%d leftover=%d tokens=%d | roundtrip OK=%d FAIL=%d crash=%d "
              "ALLPASS=%s exit=%d" % (name, c["clean"], c["files"], c["leftover"],
                                      c["tokens"], t["ok"], t["fail"], t["crash"],
                                      t["all_pass"], t["exit"]))
        if r.get("firing_delta"):
            print("   firing delta (baseline -> variant):",
                  json.dumps(r["firing_delta"], sort_keys=True))
        if r.get("files_newly_dirty"):
            print("   files NEWLY DIRTY:", r["files_newly_dirty"][:20])
        if r.get("files_newly_clean"):
            print("   files NEWLY CLEAN:", r["files_newly_clean"][:20])
    out = os.path.join(HERE, "ab_metrics.json")
    json.dump(res, open(out, "w"), indent=1)
    print("wrote", out)


main()
