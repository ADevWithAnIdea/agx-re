#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- reground the 4 EXP-0138 "N/16 pre-registered predictions REFUTED"
notes (falu2_ext.mod_hi, falu2_srcmod10.mod_hi, falu3_srcmod12.mod_hi,
falu_srcmod12b.dst) from EXP-0138's raw.

GATE: `analysis/field_verdicts.json["_meta"]["runs"]` = raw/m4_20260828_run01 +
raw/m4_20260828_run06.  The victim gate (EXP-0154/analysis/verdicts.py:167-181,
here at EXP-0138/analysis/verdicts.py:127-129) drops any case whose outcome is
`victim` in EITHER run BEFORE counting; omitting it is what manufactured 20 false
findings in EXP-0196's first pass.

Claim re-derived: n_pred_fail / len(preds), where preds = cases carrying
`expect_match: true` and n_pred_fail = those with `match: false`
(verdicts.py:138-139).  Also re-derived: the outcome histogram and the
"reproduced in both runs" determinism assertion.

Read-only.  Writes analysis/check_0138.json.
"""
import collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXP = os.path.join(ROOT, "experiments", "EXP-0138-m4-emit-falu")
RUNS = ("m4_20260828_run01", "m4_20260828_run06")
KEYS = ["falu2_ext.mod_hi", "falu2_srcmod10.mod_hi", "falu3_srcmod12.mod_hi",
        "falu_srcmod12b.dst"]
RX = re.compile(r"(\d+)/(\d+) pre-registered predictions REFUTED")


def load(run):
    out = {}
    for l in open(os.path.join(EXP, "raw", run, "sweep.jsonl")):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        out[r["i"]] = r
    return out


def main():
    A, B = load(RUNS[0]), load(RUNS[1])
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    fv = json.load(open(os.path.join(EXP, "analysis", "field_verdicts.json")))
    out = {}
    for k in KEYS:
        m, f = k.split(".", 1)
        r = val["instructions"][m][f]
        note = r.get("note") or ""
        pairs = [(A[i], B[i]) for i in sorted(set(A) & set(B))
                 if A[i].get("instr") == m and A[i].get("field") == f]
        ev = [(a, b) for a, b in pairs
              if a["outcome"] != "victim" and b["outcome"] != "victim"]
        n_victim = len(pairs) - len(ev)
        preds = [a for a, _ in ev if a.get("expect_match")]
        fail = [a for a in preds if not a["match"]]
        determ = all(a["outcome"] == b["outcome"] for a, b in ev)
        mo = RX.search(note)
        claims = []
        if mo:
            claims.append({"claim": "predictions_refuted",
                           "claimed": {"refuted": int(mo.group(1)),
                                       "predictions": int(mo.group(2))},
                           "raw": {"refuted": len(fail), "predictions": len(preds),
                                   "cases": len(ev), "victims_dropped": n_victim},
                           "ok": (len(fail) == int(mo.group(1))
                                  and len(preds) == int(mo.group(2)))})
        if "reproduced in both runs" in note:
            claims.append({"claim": "reproduced_in_both_runs",
                           "claimed": True, "raw": {"outcome_identical_in_both": determ},
                           "ok": determ})
        # transcription: the committed verdict object carries the same sentence
        claims.append({"claim": "transcription_from_committed_verdict",
                       "claimed": note[:70],
                       "raw": (fv.get(k, {}).get("note") or "")[:70],
                       "ok": (fv.get(k, {}).get("note") or "").strip() in note})
        out[k] = {"label": r.get("label"), "note": note, "claims": claims,
                  "raw_outcomes": dict(collections.Counter(a["outcome"] for a, _ in ev)),
                  "verdict": "SUPPORTED" if all(c["ok"] for c in claims) else "CONTRADICTED"}
    json.dump(out, open(os.path.join(HERE, "check_0138.json"), "w"), indent=1, sort_keys=True)
    c = collections.Counter(v["verdict"] for v in out.values())
    print("EXP-0138 family:", len(out), dict(c))
    for k, v in sorted(out.items()):
        print("  %-26s %-13s %s" % (k, v["verdict"], json.dumps(v["raw_outcomes"])))
        for cl in v["claims"]:
            if not cl["ok"]:
                print("       FAILS", json.dumps(cl)[:300])


if __name__ == "__main__":
    main()
