#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- reground the 6 EXP-0147 notes from EXP-0147's raw.

Rows: pixel_order.flags, pixel_order.scope, vtx_coord_xform.mode,
      vtx_coord_xform.sel, vtx_coord_xform.operand, n3_sample_read.tail.

Every claim is a count or an exact accepted-set rule over one arm's dense byte
sweep.  "Correct" is `outcome == "ok"`; the histogram classes are the raw's own
outcome strings (EXP-0147/analysis/verdicts.py:471-481 documents them).
`both` = values present in BOTH gated runs (run01, run02), the same restriction
verdicts.py:373 applies; the histogram it reports is run01's over that set.

Read-only.  Writes analysis/check_0147.json.
"""
import collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXP = os.path.join(ROOT, "experiments", "EXP-0147-m4-emit-pipeline-misc")
RUNS = ("m4_20260828_run01", "m4_20260828_run02")


def load(run):
    out = {}
    for l in open(os.path.join(EXP, "raw", run, "sweep.jsonl")):
        d = json.loads(l)
        if d.get("kind") is not None:
            continue
        out[(d.get("carrier"), d.get("field"), d.get("value"))] = d
    return out


R1, R2 = load(RUNS[0]), load(RUNS[1])


def cases(carrier, field):
    k1 = {k[2]: v for k, v in R1.items() if k[0] == carrier and k[1] == field}
    k2 = {k[2]: v for k, v in R2.items() if k[0] == carrier and k[1] == field}
    both = set(k1) & set(k2)
    return {v: k1[v] for v in both}, {v: k2[v] for v in both}


def intra_unstable(c1, c2):
    """verdicts.py:375-376: a case counts as intra-run stable only if NEITHER
    gated run flagged `stable: false`.  Checking run01 alone reads
    vtx_coord_xform.sel's `255/256` as `256/256`."""
    return sum(1 for v in c1
               if c1[v].get("stable") is False or c2[v].get("stable") is False)


def hist(d):
    return dict(collections.Counter(r["outcome"] for r in d.values()))


def okset(d):
    return {int(v, 0) if isinstance(v, str) else v
            for v, r in d.items() if r["outcome"] == "ok"}


