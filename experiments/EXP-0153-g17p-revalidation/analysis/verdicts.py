#!/usr/bin/env python3
"""EXP-0153 analysis: score every arm of one or two gated G17P runs against the
M4 claim it revalidates, and emit the side-by-side verdict table.

Usage:
  python3 analysis/verdicts.py raw/<run01> [raw/<run02>] --out analysis/

Rule fixed at pre-registration (§10.1): a field's G17P verdict is only
`reproduced` if BOTH gated runs agree case-for-case on the relevant outcome.
With one run supplied the report is explicitly marked PARTIAL.

CLEAN-ROOM: pure analysis of our own committed raw records.
"""
import argparse
import collections
import json
import os
import sys

M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF


def load(run):
    recs = []
    with open(os.path.join(run, "sweep.jsonl")) as f:
        for line in f:
            recs.append(json.loads(line))
    return recs


def by_arm(recs):
    d = collections.defaultdict(dict)
    for r in recs:
        if r["arm"] == "_HEALTH":
            continue
        d[r["arm"]][(r["i"], r.get("rep", 0))] = r
    return d


def accepted(arm_recs, pred=lambda r: r["outcome"] == "ok"):
    return sorted(r["value"] for r in arm_recs.values() if pred(r))


def mask_rule(values, universe):
    """Find an EXACT (mask, pattern) rule `v & mask == pattern` that admits
    exactly `values` out of `universe`, or None. Same idea as EXP-0141's
    analysis/bitrules.py: a rule is only reported when it is exact."""
    S = set(values)
    if not S or len(S) == len(universe):
        return None
    width = max(universe).bit_length() or 1
    for mask in range(1, 1 << width):
        pats = set(v & mask for v in S)
        if len(pats) != 1:
            continue
        pat = pats.pop()
        if all((v & mask) != pat for v in universe if v not in S):
            return {"mask": mask, "pattern": pat,
                    "expr": "v & 0x%x == 0x%x" % (mask, pat)}
    return None


def agree(a, b, key=lambda r: r["outcome"]):
    """Case-for-case agreement between two runs of the same arm."""
    common = sorted(set(a) & set(b))
    same = [k for k in common if key(a[k]) == key(b[k])]
    dis = [{"key": list(k), "value": a[k]["value"],
            "run1": key(a[k]), "run2": key(b[k])} for k in common
           if key(a[k]) != key(b[k])]
    return len(common), len(same), dis


# ---------------------------------------------------------------------------
# per-arm scorers
# ---------------------------------------------------------------------------
def score_A(A, out):
    r = {}
    for arm, universe, m4 in (
            ("A_dst_lo_R7", range(4), "1 of 4 (v & 3 == 1)"),
            ("A_dst_lo_R20", range(4), "1 of 4 (v & 3 == 1)"),
            ("A_dst_ext9_R7", range(128), "64 of 128 (v & 1 == 1)"),
            ("A_dst_ext9_R20", range(128), "64 of 128 (v & 1 == 1)"),
            ("A_dst_pair", range(512), "64 of 512 (v & 0x181 == 0x81)"),
            ("A_extmode", range(256), "128 of 256 (v & 0x80 == 0)")):
        if arm not in A:
            continue
        acc = accepted(A[arm])
        r[arm] = {"n_accepted": len(acc), "n_total": len(list(universe)),
                  "mask_rule": mask_rule(acc, list(universe)),
                  "m4": m4, "accepted_min": acc[:4], "accepted_max": acc[-4:],
                  "outcomes": dict(collections.Counter(
                      x["outcome"] for x in A[arm].values()))}
    # the R>=64 reachability question, stated explicitly
    if "A_extmode" in A:
        lo = [v for v in accepted(A["A_extmode"]) if v < 128]
        hi = [v for v in accepted(A["A_extmode"]) if v >= 128]
        odd = [v for v in lo if v & 1]
        flt = sorted(x["value"] for x in A["A_extmode"].values()
                     if x["outcome"] == "fault")
        r["A_extmode_detail"] = {
            "accepted_below_128": len(lo), "accepted_at_or_above_128": len(hi),
            "accepted_odd_below_128": len(odd),
            "m4": "0..127 all accepted (both parities); 128..255 silently zero",
            "fault_values": flt,
            "m4_fault_values": [252, 253, 254, 255],
            "m4_fault_note": "EXP-0141 raw run11/run12: extmode 252..255 fault "
                             "reproducibly with `Caused GPU Hang Error`; this is "
                             "EXP-0112's R = 126/127 fault, in the field where "
                             "EXP-0112 actually measured it (device_load's "
                             "extmode-target register, extmode = 2*R)",
            "R_reachable": "0..63" if (len(lo) == 128 and not hi) else "SEE DATA"}
    return r


