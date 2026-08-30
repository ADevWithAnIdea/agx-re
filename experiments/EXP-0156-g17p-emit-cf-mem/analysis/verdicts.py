#!/usr/bin/env python3
"""EXP-0156 analysis: turn the gated raw captures into per-field verdicts.

Runs on the M4 repo host (no GPU). Reads ONLY `raw/**/sweep.jsonl`, which is
append-only evidence and is never modified.

What it does, in order:

1. **`no_store` reclassification** (EXP-0140 §8's rule, reused). On the CF and
   `tgac` carriers there is no room for an integrity sentinel, so "no output word
   was written" is ambiguous between contamination and a field value that
   suppresses the store. A case that is `invalid_run` in BOTH gated runs with
   EVERY trial reporting `STATUS OK` cannot be contamination (contamination does
   not reproduce that way), so it is re-labelled `wrong_value` with a `no_store`
   note. Cases that do not reproduce stay `invalid_run` and are EXCLUDED.
   The append-only capture is never edited; the reclassification happens here.

2. **Cross-run acceptance gate.** A field is promoted only if the two runs of its
   pair dispatched the same case set for the arm AND produced the identical
   ACCEPTED-VALUE set (`ok` vs not-`ok`). Exact-outcome disagreement is reported
   separately (EXP-0141 §4.6's distinction).

3. **Exact mask-rule derivation.** For each accepted set, search for a
   (mask, pattern) pair such that `accepted == {v : v & mask == pattern}`. If none
   exists the set is printed verbatim rather than described by a rule that does
   not hold.

4. **Half-classification** for the `h2fma` arms: every case is classified
   `lo_changed` / `hi_changed` / `both` / `neither` from the observed word, which
   is what tests the `h_alu_hi` high-half hypothesis without an inertness argument.

Usage:  python3 analysis/verdicts.py            (uses the frozen run pairs)
        python3 analysis/verdicts.py RUN_A RUN_B
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
RAW = EXP / "raw"

# frozen run pairing (CAPTURE_CONTRACT.json §planned_run_ids, chunked because the
# GPU lease is broken automatically after 15 minutes)
PAIRS = [
    ("g17p-20260830-tg01a", "g17p-20260830-tg02a"),
    ("g17p-20260830-tg01b", "g17p-20260830-tg02b"),
    ("g17p-20260830-cf01a", "g17p-20260830-cf02a"),
    ("g17p-20260830-cf01b", "g17p-20260830-cf02b"),
    ("g17p-20260830-cf01c", "g17p-20260830-cf02c"),
    ("g17p-20260830-mem01", "g17p-20260830-mem02"),
    ("g17p-20260830-mtg01", "g17p-20260830-mtg02"),
    ("g17p-20260830-bf01",  "g17p-20260830-bf02"),
]

# arm -> (instruction, [db.json field names the arm's byte covers], byte)
ARM_FIELDS = {
    "jump.branch_ctrl":        ("jump", ["branch_ctrl"]),
    "pop_reconverge.reserved@a": ("pop_reconverge", ["reserved"]),
    "pop_reconverge.reserved@b": ("pop_reconverge", ["reserved"]),
    "ret.linkmode":            ("ret", ["linkmode"]),
    "ret.scoreboard":          ("ret", ["scoreboard"]),
    "ret_luse.linkmode":       ("ret_luse", ["linkmode"]),
    "ret_luse.tail":           ("ret_luse", ["tail"]),
    "if_push_pred.level":      ("if_push_pred", ["level"]),
    "jump_cond.offset":        ("jump_cond", ["offset"]),
    "jump_cond.cf_scope@P1":   ("jump_cond", ["cf_scope"]),
    "jump_cond.cf_scope@P2":   ("jump_cond", ["cf_scope"]),
    "jump_cond.reserved@P1":   ("jump_cond", ["reserved"]),
    "jump_cond.reserved@P2":   ("jump_cond", ["reserved"]),
    "mask_op.mask_bank":       ("mask_op", ["mask_bank"]),
    "mask_op.scope_kind":      ("mask_op", ["scope_kind"]),
    "atdev_atomic_mem_b12":    ("atomic_mem", ["op_lsb", "op", "per_lane", "op_msb"]),
    "atdevimm_atomic_mem_b12": ("atomic_mem", ["op_lsb", "op", "per_lane", "op_msb"]),
    "atdev_atomic_rmw_b12":    ("atomic_rmw", ["op_lsb", "op", "per_lane", "op_msb"]),
    "attg_atomic_tg_b5":       ("atomic_tg", ["op_desc"]),
    "attg_atomic_tg_b10":      ("atomic_tg", ["rsv10lo"]),
    "attg_atomic_tg_b11":      ("atomic_tg", ["op", "op_hi_rsv"]),
    "tgac.b0":                 ("tg_addr_compute", ["_byte0_unmodelled"]),
    "tgac.b1":                 ("tg_addr_compute", ["_byte1_unmodelled"]),
    "tgac.b2":                 ("tg_addr_compute", ["_byte2_unmodelled"]),
    "tgac.b3":                 ("tg_addr_compute", ["b3"]),
    "tgac.b4":                 ("tg_addr_compute", ["b4"]),
    "tgac.b5":                 ("tg_addr_compute", ["b5"]),
    "bf.byte0_dst":            ("bf_add_dst", ["dst"]),
    "bf.fmt":                  ("bf_add_dst", ["fmt"]),
    "bf.opsel":                ("bf_add_dst", ["_opsel_byte2"]),
    "bf.srcA":                 ("bf_add_dst", ["srcA"]),
    "bf.srcB":                 ("bf_add_dst", ["srcB"]),
    "bf.tail5":                ("bf_add_dst", ["tail"]),
    "bf.tail6":                ("bf_add_dst", ["tail"]),
    "bf.tail7":                ("bf_add_dst", ["tail"]),
    "bffma.byte0_dst":         ("bf_fma_dst", ["dst"]),
    "bffma.fmt":               ("bf_fma_dst", ["fmt"]),
    "bffma.srcA":              ("bf_fma_dst", ["srcA"]),
    "bffma.srcB":              ("bf_fma_dst", ["srcB"]),
    "bffma.srcC":              ("bf_fma_dst", ["srcC"]),
    "h.byte0_dst":             ("hminmax", ["dst"]),
    "h.dst_full":              ("hminmax", ["dst_full"]),
    "h.srcA":                  ("hminmax", ["srcA"]),
    "h.sel":                   ("hminmax", ["sel", "selhi"]),
    "h.srcB":                  ("hminmax", ["srcB"]),
    "h2.h_alu_hi.b0":          ("h_alu_hi", ["dst"]),
    "h2.h_alu_hi.b1":          ("h_alu_hi", ["srcA"]),
    "h2.h_alu_hi.b2":          ("h_alu_hi", ["opsel", "opflags"]),
    "h2.h_alu_hi.b3":          ("h_alu_hi", ["srcB"]),
}

BYTE_OF_ARM = {  # which byte offset within the instruction each arm sweeps
    "tgac.b0": 0, "tgac.b1": 1, "tgac.b2": 2, "tgac.b3": 3, "tgac.b4": 4,
    "tgac.b5": 5, "bf.byte0_dst": 0, "bf.fmt": 1, "bf.opsel": 2, "bf.srcA": 3,
    "bf.srcB": 4, "bf.tail5": 5, "bf.tail6": 6, "bf.tail7": 7,
}


def load(run):
    p = RAW / run / "sweep.jsonl"
    if not p.exists():
        return None
    rows = [json.loads(l) for l in p.open()]
    return rows


def cases(rows):
    return [r for r in rows if r.get("kind") == "case"]


def key(r):
    return (r["arm"], r["value"])


def all_trials_ok(r):
    st = r.get("trial_statuses") or []
    return bool(st) and all(s == "OK" for s in st)


def reclassify(a, b):
    """EXP-0140 §8 `no_store` rule, applied to BOTH runs' copies of a case."""
    out = 0
    for ka, ra in a.items():
        rb = b.get(ka)
        if rb is None:
            continue
        if ra["outcome"] == "invalid_run" and rb["outcome"] == "invalid_run" \
                and all_trials_ok(ra) and all_trials_ok(rb):
            for r in (ra, rb):
                r["outcome"] = "wrong_value"
                r["_reclassified"] = "no_store"
            out += 1
    return out


