#!/usr/bin/env python3
"""EXP-0148 analysis step 2 -- context statistics for the 23 candidate
"scaffolding" descriptors.

For each target descriptor X we compute, over the resynchronising corpus walk:

  n            number of firings
  P(prev=P|X)  what precedes X  (a near-1.0 single predecessor => X may be P's tail)
  P(next=X|P)  of all firings of that predecessor P, how often X follows
               (a near-1.0 value is the decisive continuation-word signature:
                P is NEVER seen without X, i.e. P's length rule is short by |X|)
  succ         what follows X
  bof          how often X starts a program (a real leader can; a tail cannot)
  after_stop   how often X immediately follows `stop` (i.e. begins a new function)
  distinct     number of distinct byte patterns
  files        number of distinct corpus files

Usage: python3 classify_scaffolding.py <tokens.jsonl> <out.json>
"""
import json, sys, collections

TARGETS = """b_alu10_lo7 b_alu10_loe b_alu10_lof b_alu14_c83 b_alu14_prep2
cubearray_coord_const falu_compact4 frame_marker frame_marker_compact n1_word
n2_compact2 n3_addr_prep n3_word n4_cf_word n4_rt_word operand_word
operand_word_a2_01 operand_word_x2_h5 operand_word_x2_h6 operand_word_x2_h7
pad_operand spill_frame_marker tg_atomic_prep""".split()
EXTRA = ["half_alu_fma12", "falu2_ext8b", "op04_len8"]


def main():
    toks, outp = sys.argv[1], sys.argv[2]
    rows = [json.loads(l) for l in open(toks)]
    by_mnem = collections.defaultdict(list)
    for r in rows:
        by_mnem[r["mnem"]].append(r)
    total_by_mnem = {k: len(v) for k, v in by_mnem.items()}

    # forward: for each mnemonic P, distribution of what follows it
    succ_of = collections.defaultdict(collections.Counter)
    for r in rows:
        succ_of[r["mnem"]][r["next"]] += 1

    out = {}
    for t in TARGETS + EXTRA:
        inst = by_mnem.get(t, [])
        n = len(inst)
        prevc = collections.Counter(r["prev"] for r in inst)
        nextc = collections.Counter(r["next"] for r in inst)
        # the decisive stat: for each predecessor P, P(next==t | mnem==P)
        pred_lock = []
        for p, k in prevc.most_common(8):
            tot = total_by_mnem.get(p, 0)
            pred_lock.append({"pred": p, "n_pred_before_t": k,
                              "p_prev_given_t": round(k / n, 4) if n else 0,
                              "n_total_pred": tot,
                              "p_t_after_pred": round(succ_of[p][t] / tot, 4) if tot else 0})
        out[t] = {
            "n": n,
            "files": len(set(r["file"] for r in inst)),
            "distinct_bytes": len(set(r["hex"] for r in inst)),
            "len": inst[0]["len"] if inst else None,
            "bof": sum(1 for r in inst if r["prev"] == "<BOF>"),
            "after_stop": sum(1 for r in inst if r["prev"] == "stop"),
            "eof": sum(1 for r in inst if r["next"] == "<EOF>"),
            "before_stop": sum(1 for r in inst if r["next"] == "stop"),
            "self_run": sum(1 for r in inst if r["prev"] == t),
            "pred_top": pred_lock,
            "succ_top": [{"succ": s, "p": round(k / n, 4)} for s, k in nextc.most_common(8)] if n else [],
            "sample_bytes": [h for h, _ in collections.Counter(r["hex"] for r in inst).most_common(6)],
        }
    json.dump(out, open(outp, "w"), indent=1)
    for t in TARGETS + EXTRA:
        d = out[t]
        top = d["pred_top"][0] if d["pred_top"] else {}
        print("%-24s n=%-5d files=%-4d distinct=%-4d bof=%-3d afterstop=%-3d  top_pred=%s p(prev|t)=%s p(t|prev)=%s" % (
            t, d["n"], d["files"], d["distinct_bytes"], d["bof"], d["after_stop"],
            top.get("pred"), top.get("p_prev_given_t"), top.get("p_t_after_pred")))


if __name__ == "__main__":
    main()