def score_B(A, out):
    r = {}
    if "B_modlo" in A:
        recs = A["B_modlo"]
        n = len(recs)
        ok = sum(1 for x in recs.values() if x["outcome"] == "ok")
        per_v = collections.defaultdict(lambda: [0, 0])
        for x in recs.values():
            per_v[x["value"]][1] += 1
            if x["outcome"] == "ok":
                per_v[x["value"]][0] += 1
        r["falu2.mod_lo"] = {
            "model_fit": "%d/%d" % (ok, n),
            "m4": "98/98 in each of three runs (294/294 overall)",
            "per_value_fit": dict((k, "%d/%d" % tuple(v))
                                  for k, v in sorted(per_v.items())),
            "outcomes": dict(collections.Counter(
                x["outcome"] for x in recs.values()))}
    if "B_srcB_nongpr" in A:
        recs = A["B_srcB_nongpr"]
        lo = dict((x["value"], x) for x in recs.values() if x["value"] < 64)
        hi = dict((x["value"], x) for x in recs.values() if x["value"] >= 64)
        okhi = sum(1 for x in hi.values() if x["outcome"] == "ok")
        M4_K = [0, 2, 3, 31, 32, 48, 56, 61, 62, 63]
        m4pts = dict((k, hi[64 + k]["outcome"] if (64 + k) in hi else "MISSING")
                     for k in M4_K)
        # where did the bound float4 land?
        found = {}
        for v, x in sorted(lo.items()):
            got = (x["observed"].get("out0") or [None])[0]
            if got is not None and abs(got - 5.0) > 1e-6:
                found[v] = got
        r["falu2.minifloat"] = {
            "model_fit_64_127": "%d/%d" % (okhi, len(hi)),
            "m4": "10 HW points confirmed (k = 0,2,3,31,32,48,56,61,62,63)",
            "m4_ten_points_outcome": m4pts,
            "outcomes": dict(collections.Counter(
                x["outcome"] for x in hi.values()))}
        r["falu2.nongpr_file_map"] = {
            "indices_returning_non_baseline": found,
            "m4": "indices 6..9 held 101/202/303/404 (bound constant float4&)",
            "outcomes": dict(collections.Counter(
                x["outcome"] for x in lo.values()))}
    return r


def score_C(A, out):
    if "C_i64add" not in A:
        return {}
    recs = A["C_i64add"]
    add = [x for x in recs.values() if x["field"] == "addsub"]
    base = [x for x in recs.values() if x["field"] == "_baseline"]
    fals = [x for x in recs.values() if x["field"] == "_falsifier_oracle"]
    return {"iadd2.addsub_native_64bit_add": {
        "baseline_subtract_ok": all(x["outcome"] == "ok" for x in base),
        "falsifier_detected": all(x["outcome"] != "ok" for x in fals),
        "add_repetitions_exact": "%d/%d" % (
            sum(1 for x in add if x["outcome"] == "ok"), len(add)),
        "bytes_before": base[0]["bytes"] if base else None,
        "bytes_after": add[0]["bytes"] if add else None,
        "observed_rows": (add[0]["observed"].get("out2") if add else None),
        "oracle_rows": (add[0]["oracle"]["2"] if add and add[0].get("oracle")
                        else None),
        "m4": "exact on 8 rows in both gated runs and 5/5 in run05"}}


