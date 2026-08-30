#!/usr/bin/env python3
"""EXP-0207 — the specific questions, answered from raw/ only.

`verdicts.py` decides labels.  This file extracts the per-question detail a
reader needs to check those labels: the form x sr_sel outcome MAP, the dst_hi
routing evidence including which named codeword a relocated write clobbered, the
store-mode partition test, the 4-sample vs 1-sample iter comparison, the operand
payload count with hard outcomes kept separate, the mesh sweep, and the fence
arm's detection-power control.

  python3 analysis/answers.py [--raw-root raw]
"""
import argparse
import collections
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
HARD = {"fault", "hang", "no_draw", "no_dispatch", "undecodable", "not_written",
        "invalid_run", "measurement_failed"}


def load(raw_root):
    runs = {}
    for d in sorted(glob.glob(os.path.join(raw_root, "*"))):
        f = os.path.join(d, "sweep.jsonl")
        if not os.path.isfile(f):
            continue
        runs[os.path.basename(d)] = [json.loads(l) for l in open(f, errors="replace")
                                     if l.strip().startswith("{")]
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", default=os.path.join(EXP, "raw"))
    args = ap.parse_args()
    runs = load(args.raw_root)
    out = {"runs": sorted(runs)}

    # ---------------------------------------------------- form x sr_sel map --
    fx = collections.defaultdict(dict)
    for rid, recs in runs.items():
        for r in recs:
            if r.get("field") != "__form_x_srsel":
                continue
            fx[(rid, r["arm"])][(r.get("form_value"), r.get("sr_sel"))] = \
                (r.get("outcome"), r.get("class"), (r.get("observed") or {}).get("d"))
    fmap = {}
    for (rid, arm), cells in sorted(fx.items()):
        sels = sorted({s for (_f, s) in cells})
        v0 = [cells.get((0, s)) for s in sels]
        v1 = [cells.get((1, s)) for s in sels]
        diff = [s for s, a, b in zip(sels, v0, v1) if a != b]
        fmap["%s@%s" % (arm, rid)] = {
            "selectors": sels,
            "outcome_form0": [x[0] if x else None for x in v0],
            "outcome_form1": [x[0] if x else None for x in v1],
            "payload_identical_per_selector": [s for s, a, b in zip(sels, v0, v1)
                                               if a and b and a[2] == b[2]],
            "selectors_where_form_CHANGED_anything": diff,
            "n_selectors": len(sels), "n_changed_by_form": len(diff)}
    out["get_sr_form_x_srsel"] = fmap

    # --------------------------------------------------------------- dst_hi --
    dh = {}
    for rid, recs in runs.items():
        for r in recs:
            if r.get("field") != "dst_hi" or r.get("kind") != "case":
                continue
            k = "%s@%s" % (r["arm"], rid)
            o = r.get("observed") or {}
            dh.setdefault(k, {})[r["value"]] = {
                "outcome": r["outcome"], "class": r["class"], "moved": r["moved"],
                "payload": o.get("d"), "clobbered": o.get("clobbered_codeword_slots"),
                "ledger_ok": r.get("ledger_ok")}
    out["get_sr_dst_hi"] = dh
    # the in-dimension control: `dst` is the LOW half of the same register number
    ctl = {}
    for rid, recs in runs.items():
        for r in recs:
            if r.get("field") in ("__power_dst", "__ladder_dst"):
                o = r.get("observed") or {}
                ctl["%s@%s/%s" % (r["arm"], rid, r["field"])] = {
                    "value": r["value"], "moved": r["moved"], "outcome": r["outcome"],
                    "clobbered": o.get("clobbered_codeword_slots")}
    out["get_sr_dst_control"] = ctl

    # --------------------------------------------------- per-field summaries --
    per = collections.defaultdict(lambda: collections.defaultdict(
        lambda: {"n": 0, "hard": collections.Counter(), "payloads": set(),
                 "moved": 0, "sem_hit": 0, "sem_checked": 0}))
    for rid, recs in runs.items():
        for r in recs:
            if r.get("kind") != "case" or str(r.get("field", "")).startswith("__"):
                continue
            k = "%s.%s" % (r["instr"], r["field"])
            e = per[k]["%s@%s" % (r["arm"], rid)]
            e["n"] += 1
            if r["outcome"] in HARD:
                e["hard"][r["outcome"]] += 1
            else:
                d = (r.get("observed") or {}).get("d")
                if d:
                    e["payloads"].add(d)
                if r.get("moved"):
                    e["moved"] += 1
            if r.get("oracle") is not None and r.get("match") is not None:
                e["sem_checked"] += 1
                if r["match"]:
                    e["sem_hit"] += 1
    out["per_field"] = {k: {a: {"dispatched": v["n"], "hard": dict(v["hard"]),
                                "distinct_valid_payloads": len(v["payloads"]),
                                "moved_valid": v["moved"],
                                "sem_hit": v["sem_hit"], "sem_checked": v["sem_checked"]}
                            for a, v in sorted(arms.items())}
                        for k, arms in sorted(per.items())}

    # ------------------------------------------------------------- controls --
    ctrls = collections.defaultdict(list)
    for rid, recs in runs.items():
        for r in recs:
            if r.get("kind") in ("ladder", "power_probe", "sensitivity"):
                ctrls["%s@%s" % (r["arm"], rid)].append(
                    {"field": r.get("field"), "value": r.get("value"),
                     "moved": r.get("moved"), "outcome": r.get("outcome")})
    out["controls"] = {k: v for k, v in sorted(ctrls.items())}

    # ------------------------------------------- carriers that never resolved -
    na = {}
    for rid, recs in runs.items():
        for r in recs:
            if r.get("kind") in ("arm_not_attempted", "arm_error"):
                na["%s@%s" % (r["arm"], rid)] = {
                    "kind": r["kind"], "why": r.get("why") or str(r.get("error"))[:200],
                    "outcome": r.get("outcome")}
            if r.get("kind") == "pre_reference":
                out.setdefault("pre_reference", {})["%s@%s" % (r["arm"], rid)] = {
                    "swap_changed_behaviour": r.get("swap_changed_behaviour"),
                    "status": r.get("status")}
    out["not_resolved"] = na

    json.dump(out, open(os.path.join(HERE, "answers.json"), "w"), indent=1, sort_keys=True)
    print("== form x sr_sel: does flipping `form` change ANY selector's outcome?")
    for k, v in sorted(fmap.items()):
        print("   %-24s selectors=%-3d changed_by_form=%d %s"
              % (k, v["n_selectors"], v["n_changed_by_form"],
                 v["selectors_where_form_CHANGED_anything"]))
    print("== dst_hi")
    for k, v in sorted(dh.items()):
        mv = sorted(x for x, y in v.items() if y["moved"])
        cl = sorted({tuple(y["clobbered"] or []) for y in v.values()})
        print("   %-24s values=%-3d moved=%s clobbered_sets=%s" % (k, len(v), mv, cl))
    print("== dst control (the in-dimension positive control)")
    for k, v in sorted(ctl.items()):
        print("   %-34s v=%-4s moved=%-5s %s clob=%s"
              % (k, v["value"], v["moved"], v["outcome"], v["clobbered"]))
    print("== per field")
    for k, arms in sorted(out["per_field"].items()):
        for a, v in sorted(arms.items()):
            print("   %-28s %-22s disp=%-5d V=%-4d moved=%-5d sem=%d/%d hard=%s"
                  % (k, a, v["dispatched"], v["distinct_valid_payloads"], v["moved_valid"],
                     v["sem_hit"], v["sem_checked"], v["hard"]))
    print("== arms that never resolved")
    for k, v in sorted(na.items()):
        print("   %-24s %-20s %s" % (k, v["kind"], str(v["why"])[:110]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
