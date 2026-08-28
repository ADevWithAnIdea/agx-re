#!/usr/bin/env python3
"""report.py -- derives per-item summaries from raw/<run_id>.jsonl for RESULTS.md.
Read-only analysis over the gated capture; does not touch raw/ or re-dispatch
anything. Writes analysis/summary.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP_ROOT = os.path.dirname(HERE)
RAW_DIR = os.path.join(EXP_ROOT, "raw")


def load(run_id):
    path = os.path.join(RAW_DIR, f"{run_id}.jsonl")
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if "case_id" in d:
                recs.append(d)
    return recs


def item_reach(recs):
    rows = [r for r in recs if r["item"] == "branch-reach"]
    out = []
    for r in rows:
        cid = r["case_id"]
        status = r["status"]
        results = r.get("out", {}).get("results")
        delta = None
        if cid == "reach_baseline":
            delta = 0
        elif cid.startswith("reach_fwd_"):
            delta = int(cid[len("reach_fwd_"):])
        elif cid.startswith("reach_bwd_"):
            delta = -int(cid[len("reach_bwd_"):])
        out.append({"case_id": cid, "delta": delta, "status": status, "results": results})
    out.sort(key=lambda x: (x["delta"] is None, x["delta"]))
    return out


def item_deep(recs):
    rows = [r for r in recs if r["item"] == "CF-03"]
    out = []
    for r in rows:
        out.append({"case_id": r["case_id"], "status": r["status"], "verdict": r["verdict"],
                     "note": r["note"]})
    return out


def item_pred(recs):
    rows = [r for r in recs if r["item"] == "CF-05-dstpred-mechanism"]
    out = []
    for r in rows:
        cp = r["case_params"]
        out.append({"case_id": r["case_id"], "dst_pred": cp["dst_pred"], "ifpush_pred": cp["ifpush_pred"],
                     "status": r["status"], "results": r.get("out", {}).get("results")})
    return out


def item_shuffle(recs):
    rows = [r for r in recs if r["item"] == "SIMD-03-static"]
    out = []
    for r in rows:
        cp = r["case_params"]
        out.append({"case_id": r["case_id"], "fn": cp.get("shuffle_fn"), "lane_raw": cp.get("lane_raw"),
                     "status": r["status"], "results": r.get("out", {}).get("results")})
    return out


def item_vote(recs):
    rows = [r for r in recs if r["item"] == "SIMD-07-vote-family"]
    out = []
    for r in rows:
        out.append({"case_id": r["case_id"], "status": r["status"],
                     "pixels": r.get("out", {}).get("pixels")})
    return out


def item_width(recs):
    rows = [r for r in recs if r["item"] == "SIMD-01-fragment-width"]
    out = []
    for r in rows:
        out.append({"case_id": r["case_id"], "status": r["status"],
                     "pixels": r.get("out", {}).get("pixels")})
    return out


def item_sgbar(recs):
    rows = [r for r in recs if r["item"] == "SIMD-06-adversarial"]
    out = []
    for r in rows:
        o = r.get("out", {})
        out.append({"case_id": r["case_id"], "kind": r["kind"], "status": r["status"],
                     "verdict": r["verdict"], "identical": o.get("identical"),
                     "a_len": o.get("a_len"), "b_len": o.get("b_len")})
    return out


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else "m4_20260828_run02"
    recs = load(run_id)
    summary = {
        "run_id": run_id,
        "n_records": len(recs),
        "reach": item_reach(recs),
        "deep": item_deep(recs),
        "pred": item_pred(recs),
        "shuffle": item_shuffle(recs),
        "vote": item_vote(recs),
        "width": item_width(recs),
        "sgbar": item_sgbar(recs),
    }
    out_path = os.path.join(HERE, "summary.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print(f"wrote {out_path}: {len(recs)} records")
    # quick console summaries
    print("\n--- reach (branch-reach) status counts ---")
    from collections import Counter
    c = Counter(r["status"] for r in summary["reach"])
    print(c)
    print("\n--- deep (CF-03) status counts ---")
    c = Counter(r["status"] for r in summary["deep"])
    print(c)
    print("\n--- pred (dst_pred x if_push_pred) unique result patterns ---")
    patterns = {}
    for r in summary["pred"]:
        key = tuple(r["results"].get("0", r["results"].get(0)) if r["results"] else None)
        patterns.setdefault(str(r["results"]), []).append((r["dst_pred"], r["ifpush_pred"]))
    for k, v in patterns.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