def score_D(A, out):
    r = {}
    if "D_falu2_srcB" in A:
        recs = dict((x["value"], x) for x in A["D_falu2_srcB"].values())
        alias = dict((v, recs[v]["outcome"]) for v in range(64, 113) if v in recs)
        r["register_model.falu2_srcB"] = {
            "aliasing_ok_64_112": sum(1 for o in alias.values() if o == "ok"),
            "aliasing_total_64_112": len(alias),
            "aliasing_non_ok": dict((v, o) for v, o in alias.items() if o != "ok"),
            "v113_125": dict((v, recs[v]["outcome"]) for v in range(113, 126)
                             if v in recs),
            "v126": recs[126]["outcome"] if 126 in recs else None,
            "v127": recs[127]["outcome"] if 127 in recs else None,
            "v126_fault_classes": recs[126].get("fault_classes") if 126 in recs else None,
            "v127_fault_classes": recs[127].get("fault_classes") if 127 in recs else None,
            "m4": "r(R mod 64) for R in [64,112]; 126/127 FAULT (EXP-0112)",
            "outcomes": dict(collections.Counter(
                x["outcome"] for x in recs.values()))}
    if "D_iadd2_dst" in A:
        recs = dict((x["value"], x) for x in A["D_iadd2_dst"].values()
                    if x["field"] == "dst")
        faults = sorted(v for v, x in recs.items() if x["outcome"] == "fault")
        # "reached r6" is an OBSERVED value test, not an oracle test: for most
        # dst values the relocation oracle IS the sentinel 99 ("the sum did not
        # land in r6"), so `outcome == ok` would count those as reaching it.
        reach = sorted(v for v, x in recs.items()
                       if (x["observed"].get("out0") or [None])[0] == 32)
        r["register_model.iadd2_dst"] = {
            "reached_r6_at": reach,
            "m4_reached_r6_at": [12, 13],
            "fault_values": [faults[0], faults[-1]] if faults else [],
            "n_fault": len(faults),
            "fault_boundary_reg": (faults[0] >> 1) if faults else None,
            "m4_fault_boundary_reg": 96,
            "alias_140_141": dict((v, recs[v]["outcome"]) for v in (140, 141)
                                  if v in recs),
            "alias_140_141_observed": dict(
                (v, (recs[v]["observed"].get("out0") or [None])[0])
                for v in (140, 141) if v in recs),
            "m4_alias_140_141": "did NOT reach r6 (EXP-0112's mod-64 aliasing "
                                "refuted for this field)",
            "outcomes": dict(collections.Counter(
                x["outcome"] for x in recs.values()))}
    return r


def score_E(A, out, A_IN):
    r = {}
    for arm, field in (("E_offset", "offset"), ("E_width", "width")):
        if arm not in A:
            continue
        recs = dict((x["value"], x) for x in A[arm].values())
        pre = sum(1 for x in recs.values() if x["outcome"] == "ok")
        # score the COMPETING model on the same records
        comp = 0
        for v, x in recs.items():
            got = x["observed"].get("out2")
            if got is None:
                continue
            if field == "offset":
                want = [(a >> (v % 32)) & 0xFF for a in A_IN]
            else:
                ww = 32 if v >= 32 else v
                want = ([(a >> 4) & M32 for a in A_IN] if (ww == 0 or ww >= 32)
                        else [(a >> 4) & ((1 << ww) - 1) for a in A_IN])
            if got[:len(want)] == want:
                comp += 1
        r["ibfe." + field] = {
            "preregistered_model_fit": "%d/%d" % (pre, len(recs)),
            "competing_model_fit": "%d/%d" % (comp, len(recs)),
            "preregistered_model": ("LITERAL" if field == "offset" else "mod 32"),
            "competing_model": ("mod 32" if field == "offset" else "literal-clamp"),
            "m4": ("literal 64/64 vs mod-32 32/64" if field == "offset"
                   else "mod-32 64/64 vs literal-clamp 37/64"),
            "outcomes": dict(collections.Counter(
                x["outcome"] for x in recs.values()))}
    if "E_shr" in A:
        recs = dict((x["value"], x) for x in A["E_shr"].values()
                    if x["field"] == "offset")
        r["ibfe.offset@k_shr"] = {
            "n_inert": sum(1 for x in recs.values() if x["outcome"] == "ok"),
            "n_total": len(recs),
            "inert_values": sorted(v for v, x in recs.items()
                                   if x["outcome"] == "ok"),
            "outcomes": dict(collections.Counter(
                x["outcome"] for x in recs.values()))}
    return r


