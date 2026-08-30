#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- reground the 19 EXP-0155-family notes from EXP-0155's committed raw.

CRITICAL GATE NOTE.  EXP-0155's gated pair is **run03 + run04**, not the
directories named run01/run02: `analysis/field_verdicts.json["_runs"]` says
`{"run01": "g17p_20260829_run03", "run02": "g17p_20260829_run04"}`, and
`raw/g17p_20260829_run01/PARTIAL.md` says run01 is "PARTIAL, RETAINED, NOT
REUSED, NOT USED FOR PROMOTION".  Pairing run01 with run02 makes almost every
note read CONTRADICTED; that is the instrument, not the corpus.  (First pass of
this script did exactly that -- see RESULTS.md 5.)

METRIC VALIDATION.  Two metrics are used, and both are validated against the
producing experiment's committed output before any verdict is taken:

  moved_r  = |{v in run03 & run04 : outcome_r(v) != "ok"}|   (value >= 0 only)
  agree    = agreement on the BOOLEAN "moved", not on the outcome string
  -> reproduces all 227 `cross_run` triples in
     EXP-0155/analysis/field_verdicts_flat.json EXACTLY (227/227).

  disagree_exact = |{v : outcome_run03(v) != outcome_run04(v)}|
  -> the metric EXP-0155/analysis/verdicts.py:296-297 uses for the
     "swept N/M" / "K/N values disagree" note text.