def mask_rule(accepted, width=8):
    """Exact (mask, pattern) such that accepted == {v : v & mask == pattern}."""
    universe = set(range(1 << width))
    acc = set(accepted)
    if not acc or acc == universe:
        return None
    for mask in range(1 << width):
        pats = {v & mask for v in acc}
        if len(pats) != 1:
            continue
        pat = pats.pop()
        if {v for v in universe if (v & mask) == pat} == acc:
            return (mask, pat)
    return None


def half_class(observed, oracle):
    """lo/hi change classification for the packed-half2 carrier."""
    lo = hi = False
    for k, e in oracle.items():
        if not k.startswith("0:"):
            continue
        o = observed.get(k)
        if o is None:
            return "no_store"
        if (o & 0xFFFF) != (e & 0xFFFF):
            lo = True
        if ((o >> 16) & 0xFFFF) != ((e >> 16) & 0xFFFF):
            hi = True
    return {(False, False): "neither", (True, False): "lo_changed",
            (False, True): "hi_changed", (True, True): "both"}[(lo, hi)]


def main():
    pairs = PAIRS
    if len(sys.argv) == 3:
        pairs = [(sys.argv[1], sys.argv[2])]
    report = {"pairs": {}, "arms": {}, "health": {}, "controls": [],
              "half_classification": {}, "notes": []}
    arm_rows = defaultdict(lambda: {"a": {}, "b": {}})
    for ra, rb in pairs:
        A, B = load(ra), load(rb)
        if A is None or B is None:
            report["pairs"][ra + "|" + rb] = "MISSING"
            continue
        ca = {key(r): r for r in cases(A)}
        cb = {key(r): r for r in cases(B)}
        nre = reclassify(ca, cb)
        common = set(ca) & set(cb)
        report["pairs"][ra + "|" + rb] = {
            "cases_a": len(ca), "cases_b": len(cb), "common": len(common),
            "only_a": len(set(ca) - set(cb)), "only_b": len(set(cb) - set(ca)),
            "no_store_reclassified": nre,
            "baseline_checks_a": sum(1 for r in A if r.get("kind") == "baseline_check"),
            "baseline_fail_a": sum(1 for r in A if r.get("kind") == "baseline_check"
                                   and r.get("outcome") != "ok"),
            "baseline_checks_b": sum(1 for r in B if r.get("kind") == "baseline_check"),
            "baseline_fail_b": sum(1 for r in B if r.get("kind") == "baseline_check"
                                   and r.get("outcome") != "ok"),
            "hangs_a": sum(1 for r in ca.values() if r["outcome"] == "hang"),
            "hangs_b": sum(1 for r in cb.values() if r["outcome"] == "hang"),
        }
        for k in common:
            arm_rows[k[0]]["a"][k[1]] = ca[k]
            arm_rows[k[0]]["b"][k[1]] = cb[k]
        # pre-registered controls / falsifiers
        for k, r in sorted(ca.items()):
            if r["expect_match"] is not None and (
                    r["group"].endswith(("baseline", "falsifier", "liveness",
                                         "control", "semantic", "halfprobe"))
                    or r["arm"].endswith(("liveness", "control", "semantic",
                                          "halfprobe", "baseline"))):
                rb2 = cb.get(k)
                report["controls"].append({
                    "run_pair": ra + "|" + rb, "arm": r["arm"],
                    "group": r["group"], "value": r["value"],
                    "note": r["note"][:130], "expect_match": r["expect_match"],
                    "match_a": r["match"], "match_b": rb2["match"] if rb2 else None,
                    "outcome_a": r["outcome"],
                    "outcome_b": rb2["outcome"] if rb2 else None,
                    "fired_as_registered": (r["match"] == r["expect_match"]) and
                                           (rb2 is not None and
                                            rb2["match"] == r["expect_match"]),
                })

    for arm, d in sorted(arm_rows.items()):
        a, b = d["a"], d["b"]
        vals = sorted(set(a) & set(b))
        acc_a = {v for v in vals if a[v]["outcome"] == "ok"}
        acc_b = {v for v in vals if b[v]["outcome"] == "ok"}
        oc = Counter(a[v]["outcome"] for v in vals)
        agree_acc = sum(1 for v in vals if (v in acc_a) == (v in acc_b))
        agree_exact = sum(1 for v in vals if a[v]["outcome"] == b[v]["outcome"])
        rule = mask_rule(acc_a) if all(v < 256 for v in vals) and len(vals) == 256 else None
        entry = {
            "swept": len(vals), "dense_full_byte": len(vals) == 256,
            "accepted_a": len(acc_a), "accepted_b": len(acc_b),
            "accepted_set_identical": acc_a == acc_b,
            "accepted_values": sorted(acc_a) if len(acc_a) <= 130 else "…%d values" % len(acc_a),
            "mask_rule": ("v & 0x%02X == 0x%02X" % rule) if rule else None,
            "cross_run_accept_agreement_pct": round(100.0 * agree_acc / max(1, len(vals)), 3),
            "cross_run_exact_agreement_pct": round(100.0 * agree_exact / max(1, len(vals)), 3),
            "outcome_histogram_a": dict(oc),
            "reclassified_no_store": sum(1 for v in vals
                                         if a[v].get("_reclassified") == "no_store"),
            "hangs_a": sum(1 for v in vals if a[v]["outcome"] == "hang"),
            "skipped": sum(1 for v in vals if a[v]["outcome"] == "skipped"),
        }
        if arm.startswith("h2."):
            hc = Counter(half_class(a[v]["observed"], a[v]["oracle"]) for v in vals)
            hcb = Counter(half_class(b[v]["observed"], b[v]["oracle"]) for v in vals)
            entry["half_class_a"] = dict(hc)
            entry["half_class_b"] = dict(hcb)
            entry["half_class_agree"] = hc == hcb
        report["arms"][arm] = entry
    print(json.dumps(report, indent=1, sort_keys=True))
    (EXP / "analysis" / "gate_report.json").write_text(
        json.dumps(report, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
