#!/usr/bin/env python3
"""EXP-0171 premise check -- OFFLINE, no device.

Re-derives, from committed evidence only, the five load-bearing premises this
experiment's design rests on. Run BEFORE the frozen contract is used, and again
at analysis time; the JSON it writes is the auditable form of PROGRESS.md M1.

  python3 analysis/premise_check.py > work/m1_findings.json

Sources inspected: tools/agx-isa/{db,validation}.json and the committed
append-only raw of EXP-0154 (which was itself captured from OUR OWN MSL).
Apple binary introspection: NONE.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXP))
ISA = os.path.join(ROOT, "tools", "agx-isa")
E0154 = os.path.join(ROOT, "experiments", "EXP-0154-g17p-emit-alu")
GATED = ("g17p_20260829_run02", "g17p_20260829_run04")
EMIT = {"hardware-run", "isolated-byte-diff"}

# The five ilogic fields blocking emittability, and the byte each lives in.
ILOGIC_BYTES = {"lut_a_free": 4, "z6": 6, "outmod": 7, "z8": 8, "z9": 9}
# EXP-0154 logged byte+4 under the pre-split arm name `lut_a`.
ARM_ALIAS = {"lut_a_free": "lut_a"}
# A5 decomposition of byte+4 (EXP-0166 amendment A5): sub-field -> (shift, mask)
BYTE4_SUBFIELDS = {"lut_a_sel": (0, 0x03), "lut_a_free": (2, 0x07),
                   "lut_a_z": (5, 0x07)}
LADDER = ("srcA", "srcB", "lut_b")          # known-live bytes on the same instr


def load(p):
    with open(p) as f:
        return json.load(f)


def sweep(run):
    p = os.path.join(E0154, "raw", run, "sweep.jsonl")
    out = []
    with open(p) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def main():
    db = load(os.path.join(ISA, "db.json"))
    val = load(os.path.join(ISA, "validation.json"))
    res = {"_note": "offline re-derivation; no device touched", "premises": {}}

    # --- P1: how many fields actually block `ilogic` -----------------------
    ilog = [i for i in db["instructions"] if i["mnemonic"] == "ilogic"][0]
    ventry = val["instructions"]["ilogic"]
    blocking = [(f["name"], f["start"], f["width"],
                 ventry.get(f["name"], {}).get("label", "MISSING"))
                for f in ilog["fields"]
                if ventry.get(f["name"], {}).get("label") not in EMIT]
    res["premises"]["P1_ilogic_blocking_fields"] = {
        "count": len(blocking), "fields": blocking,
        "dispatch_claim": "one field (lut_a_free)",
        "verdict": "CORRECTED" if len(blocking) != 1 else "AS-DISPATCHED"}

    # --- P2/P3: EXP-0154 coverage and liveness, per byte -------------------
    per_run = {}
    for run in GATED:
        recs = [r for r in sweep(run) if r.get("instr") == "ilogic"]
        byfield = collections.defaultdict(list)
        for r in recs:
            byfield[r.get("field")].append(r)
        info = {}
        for f, rs in byfield.items():
            info[f] = {
                "n": len(rs),
                "distinct_bytes": len(set(r["bytes"] for r in rs)),
                "distinct_digests": len(set(r["observed"]["digest"] for r in rs)),
                "outcomes": dict(collections.Counter(r["outcome"] for r in rs)),
            }
        per_run[run] = info
    res["premises"]["P2_exp0154_ilogic_coverage"] = per_run
    res["premises"]["P3_tail_inert_ladder_live"] = {
        "inert_bytes": {f: {run: per_run[run].get(f, {}).get("distinct_digests")
                            for run in GATED}
                        for f in ("z6", "outmod", "z8", "z9")},
        "ladder_bytes": {f: {run: per_run[run].get(f, {}).get("distinct_digests")
                             for run in GATED}
                         for f in LADDER},
        "reading": "distinct_digests == 1 is inert; > 1 is detection power",
    }

    # --- P4: A5 decomposition of EXP-0154's byte+4 (G17P carrier #1) -------
    a5 = {}
    for sub, (shift, mask) in BYTE4_SUBFIELDS.items():
        rows = {}
        for run in GATED:
            recs = [r for r in sweep(run)
                    if r.get("instr") == "ilogic" and r.get("field") == "lut_a"]
            keep = [r for r in recs
                    if (r["value"] & ~(mask << shift) & 0xFF) == 0]
            keep.sort(key=lambda r: r["value"])
            rows[run] = [{"sub": (r["value"] >> shift) & mask,
                          "byte": r["value"], "outcome": r["outcome"],
                          "digest": r["observed"]["digest"]} for r in keep]
        # cross-run agreement + movement, per FIELD-SWEEP-PROTOCOL
        a = {x["sub"]: x for x in rows[GATED[0]]}
        b = {x["sub"]: x for x in rows[GATED[1]]}
        common = sorted(set(a) & set(b))
        agree = [s for s in common if a[s]["digest"] == b[s]["digest"]]
        base = a.get(0, {}).get("digest")
        moved = [s for s in agree if a[s]["digest"] != base]
        a5[sub] = {"n_subvalues": len(common), "agree": len(agree),
                   "disagree": len(common) - len(agree), "moved": len(moved),
                   "moved_values": moved,
                   "per_run": rows}
    res["premises"]["P4_A5_byte4_decomposition_G17P"] = a5

    # --- P5: match/field bit overlap (DEF-0166-1) over candidates ----------
    cands = ["ilogic", "iadd2", "ibfe", "ibitcount", "icmp_pred",
             "fspecial_est", "packed_half2_hi", "bf_alu", "bf_fma_dst",
             "funary", "mem_fence8"]
    ov = {}
    for i in db["instructions"]:
        if i["mnemonic"] not in cands:
            continue
        mm = 0
        for st, w, v in i.get("match", []):
            mm |= (v & ((1 << w) - 1)) << st
        for f in i.get("fields", []):
            fm = ((1 << f["width"]) - 1) << f["start"]
            if mm & fm:
                ov["%s.%s" % (i["mnemonic"], f["name"])] = {
                    "start": f["start"], "width": f["width"],
                    "stuck_bits": bin(((mm & fm) >> f["start"]))}
    res["premises"]["P5_assemble_match_overlap"] = {
        "overlapping_candidate_fields": ov,
        "mitigation": "swept values are spliced as RAW BYTES into the lifted "
                      "block; isadb.assemble() is never on the sweep path. "
                      "analysis/coverage.py gates on distinct `bytes` count."}

    json.dump(res, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