Read-only.  Writes analysis/check_0155.json.
"""
import collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXP = os.path.join(ROOT, "experiments", "EXP-0155-g17p-emit-tex-frag")
GATED = ("g17p_20260829_run03", "g17p_20260829_run04")


def load(run, keep_sentinel=False):
    out = collections.defaultdict(dict)
    for l in open(os.path.join(EXP, "raw", run, "sweep.jsonl")):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        f = r.get("field")
        if not isinstance(f, str) or f.startswith("_"):
            continue
        v = r.get("value")
        if v is None or (v < 0 and not keep_sentinel):
            continue
        out[(r.get("carrier"), f)][v] = r.get("outcome")
    return out


RA, RB = load(GATED[0]), load(GATED[1])
# verdicts.py's index() does NOT drop the value=-1 sentinel record, so its
# `swept N/M` and `K/N disagree` note text counts it; the flat file's cross_run
# block does drop it.  Both conventions are committed; each claim is checked
# against the convention of the artifact that produced it.  Ignoring this makes
# every "swept N/M" note read off-by-one.
SA, SB = load(GATED[0], True), load(GATED[1], True)


def stats(arm, field, sentinel=False):
    src = (SA, SB) if sentinel else (RA, RB)
    o3, o4 = src[0].get((arm, field), {}), src[1].get((arm, field), {})
    common = sorted(set(o3) & set(o4))
    m3 = sum(1 for v in common if o3[v] != "ok")
    m4 = sum(1 for v in common if o4[v] != "ok")
    dis_moved = sum(1 for v in common if (o3[v] != "ok") != (o4[v] != "ok"))
    dis_exact = sum(1 for v in common if o3[v] != o4[v])
    return {"n_run03": len(o3), "n_run04": len(o4), "common": len(common),
            "moved03": m3, "moved04": m4,
            "agree_pct_movedbool": round(100.0 * (len(common) - dis_moved) / len(common), 2)
                                   if common else None,
            "disagree_exact": dis_exact,
            "outcomes_run03": dict(collections.Counter(o3[v] for v in common))}


RX_REPOINT = re.compile(
    r"representative arm re-pointed from (\S+) to (\S+), where the field is "
    r"demonstrably live \((\d+)/(\d+) of (\d+) moved, ([\d.]+)% cross-run agreement\); "
    r"the original arm showed it inert")
RX_SWEPT = re.compile(r"swept (\d+)/(\d+) of the frozen value set in both runs")
RX_DIS = re.compile(r"(\d+)/(\d+) values disagree between the two gated runs")


def main():
    val = json.load(open(os.environ.get("EXP0198_VALIDATION", os.path.join(ROOT, "tools/agx-isa/validation.json"))))
    nc = set(json.load(open(os.path.join(
        ROOT, "experiments/EXP-0196-note-integrity-audit/work/not_checked.json"))))
    flat = json.load(open(os.path.join(EXP, "analysis", "field_verdicts_flat.json")))
    fv = json.load(open(os.path.join(EXP, "analysis", "field_verdicts.json")))
    pav = fv["per_arm_field_verdicts"]
    out = {}
    for m, e in sorted(val["instructions"].items()):
        for f, r in sorted(e.items()):
            k = "%s.%s" % (m, f)
            if k not in nc or not isinstance(r, dict):
                continue
            if "EXP-0155" not in (r.get("evidence") or []):
                continue
            note = r.get("note") or ""
            claims = []
            orig_arm = None
            mo = RX_REPOINT.search(note)
            if mo:
                orig_arm = mo.group(1)
                a_arm, b_arm = mo.group(1), mo.group(2)
                n3, n4, kk = int(mo.group(3)), int(mo.group(4)), int(mo.group(5))
                pct = float(mo.group(6))
                sb, sa = stats(b_arm, f), stats(a_arm, f)
                claims.append({
                    "claim": "new_arm_is_live",
                    "claimed": {"moved03": n3, "moved04": n4, "common": kk,
                                "agree_pct": pct},
                    "raw": sb,
                    "ok": (sb["moved03"] == n3 and sb["moved04"] == n4
                           and sb["common"] == kk
                           and abs((sb["agree_pct_movedbool"] or -1) - pct) < 0.01)})
                claims.append({
                    "claim": "original_arm_inert",
                    "claimed_arm": a_arm,
                    "claimed": "the original arm showed it inert (0 values moved)",
                    "raw": sa,
                    "committed_cross_run": flat.get(k, {}).get("cross_run", {}).get(a_arm),
                    "committed_outcome_counts":
                        pav.get("%s@%s" % (k, a_arm), {}).get("outcome_counts"),
                    "ok": (sa["moved03"] == 0 and sa["moved04"] == 0)})
            mo = RX_SWEPT.search(note)
            if mo:
                # a swept/disagree clause was written by verdicts.py for the arm
                # that was the roll-up representative AT THE TIME, i.e. the
                # ORIGINAL arm when the note also carries a re-pointing clause.
                arm = orig_arm or flat.get(k, {}).get("arm")
                s = stats(arm, f, sentinel=True)
                claims.append({"claim": "swept_of_frozen_set", "arm": arm,
                               "claimed": {"got": int(mo.group(1)), "want": int(mo.group(2))},
                               "committed": {"swept_both_runs": flat.get(k, {}).get("swept_both_runs"),
                                             "of": flat.get(k, {}).get("of")},
                               "raw": s,
                               "ok": (s["common"] == int(mo.group(1))
                                      and s["disagree_exact"] == 0)})
            mo = RX_DIS.search(note)
            if mo:
                arm = orig_arm or flat.get(k, {}).get("arm")
                s = stats(arm, f, sentinel=True)
                claims.append({"claim": "cross_run_disagreements", "arm": arm,
                               "claimed": {"disagree": int(mo.group(1)),
                                           "common": int(mo.group(2))},
                               "raw": s,
                               "ok": (s["disagree_exact"] == int(mo.group(1))
                                      and s["common"] == int(mo.group(2)))})
            if not claims:
                continue
            out[k] = {"label": r.get("label"), "note": note, "claims": claims,
                      "verdict": "SUPPORTED" if all(c["ok"] for c in claims)
                                 else "CONTRADICTED"}
    json.dump(out, open(os.path.join(HERE, "check_0155.json"), "w"), indent=1, sort_keys=True)
    c = collections.Counter(v["verdict"] for v in out.values())
    print("EXP-0155 family:", len(out), dict(c))
    for k, v in sorted(out.items()):
        flag = "" if v["verdict"] == "SUPPORTED" else "  <<<"
        print("%-32s %-14s %s%s" % (k, v["verdict"], v["label"], flag))
        for cl in v["claims"]:
            if not cl["ok"]:
                print("      FAILS %s: claimed=%s raw=%s" %
                      (cl["claim"], json.dumps(cl.get("claimed")),
                       json.dumps({x: cl["raw"][x] for x in
                                   ("common", "moved03", "moved04", "disagree_exact",
                                    "agree_pct_movedbool")})))


if __name__ == "__main__":
    main()
