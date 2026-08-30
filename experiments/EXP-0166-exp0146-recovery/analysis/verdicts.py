#!/usr/bin/env python3
"""EXP-0166 stage 2 — decomposition (A5), gates (G1-G5) and the three deliverable JSONs.

  python3 analysis/verdicts.py

Reads analysis/derived_stats.json (written by adjudicate.py) plus EXP-0146's raw captures again
for the A5 sub-field decomposition, and writes:

  analysis/field_verdicts.json        merge-ready survivors, flat <mnemonic>.<field>
  analysis/withheld.json              everything rejected, with reason and numbers
  analysis/proposed_db_defects.json   descriptor defects with evidence

Offline only. Writes nothing outside this experiment directory.
"""
import json
import os
from collections import defaultdict

import adjudicate as A

HERE = A.HERE


def hexbytes(s):
    return bytes.fromhex(s)


def diffbits(a, b):
    out = []
    for i in range(min(len(a), len(b))):
        x = a[i] ^ b[i]
        for k in range(8):
            if (x >> k) & 1:
                out.append(i * 8 + k)
    return out


def main():
    stats, comp, dbf, dbi, val, flaked, _log = A.main()

    runs = {r: A.load_jsonl(os.path.join(A.SRC, "raw", r, "sweep.jsonl")) for r in A.GATED_RUNS}
    # (instr,carrier) -> unmutated bytes ; (instr,field,carrier,value) -> rec per run
    unmut = {}
    per = {r: {} for r in A.GATED_RUNS}
    for r, recs in runs.items():
        for rec in recs:
            ins, fld, car = rec.get("instr"), rec.get("field"), rec.get("carrier")
            if ins in ("_meta", "_i64"):
                continue
            if fld == "_baseline":
                unmut[(ins, car)] = rec["bytes"]
                continue
            if fld.startswith("_") or fld == "lut_a+lut_b+op_base":
                continue
            v = rec.get("value")
            if isinstance(v, (list, dict)):
                continue
            per[r][(ins, fld, car, v)] = rec

    # ------------------------------------------------------------------ A5 decomposition
    # pool of (instr,carrier) -> list of (armkey, value)
    pool = defaultdict(list)
    for (ins, fld, car, v) in per[A.GATED_RUNS[1]]:
        pool[(ins, car)].append((fld, v))

    decomposed = {}
    for (ins, car), items in sorted(pool.items()):
        if (ins, car) not in unmut:
            continue
        base = hexbytes(unmut[(ins, car)])
        for fname, (s, w) in sorted(dbf.get(ins, {}).items()):
            if w > 8:
                continue                       # composites go through A1, not A5
            sel = {}
            srcarms = set()
            for (fld, v) in items:
                r3 = per[A.GATED_RUNS[1]].get((ins, fld, car, v))
                r1 = per[A.GATED_RUNS[0]].get((ins, fld, car, v))
                if not (r1 and r3 and r3.get("bytes")):
                    continue
                b = hexbytes(r3["bytes"])
                if len(b) != len(base):
                    continue
                d = diffbits(b, base)
                if d and not all(s <= x < s + w for x in d):
                    continue                   # touches bits outside F
                sv = A.getbits(b, s, w)
                if sv in sel:
                    continue
                sel[sv] = (fld, v, r1, r3)
                srcarms.add(fld)
            if not sel:
                continue
            N = D = M = I = 0
            inert_sv, moved_sv, dis_sv = [], [], []
            for sv, (fld, v, r1, r3) in sorted(sel.items()):
                if not (A.informative(r1) and A.informative(r3)):
                    continue
                N += 1
                if A.observable(r1) != A.observable(r3):
                    D += 1
                    dis_sv.append(sv)
                elif A.inert_A3(r1) and A.inert_A3(r3):
                    I += 1
                    inert_sv.append(sv)
                else:
                    M += 1
                    moved_sv.append(sv)
            agree = (M + I) / N if N else 0.0
            dense = len(sel) == (1 << w)
            if not dense:
                verdict = "withheld"
            elif M >= 1 and agree >= A.AGREEMENT_MIN and M >= A.MOVEMENT_OVER_DISAGREE * D:
                verdict = "stable-live"
            elif M == 0 and agree >= A.AGREEMENT_MIN:
                verdict = "inert-single-carrier"
            else:
                verdict = "withheld"
            decomposed["%s.%s@%s" % (ins, fname, car)] = {
                "instr": ins, "field": fname, "carrier": car,
                "bits": [s, w], "N": N, "D": D, "M": M, "I": I,
                "agreement": round(agree, 5), "verdict": verdict,
                "subvalues_covered": len(sel), "subvalues_possible": 1 << w, "dense": dense,
                "decomposed_from": sorted(srcarms),
                "inert_subvalues": inert_sv, "moved_subvalues": moved_sv,
                "disagree_subvalues": dis_sv,
            }

    json.dump(decomposed, open(os.path.join(HERE, "decomposed_fields.json"), "w"),
              indent=1, sort_keys=True)
    print("wrote decomposed_fields.json — %d decomposed arms" % len(decomposed))

    # ------------------------------------------------------------------ candidate assembly
    # Candidate rows come from three sources, in this precedence:
    #   1. direct arm whose re-located bits EQUAL a db.json field  (G1 exact)
    #   2. A5 decomposition (dense only)
    #   3. A1 composites
    cand = {}          # "mnem.field" -> list of row dicts (one per carrier/source)

    def add(mnem, field, row):
        cand.setdefault("%s.%s" % (mnem, field), []).append(row)

    arms = stats                    # adjudicate.main() returns the arms dict
    for k, s in arms.items():
        f = s["db_field_at_swept_bits"]
        if not f or s["field"].startswith("byte+"):
            continue
        add(s["instr"], f, {
            "source": "direct", "arm": k, "carrier": s["carrier"],
            "verdict": s["verdict_A3"], "N": s["N_A3"], "D": s["D_A3"],
            "M": s["M_A3"], "I": s["I_A3"], "agreement": s["agreement_A3"],
            "distinct_encodings": s["distinct_encodings"], "dense": s["dense"],
            "width": s["swept_width"], "inert_values": s["inert_values"],
            "victim_skipped": s["victim_skipped"],
            "verdict_literal_prereg": s["verdict_lit"],
        })
    for k, d in decomposed.items():
        add(d["instr"], d["field"], {
            "source": "A5-decomposed", "arm": k, "carrier": d["carrier"],
            "verdict": d["verdict"], "N": d["N"], "D": d["D"], "M": d["M"], "I": d["I"],
            "agreement": d["agreement"], "distinct_encodings": d["subvalues_covered"],
            "dense": d["dense"], "width": d["bits"][1],
            "inert_values": d["inert_subvalues"], "victim_skipped": 0,
            "decomposed_from": d["decomposed_from"],
        })
    for k, c in comp.items():
        mnem, fname = k.split(".", 1)
        add(mnem, fname, {
            "source": "A1-composite", "arm": k, "carrier": c["carrier"],
            "verdict": c["verdict_A3"], "per_byte": c["per_byte"],
            "N": None, "D": None, "M": None, "I": None, "agreement": None,
            "distinct_encodings": None, "dense": False,
            "width": (c["field_bits"] or [0, 0])[1], "inert_values": [], "victim_skipped": 0,
        })

    ORDER = {"stable-live": 0, "inert-envelope": 1, "inert-single-carrier": 2, "withheld": 3}

    merged, withheld, defects = {}, {}, []

    for key, rows in sorted(cand.items()):
        mnem, field = key.split(".", 1)
        # promote single-carrier inertness to inert-envelope only with >= 2 carriers (§4.4)
        carriers_inert = {r["carrier"] for r in rows if r["verdict"] == "inert-single-carrier"}
        if len(carriers_inert) >= 2:
            for r in rows:
                if r["verdict"] == "inert-single-carrier":
                    r["verdict"] = "inert-envelope"
        rows.sort(key=lambda r: (ORDER[r["verdict"]], -(r["M"] or 0), -(r["N"] or 0)))
        best = rows[0]
        disagreeing_carriers = len({r["verdict"] for r in rows}) > 1

        cur = (val["instructions"].get(mnem) or {}).get(field)
        cur_label = cur["label"] if cur else "untested"

        entry = {
            "key": key, "chosen": best, "all_arms": rows,
            "current_label": cur_label,
            "current_evidence": (cur or {}).get("evidence"),
            "current_target": (cur or {}).get("target"),
            "carriers_disagree": disagreeing_carriers,
        }

        # ---- G3 veto
        veto = None
        if mnem in ("carry_gen", "n2_op6") or key in ("n3_mov.dst", "n3_mov.srcA_reg",
                                                      "n3_mov.srcA_uni") or mnem == "mov_zext16" \
           or key in ("ilogic.srcA", "ilogic.srcB", "ilogic.outmod",
                      "iadd2.srcB_ext", "iadd2.srcA"):
            veto = VETO_TEXT.get(key) or VETO_TEXT.get(mnem)
        if veto:
            entry["reason"] = "G3 veto: " + veto
            withheld[key] = entry
            continue

        # ---- statistical verdict
        if best["verdict"] == "withheld":
            entry["reason"] = ("§4.4 withheld: M=%s I=%s D=%s N=%s agreement=%s%s"
                               % (best["M"], best["I"], best["D"], best["N"], best["agreement"],
                                  "" if best.get("dense", True) else
                                  "; and only %s of %s encodings reachable (A4)"
                                  % (best["distinct_encodings"], 1 << best["width"])))
            withheld[key] = entry
            continue
        if best["verdict"] == "inert-single-carrier":
            entry["reason"] = ("§4.4 withheld: never moved an observable, and on exactly ONE "
                               "carrier (%s). Single-carrier inertness is not emitter grade."
                               % best["carrier"])
            withheld[key] = entry
            continue

        label = "hardware-run" if best["verdict"] == "stable-live" else "isolated-byte-diff"

        # ---- G2 no-downgrade / redundancy
        if cur and A.STRENGTH[cur_label] <= A.STRENGTH[label]:
            entry["reason"] = ("G2 redundant: validation.json already records %s (%s, %s) which is "
                               "at least as strong as the %s this evidence supports"
                               % (cur_label, (cur or {}).get("target"), (cur or {}).get("evidence"),
                                  label))
            withheld[key] = entry
            continue

        merged[key] = {"label": label, "range": None, "target": A.TARGET,
                       "evidence": A.EVIDENCE, "note": None, "_stats": entry}

    # No file is written here: stage 3 (emit_deliverables.py) consumes these objects directly and
    # writes field_verdicts.json + withheld.json, which carry every number this stage produced.
    print("candidates: %d merged, %d withheld" % (len(merged), len(withheld)))
    return merged, withheld, arms, decomposed, comp, dbf, dbi, val, flaked


