#!/usr/bin/env python3
"""EXP-0148 analysis step 3 -- the continuation-word test.

For a candidate scaffolding descriptor X and each of its observed predecessors P:
partition every corpus firing of P by (byte index, bit) of P's own bytes and look
for a SEPARATOR: a bit whose value perfectly (or near-perfectly) predicts whether
X follows.

A separator with high purity is the signature of case (a): X is not an independent
instruction, it is the continuation of a longer form of P selected by that bit, and
the real fix is P's length rule (+|X| bytes when the bit is set).

No separator -> X is not P's tail; it is either a real instruction (b) or a
free-floating decoder artifact (c).

Usage: python3 continuation_test.py <tokens.jsonl> <out.json> [target ...]
"""
import json, sys, collections

TARGETS = """b_alu10_lo7 b_alu10_loe b_alu10_lof b_alu14_c83 b_alu14_prep2
cubearray_coord_const falu_compact4 frame_marker frame_marker_compact n1_word
n2_compact2 n3_addr_prep n3_word n4_cf_word n4_rt_word operand_word
operand_word_a2_01 operand_word_x2_h5 operand_word_x2_h6 operand_word_x2_h7
pad_operand spill_frame_marker tg_atomic_prep half_alu_fma12 falu2_ext8b
op04_len8""".split()

MIN_PRED = 20        # need at least this many firings of P to test it
MIN_SHARE = 0.15     # only test predecessors that account for >=15% of X


def separators(pred_rows, target):
    """pred_rows: list of (hexbytes, follows_target_bool). Return best bit separators."""
    n = len(pred_rows)
    pos = sum(1 for _, f in pred_rows if f)
    if pos == 0 or pos == n:
        return []
    L = min(len(h) // 2 for h, _ in pred_rows)
    out = []
    for bi in range(L):
        for bit in range(8):
            m = 1 << bit
            a = collections.Counter()   # bitvalue -> (n, npos)
            tot = collections.Counter()
            for h, f in pred_rows:
                v = 1 if (bytes.fromhex(h)[bi] & m) else 0
                tot[v] += 1
                if f:
                    a[v] += 1
            if len(tot) < 2:
                continue
            # purity: how well does the bit separate?
            p1 = a[1] / tot[1] if tot[1] else 0
            p0 = a[0] / tot[0] if tot[0] else 0
            sep = abs(p1 - p0)
            out.append({"byte": bi, "bit": bit, "p_target_bit1": round(p1, 4),
                        "p_target_bit0": round(p0, 4), "n_bit1": tot[1], "n_bit0": tot[0],
                        "separation": round(sep, 4)})
    out.sort(key=lambda d: -d["separation"])
    return out[:5]


def main():
    toks, outp = sys.argv[1], sys.argv[2]
    targets = sys.argv[3:] or TARGETS
    rows = [json.loads(l) for l in open(toks)]
    by_mnem = collections.defaultdict(list)
    for r in rows:
        by_mnem[r["mnem"]].append(r)

    out = {}
    for t in targets:
        inst = by_mnem.get(t, [])
        if not inst:
            out[t] = {"n": 0}
            continue
        prevc = collections.Counter(r["prev"] for r in inst)
        res = {"n": len(inst), "preds": []}
        for p, k in prevc.most_common():
            if k / len(inst) < MIN_SHARE:
                continue
            prows = by_mnem.get(p, [])
            if len(prows) < MIN_PRED:
                continue
            pr = [(r["hex"], r["next"] == t) for r in prows]
            res["preds"].append({
                "pred": p, "n_pred": len(prows), "n_followed_by_t": sum(1 for _, f in pr if f),
                "share_of_t": round(k / len(inst), 4),
                "separators": separators(pr, t),
            })
        out[t] = res
    json.dump(out, open(outp, "w"), indent=1)
    for t in targets:
        d = out[t]
        if not d.get("n"):
            print("%-24s n=0" % t); continue
        print("== %s (n=%d)" % (t, d["n"]))
        for p in d["preds"]:
            s = p["separators"][0] if p["separators"] else None
            print("   pred %-20s n=%-5d followed=%-4d share=%.2f  best-sep=%s" % (
                p["pred"], p["n_pred"], p["n_followed_by_t"], p["share_of_t"],
                ("byte+%d bit%d  p1=%.3f p0=%.3f sep=%.3f (n1=%d n0=%d)" % (
                    s["byte"], s["bit"], s["p_target_bit1"], s["p_target_bit0"],
                    s["separation"], s["n_bit1"], s["n_bit0"])) if s else "none"))


if __name__ == "__main__":
    main()
