#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 -- independent regrounding of the 11 EXP-0168 notes of the form
"N.NNN% agreement over K shared values, M moved vs D disagreements (Xx), ladder
and falsifier passed in every run" straight from EXP-0168's raw.

Own implementation of the rule EXP-0168 documents in analysis/verdicts.py
(placeholder + validity filters, join on (arm, role, field, cross_value, bytes),
best pair by (agree_pct, common), ladder pass = >=2 distinct observed digests,
falsifier pass = no `ok`).  The numbers are recomputed, not copied.

Read-only.  Writes analysis/check_0168.json.
"""
import collections, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
E = os.path.join(ROOT, "experiments", "EXP-0168-g17p-dst-resweep")
RX = re.compile(r"([\d.]+)% agreement over (\d+) shared values, (\d+) moved vs "
                r"(\d+) disagreements \(([^)]+)\), ladder and falsifier passed in every run")


def placeholder(r):
    return r.get("role") == "arm_not_run" or not r.get("attempts")


def key_of(r):
    return (r.get("arm"), r.get("role"), r.get("field"), r.get("cross_value"), r.get("bytes"))


def load():
    per_run = {}
    for rd in sorted(glob.glob(os.path.join(E, "raw", "*"))):
        p = os.path.join(rd, "sweep.jsonl")
        if not os.path.isdir(rd) or not os.path.exists(p):
            continue
        recs = []
        for ln in open(p, "rb"):
            try:
                recs.append(json.loads(ln))
            except Exception:
                pass
        per_run[os.path.basename(rd)] = recs
    return per_run


def main():
    per_run = load()
    sweeps = collections.defaultdict(lambda: collections.defaultdict(dict))
    moved = collections.defaultdict(lambda: collections.defaultdict(dict))
    ladder = collections.defaultdict(dict)
    falsif = collections.defaultdict(dict)
    for run, recs in per_run.items():
        by_l, by_f = collections.defaultdict(list), collections.defaultdict(list)
        for r in recs:
            if placeholder(r) or r.get("validity") != "valid":
                continue
            role = r.get("role")
            if role == "ladder":
                by_l[r["arm"]].append(r)
                continue
            if role == "falsifier":
                by_f[r["arm"]].append(r)
                continue
            if role != "sweep":
                continue
            fk = "%s.%s" % (r.get("instr"), (r.get("field") or "").split("@")[0])
            sweeps[fk][r.get("arm")].setdefault(run, {})[key_of(r)] = r.get("outcome")
            moved[fk][r.get("arm")].setdefault(run, {})[key_of(r)] = bool(r.get("moved"))
        for arm, rs in by_l.items():
            hs = {(r.get("observed") or {}).get("digest") or (r.get("observed") or {}).get("hash")
                  for r in rs}
            ladder[arm][run] = {"n": len(rs), "distinct": len(hs), "pass": len(hs) >= 2}
        for arm, rs in by_f.items():
            bad = [r for r in rs if r.get("outcome") == "ok"]
            falsif[arm][run] = {"n": len(rs), "scored_ok": len(bad),
                                "pass": len(rs) > 0 and not bad}

    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    out = {}
    for m, entry in sorted(val["instructions"].items()):
        for f, r in sorted(entry.items()):
            if not isinstance(r, dict):
                continue
            mo = RX.search(r.get("note") or "")
            if not mo:
                continue
            fk = "%s.%s" % (m, f)
            claim = {"agree_pct": float(mo.group(1)), "common": int(mo.group(2)),
                     "moved": int(mo.group(3)), "disagreements": int(mo.group(4))}
            best = None
            for arm, byrun in sweeps.get(fk, {}).items():
                runs = sorted(byrun)
                for i in range(len(runs)):
                    for j in range(i + 1, len(runs)):
                        A, B = byrun[runs[i]], byrun[runs[j]]
                        common = sorted(set(A) & set(B))
                        if not common:
                            continue
                        dis = [k for k in common if A[k] != B[k]]
                        mv = sum(1 for k in common if moved[fk][arm][runs[i]].get(k))
                        p = {"arm": arm, "pair": "%s|%s" % (runs[i], runs[j]),
                             "common": len(common), "disagreements": len(dis),
                             "agree_pct": round(100.0 * (len(common) - len(dis)) / len(common), 3),
                             "moved": mv}
                        cand = (p["agree_pct"], p["common"])
                        if best is None or cand > (best["agree_pct"], best["common"]):
                            best = p
            lad_ok = fal_ok = None
            if best:
                lad_ok = all(v["pass"] for v in ladder.get(best["arm"], {}).values()) \
                    if ladder.get(best["arm"]) else None
                fal_ok = all(v["pass"] for v in falsif.get(best["arm"], {}).values()) \
                    if falsif.get(best["arm"]) else None
            ok = bool(best and best["agree_pct"] == claim["agree_pct"]
                      and best["common"] == claim["common"]
                      and best["moved"] == claim["moved"]
                      and best["disagreements"] == claim["disagreements"]
                      and lad_ok and fal_ok)
            out[fk] = {"claim": claim, "raw_best_pair": best, "ladder_pass_all_runs": lad_ok,
                       "falsifier_pass_all_runs": fal_ok,
                       "verdict": "SUPPORTED" if ok else "MISMATCH"}
    json.dump(out, open(os.path.join(HERE, "check_0168.json"), "w"), indent=1, sort_keys=True)
    print(collections.Counter(v["verdict"] for v in out.values()))
    for k, v in sorted(out.items()):
        if v["verdict"] != "SUPPORTED":
            print("MISMATCH", k, "claim", v["claim"], "raw", v["raw_best_pair"],
                  "ladder", v["ladder_pass_all_runs"], "fals", v["falsifier_pass_all_runs"])


if __name__ == "__main__":
    main()