VETO_TEXT = {
    "carry_gen": ("Superseded value-for-value on G17P by EXP-0161 (two independent carriers) and "
                  "already merged as hardware-run/G17P; and db.json RENAMED these fields because "
                  "of EXP-0146 itself (subop->srcA, srcA->srcB), so a name-keyed merge of the "
                  "EXP-0146 rows would write two of them into the wrong field."),
    "n2_op6": ("Superseded: EXP-0157 swept four independent carriers on G17P (vs EXP-0146's two) "
               "and all six fields are already hardware-run/G17P."),
    "n3_mov.dst": ("EXP-0157 measured THE SAME u64eq carrier on G17P and the orchestrator "
                   "explicitly WITHHELD this row under the liveness policy (PROVENANCE.md). "
                   "The M4 arm is the same carrier, so it adds no second structurally different "
                   "carrier; merging it would be inconsistent with that decision."),
    "mov_zext16": ("Descriptor under active repair by EXP-0165 this session (DEF-0161-2); "
                   "EXP-0161's own G17P verdicts are held back because the field names change "
                   "under the fix. Reported as corroboration and as proposed defects instead."),
    "ilogic.srcA": ("EXP-0154 DEF-0154-5: the operand labels are SWAPPED relative to EXP-0146's "
                    "published LUT table, and both fields are already hardware-run/G17P under the "
                    "corrected labelling."),
    "iadd2.srcB_ext": ("EXP-0154 (G17P, 128/128): these bits are the srcA REGISTER SELECTOR "
                       "(reg<<2), not a modifier. db.json carries a verbatim 'Do NOT adopt "
                       "EXP-0146's (v & 0x7C) == 0x00 rule' warning."),
    "iadd2.srcA": ("EXP-0154 DEF-0154-4 + EXP-0158: byte+7 is not the srcA register selector and "
                   "its inertness is refuted on G17P (44/64 sampled values wrong)."),
}
VETO_TEXT["n3_mov.srcA_reg"] = VETO_TEXT["n3_mov.dst"]
VETO_TEXT["n3_mov.srcA_uni"] = VETO_TEXT["n3_mov.dst"]
VETO_TEXT["ilogic.srcB"] = VETO_TEXT["ilogic.srcA"]
VETO_TEXT["ilogic.outmod"] = (
    "G3 target divergence (DEF-0166-5): EXP-0146 (M4, carrier k_logic_and, dense 0..255, both "
    "gated runs agreeing) finds 128 of 256 values move the observable -- every value with bit 7 "
    "CLEAR silently zeroes. EXP-0154 (G17P, synthesized register-dump carrier, 253 sampled) finds "
    "the field INERT across the whole range and records it isolated-byte-diff. That is exactly the "
    "'later experiment found the field inert where EXP-0146 called it live' condition, so the row "
    "is withheld and the divergence reported. Likeliest explanation is the carrier (a store-enable "
    "bit is invisible to a register dump), but that is a hypothesis, not a measurement.")


if __name__ == "__main__":
    main()
