#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 -- independent regrounding of the 53 `... ladder-passing carriers`
notes in tools/agx-isa/validation.json, straight from EXP-0169's committed raw.

Deliberately NOT an import of EXP-0169's analysis/verdicts.py: the point is to
recompute the note's numbers from sweep.jsonl with our own code, so a bug in
that script cannot make the note look supported. The gate constants and the
observation signature are copied from its docstring/spec (>=99% cross-run
agreement, min(movedA,movedB) >= 2 x disagreements, >=2 common values), because
the CLAIM is stated in those terms; the arithmetic is ours.

Read-only.  Writes analysis/check_0169.json.
"""
import collections, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
E169 = os.path.join(ROOT, "experiments", "EXP-0169-g17p-rerecord")
HARD = {"fault", "hang", "undecodable", "killed", "not_written",
        "no_draw", "lost_7_of_8", "nondeterministic"}
MIN_COMMON, MIN_AGREE_PCT, MOVED_OVER_DISAGREE = 2, 99.0, 2.0


def sig_of(rec):
    oc = rec.get("outcome")
    hard = oc if oc in HARD else "run"
    obs = rec.get("observed")
    d = "-" if obs is None else hashlib.sha1(
        json.dumps(obs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:10]
    return hard + "|" + d


def load_run(path):
    groups = collections.defaultdict(dict)
    dbytes = collections.defaultdict(set)
    ladder = collections.defaultdict(dict)
    n = 0
    with open(os.path.join(path, "sweep.jsonl")) as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            n += 1
            fld = r.get("field")
            if not isinstance(fld, str):
                continue
            ac = (r.get("arm"), r.get("carrier"))
            if fld.startswith("__"):
                ok = None
                if r.get("predict") == "not_ok":
                    ok = (r.get("outcome") != "ok")
                elif r.get("predict") == "move":
                    ok = bool(r.get("outcome") != "ok" or r.get("match") is False)
                ladder[ac][fld] = {"outcome": r.get("outcome"), "pass": ok}
                continue
            key = (r.get("instr"), r.get("arm"), r.get("carrier"), fld)
            groups[key][(r.get("cross") or "", r.get("value"))] = sig_of(r)
            if r.get("bytes"):
                dbytes[key].add(r["bytes"])
    return groups, dbytes, ladder, n


def moved_of(sigs):
    if len(sigs) < 2:
        return 0
    modal = collections.Counter(sigs.values()).most_common(1)[0][0]
    return sum(1 for s in sigs.values() if s != modal)


def cross_run(a, b):
    common = set(a) & set(b)
    agree = sum(1 for k in common if a[k] == b[k])
    n = len(common)
    return {"common": n, "agree": agree, "disagreements": n - agree,
            "agree_pct": round(100.0 * agree / n, 2) if n else None,
            "movedA": moved_of(a), "movedB": moved_of(b),
            "n_valuesA": len(a), "n_valuesB": len(b)}


def gate_live(c):
    if c["common"] < MIN_COMMON or c["agree_pct"] is None or c["agree_pct"] < MIN_AGREE_PCT:
        return False
    if c["movedA"] < 1 or c["movedB"] < 1:
        return False
    return min(c["movedA"], c["movedB"]) >= MOVED_OVER_DISAGREE * c["disagreements"]


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    runs = {}
    for d in sorted(os.listdir(os.path.join(E169, "raw"))):
        p = os.path.join(E169, "raw", d)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "sweep.jsonl")):
            runs["raw/" + d] = load_run(p)
            print("loaded %s: %d records" % (d, runs["raw/" + d][3]), file=sys.stderr)

    # the committed verdict rows, for the runs_used / carrier list each note rests on
    vd = {}
    for fn in ("field_verdicts.json", "field_verdicts_apply.json",
               "field_verdicts_part2_apply.json", "field_verdicts_held_c2load.json"):
        p = os.path.join(E169, "analysis", fn)
        if os.path.exists(p):
            for k, r in json.load(open(p)).items():
                if k.startswith("_"):
                    continue
                vd.setdefault(k, (fn, r))

    out = {}
    for m, e in sorted(val["instructions"].items()):
        for f, r in sorted(e.items()):
            if not isinstance(r, dict):
                continue
            nt = r.get("note") or ""
            if "ladder-passing carriers" not in nt:
                continue
            key = "%s.%s" % (m, f)
            mo = re.search(r"moved on (\d+) of (\d+) ladder-passing carriers", nt)
            ne = re.search(r"no observable effect over the swept range on (\d+) "
                           r"structurally different ladder-passing carriers", nt)
            claim_moved = int(mo.group(1)) if mo else 0
            claim_ladder = int(mo.group(2)) if mo else int(ne.group(1))
            src_fn, src = vd.get(key, (None, None))
            arms_claimed = src.get("arms", []) if src else []
            recomputed = []
            for a in arms_claimed:
                ru = a.get("runs_used") or []
                ac = (a["arm"], a["carrier"])
                gk = (m, a["arm"], a["carrier"], f)
                present = [rn for rn in ru if rn in runs and gk in runs[rn][0]]
                lad = {}
                for rn in ru:
                    if rn in runs:
                        lad.update(runs[rn][2].get(ac, {}))
                lad_pass = bool(lad) and all(v["pass"] for v in lad.values() if v["pass"] is not None)
                c = None
                if len(present) >= 2:
                    c = cross_run(runs[present[0]][0][gk], runs[present[1]][0][gk])
                nb = max([len(runs[rn][1].get(gk, ())) for rn in present] or [0])
                recomputed.append({
                    "arm": a["arm"], "carrier": a["carrier"], "runs_used": ru,
                    "runs_with_records": present,
                    "raw_ladder_records": sorted(lad),
                    "raw_ladder_pass": lad_pass,
                    "claimed_ladder_pass": a.get("ladder_pass"),
                    "raw_cross_run": c,
                    "claimed_cross_run": a.get("cross_run"),
                    "raw_gate_live": bool(c and gate_live(c)),
                    "claimed_gate_live": a.get("gate_live"),
                    "raw_distinct_bytes": nb,
                    "claimed_distinct_bytes": a.get("distinct_bytes"),
                })
            n_lad = sum(1 for x in recomputed if x["raw_ladder_pass"])
            n_mov = sum(1 for x in recomputed if x["raw_ladder_pass"] and x["raw_gate_live"])
            verdict = "SUPPORTED" if (n_mov, n_lad) == (claim_moved, claim_ladder) else "MISMATCH"
            out[key] = {"note": nt, "source_file": src_fn,
                        "claim": {"moved": claim_moved, "ladder_passing": claim_ladder},
                        "raw": {"moved": n_mov, "ladder_passing": n_lad},
                        "verdict": verdict, "arms": recomputed}
    json.dump(out, open(os.path.join(HERE, "check_0169.json"), "w"), indent=1, sort_keys=True)
    agg = collections.Counter(v["verdict"] for v in out.values())
    print(json.dumps(agg, indent=1))
    for k, v in sorted(out.items()):
        if v["verdict"] != "SUPPORTED":
            print("MISMATCH %s claim=%s raw=%s" % (k, v["claim"], v["raw"]))


if __name__ == "__main__":
    main()