def score_F(A, out):
    r = {}
    if "F_imm7" in A:
        recs = dict((x["value"], x) for x in A["F_imm7"].values())
        bad = dict((v, x["outcome"]) for v, x in recs.items()
                   if x["outcome"] != "ok")
        r["mov_imm.imm7"] = {
            "n_ok": sum(1 for x in recs.values() if x["outcome"] == "ok"),
            "n_total": len(recs), "non_ok": bad,
            "v12_outcome": recs[12]["outcome"] if 12 in recs else None,
            "v12_observed": (recs[12]["observed"].get("out0") or [None])[0]
                            if 12 in recs else None,
            "v12_roundtrip": recs[12].get("rt") if 12 in recs else None,
            "m4": "hardware-run 0..127; imm7 == 12 does NOT TOKENIZE (decoder), "
                  "hardware never tested"}
    if "F_imm_top" in A:
        pad = dict((x["value"], x) for x in A["F_imm_top"].values()
                   if x["field"] == "imm8_padded")
        unp = dict((x["value"], x) for x in A["F_imm_top"].values()
                   if x["field"] == "imm8_unpadded")
        r["mov_imm.imm_top"] = {
            "padded": dict((v, {"outcome": x["outcome"],
                                "out0": (x["observed"].get("out0") or [None])[0]})
                           for v, x in sorted(pad.items())),
            "unpadded": dict((v, {"outcome": x["outcome"],
                                  "status": x["status"],
                                  "fault_classes": x.get("fault_classes")})
                             for v, x in sorted(unp.items())),
            "m4": "padded: destination KEEPS its previous value (7), proving a "
                  "non-write rather than a silent zero; unpadded: the following "
                  "2-byte instruction is consumed"}
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", default="analysis")
    a = ap.parse_args()
    A_IN = [0x12345678, 0xFFFFFFFF, 0x0000FF00, 0xDEADBEEF, 0x00000001,
            0x00000000, 0x80000000, 0x7FFFFFFF]
    runs = [by_arm(load(p)) for p in a.runs]
    R = runs[0]
    rep = {"runs": a.runs, "target": "G17P", "n_runs": len(runs),
           "gated": len(runs) >= 2,
           "PARTIAL": (len(runs) < 2)}
    rep["A_device_load_destination"] = score_A(R, a.out)
    rep["B_falu2_source_class"] = score_B(R, a.out)
    rep["C_native_64bit_add"] = score_C(R, a.out)
    rep["D_register_model"] = score_D(R, a.out)
    rep["E_ibfe_out_of_range"] = score_E(R, a.out, A_IN)
    rep["F_mov_imm"] = score_F(R, a.out)

    if len(runs) >= 2:
        cross = {}
        for arm in sorted(set(runs[0]) & set(runs[1])):
            n, same, dis = agree(runs[0][arm], runs[1][arm])
            cross[arm] = {"n_common": n, "n_agree": same,
                          "n_disagree": len(dis), "disagreements": dis[:20]}
        rep["cross_run_agreement"] = cross
        rep["cross_run_total"] = {
            "n_common": sum(v["n_common"] for v in cross.values()),
            "n_agree": sum(v["n_agree"] for v in cross.values()),
            "n_disagree": sum(v["n_disagree"] for v in cross.values())}
    # health
    for i, p in enumerate(a.runs):
        h = [r for r in load(p) if r["arm"] == "_HEALTH"]
        rep.setdefault("health", {})[p] = {
            "n": len(h), "n_ok": sum(1 for x in h if x["outcome"] == "ok"),
            "cascade_suspected": [x["note"] for x in h
                                  if x["outcome"] != "ok"]}
    outp = os.path.join(a.out, "verdicts.json")
    json.dump(rep, open(outp, "w"), indent=1, sort_keys=True, default=str)
    print(json.dumps(rep, indent=1, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