def bytegroup(carrier, field, prefix):
    c1, c2 = cases(carrier, field)
    sel = {int(v.split("=")[1], 16): r for v, r in c1.items() if v.startswith(prefix + "=")}
    return sel


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    out = {}

    def add(key, claims):
        r = val["instructions"][key.split(".")[0]][key.split(".", 1)[1]]
        out[key] = {"label": r.get("label"), "note": r.get("note"), "claims": claims,
                    "verdict": "SUPPORTED" if all(c["ok"] for c in claims) else "CONTRADICTED"}

    # ---- pixel_order.flags -------------------------------------------------
    acq, _ = cases("pixel_order", "flags")
    rel, _ = cases("pixel_order_rel", "flags")
    a_ok, r_ok = okset(acq), okset(rel)
    add("pixel_order.flags", [
        {"claim": "ACQUIRE rule bit0==0 AND (v&0x0e)!=0, 112/256",
         "raw": {"n_ok": len(a_ok), "n_cases": len(acq), "hist": hist(acq)},
         "ok": (a_ok == {v for v in range(256) if (v & 1) == 0 and (v & 0x0e) != 0}
                and len(a_ok) == 112 and len(acq) == 256)},
        {"claim": "RELEASE rule (v&0x0f)>=2, 224/256",
         "raw": {"n_ok": len(r_ok), "n_cases": len(rel), "hist": hist(rel)},
         "ok": (r_ok == {v for v in range(256) if (v & 0x0f) >= 2}
                and len(r_ok) == 224 and len(rel) == 256)}])

    # ---- pixel_order.scope -------------------------------------------------
    acq, _ = cases("pixel_order", "scope")
    rel, _ = cases("pixel_order_rel", "scope")
    a_ok, r_ok = okset(acq), okset(rel)
    add("pixel_order.scope", [
        {"claim": "ACQUIRE bit4==1 AND (bit6 XOR bit7)==1, 64/256, baseline 0x50",
         "raw": {"n_ok": len(a_ok), "n_cases": len(acq), "hist": hist(acq),
                 "baseline_in_ok": 0x50 in a_ok},
         "ok": (a_ok == {v for v in range(256)
                         if (v >> 4) & 1 and (((v >> 6) & 1) ^ ((v >> 7) & 1))}
                and len(a_ok) == 64 and 0x50 in a_ok)},
        {"claim": "RELEASE bit4==1 AND bit7==1, 64/256, baseline 0xd0",
         "raw": {"n_ok": len(r_ok), "n_cases": len(rel), "hist": hist(rel),
                 "baseline_in_ok": 0xd0 in r_ok},
         "ok": (r_ok == {v for v in range(256)
                         if (v >> 4) & 1 and (v >> 7) & 1}
                and len(r_ok) == 64 and 0xd0 in r_ok)}])

    # ---- vtx_coord_xform.mode ---------------------------------------------
    c1, _ = cases("vtx_coord_xform", "mode")
    ok = okset(c1)
    h = hist(c1)
    add("vtx_coord_xform.mode", [
        {"claim": "(mode & 0xf3) in {0x22,0xe2}, 8/256, baseline 0x22",
         "raw": {"n_ok": len(ok), "ok_values": sorted(ok), "hist": h},
         "ok": (ok == {v for v in range(256) if (v & 0xf3) in (0x22, 0xe2)}
                and len(ok) == 8 and 0x22 in ok)},
        {"claim": "240 of 256 no_draw; 8 wrong pixel",
         "raw": h,
         "ok": (h.get("no_draw") == 240 and h.get("wrong_value") == 8)}])

    # ---- vtx_coord_xform.sel ----------------------------------------------
    c1, c2 = cases("vtx_coord_xform", "sel")
    h = hist(c1)
    faults = [r for r in c1.values() if r["outcome"] == "fault"]
    hang = [r for r in faults if "Hang" in json.dumps(r.get("observed"))
            or "Hang" in (r.get("note") or "")]
    n_unstable = intra_unstable(c1, c2)
    add("vtx_coord_xform.sel", [
        {"claim": "91 ok, 143 no_draw, 19 faults, 1 wrong_value",
         "raw": {"hist": h, "n_cases": len(c1)},
         "ok": (h.get("ok") == 91 and h.get("no_draw") == 143
                and h.get("fault") == 19 and h.get("wrong_value") == 1)},
        {"claim": "Intra-run 255/256 stable",
         "raw": {"n_cases": len(c1), "intra_stable": len(c1) - n_unstable},
         "ok": (len(c1) == 256 and len(c1) - n_unstable == 255)}])

    # ---- vtx_coord_xform.operand ------------------------------------------
    c1, _ = cases("vtx_coord_xform", "operand")
    per = {b: bytegroup("vtx_coord_xform", "operand", "byte%d" % b) for b in range(5)}
    ph = {b: dict(collections.Counter(r["outcome"] for r in per[b].values()))
          for b in per}
    add("vtx_coord_xform.operand", [
        {"claim": "5x256 per byte + structured whole-field values, 1339 cases",
         "raw": {"n_cases": len(c1),
                 "per_byte_counts": {b: len(per[b]) for b in per},
                 "whole": sum(1 for v in c1 if v.startswith("whole"))},
         "ok": (len(c1) == 1339 and all(len(per[b]) == 256 for b in per))},
        {"claim": "bytes 0 and 4 FULLY INERT (256/256 each)",
         "raw": {"byte0": ph[0], "byte4": ph[4]},
         "ok": (ph[0].get("ok") == 256 and ph[4].get("ok") == 256)},
        {"claim": "byte 3 fault-prone (17 faults)",
         "raw": ph[3], "ok": ph[3].get("fault") == 17},
        {"claim": "bytes 1-2 mix correct with no_draw",
         "raw": {"byte1": ph[1], "byte2": ph[2]},
         "ok": (ph[1].get("ok", 0) > 0 and ph[1].get("no_draw", 0) > 0
                and ph[2].get("ok", 0) > 0 and ph[2].get("no_draw", 0) > 0)},
        {"claim": "Intra-run 1339/1339 stable",
         "raw": {"n_cases": len(c1),
                 "intra_stable": len(c1) - intra_unstable(c1, cases("vtx_coord_xform", "operand")[1])},
         "ok": (len(c1) == 1339
                and intra_unstable(c1, cases("vtx_coord_xform", "operand")[1]) == 0)}])

    # ---- n3_sample_read.tail ----------------------------------------------
    c1, c2 = cases("n3_sample_read", "tail")
    per = {b: bytegroup("n3_sample_read", "tail", "byte%d" % b) for b in range(6)}
    ph = {b: dict(collections.Counter(r["outcome"] for r in per[b].values())) for b in per}
    f0 = [r for r in per[0].values() if r["outcome"] == "fault"]
    hang0 = [r for r in f0 if "Hang" in json.dumps(r.get("observed"))
             or "Hang" in (r.get("note") or "")]
    add("n3_sample_read.tail", [
        {"claim": "6x256 per byte + structured whole-field values, 1603 cases",
         "raw": {"n_cases": len(c1), "per_byte_counts": {b: len(per[b]) for b in per}},
         "ok": (len(c1) == 1603 and all(len(per[b]) == 256 for b in per))},
        {"claim": "bytes 1-5 FULLY INERT (256/256 each)",
         "raw": {b: ph[b] for b in range(1, 6)},
         "ok": all(ph[b].get("ok") == 256 for b in range(1, 6))},
        {"claim": "byte 0: 53 values fault",
         "raw": {"byte0": ph[0], "faults_with_Hang_string": len(hang0)},
         "ok": ph[0].get("fault") == 53},
        {"claim": "Intra-run 1603/1603 stable",
         "raw": {"n_cases": len(c1), "intra_stable": len(c1) - intra_unstable(c1, c2)},
         "ok": (len(c1) == 1603 and intra_unstable(c1, c2) == 0)}])

    json.dump(out, open(os.path.join(HERE, "check_0147.json"), "w"), indent=1, sort_keys=True)
    c = collections.Counter(v["verdict"] for v in out.values())
    print("EXP-0147 family:", len(out), dict(c))
    for k, v in sorted(out.items()):
        print("  %-28s %s" % (k, v["verdict"]))
        for cl in v["claims"]:
            if not cl["ok"]:
                print("       FAILS", json.dumps(cl)[:400])


if __name__ == "__main__":
    main()
