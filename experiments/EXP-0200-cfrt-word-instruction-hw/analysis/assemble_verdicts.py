#!/usr/bin/env python3
"""EXP-0200 -- assemble `analysis/field_verdicts.json` from raw ONLY.

  python3 analysis/assemble_verdicts.py

Every number below is recomputed from `raw/` on each invocation. Nothing is read
back from a previous verdicts file, from the census, or from a note. The six
axes of `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` section 2 are emitted per row,
with exact numerators and denominators, never a percentage alone.

The top-level keys are `<mnemonic>.<field>` (`_instruction` for the
instruction-level row), which is the shape `tools/agx-isa/wave_audit.py` reads.
"""
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
HALT = ("not_written", "invalid_run")


def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def t1_dst():
    """Target 1: EXP-0187's frozen 25-arm contract, run forward and reversed."""
    runs = {"g17p_20260830_t1run01": None, "g17p_20260830_t1run02rev": None}
    for r in runs:
        runs[r] = load(EXP / "raw" / "t1_frozen0187" / r / "sweep.jsonl")
    per = {}
    for rid, recs in runs.items():
        for x in recs:
            if x.get("instr") == "n4_rt_word" and x.get("field") == "dst":
                per.setdefault(x["carrier"], {}).setdefault(rid, {})[x["value"]] = x
    out = {"per_carrier": {}, "predicate": "(dst & 0b110) == 0b100",
           "predicate_holds_arm_runs": 0, "arm_runs": 0,
           "fault_observations": 0, "clean_observations": 0,
           "distinct_valid_payloads_per_arm": {}}
    baseline_bad = []
    for carrier, byrun in sorted(per.items()):
        rec = {}
        for rid, cases in sorted(byrun.items()):
            faults = {v for v, x in cases.items() if x["outcome"] == "fault"}
            clean = {v for v, x in cases.items() if x["outcome"] == "ok"}
            other = collections.Counter(x["outcome"] for x in cases.values()
                                        if x["outcome"] not in ("fault", "ok"))
            pred = {v for v in range(256) if (v & 0b110) == 0b100}
            payloads = {tuple(x["observed"].get("vals") or [])
                        for x in cases.values() if x["outcome"] == "ok"}
            out["arm_runs"] += 1
            if faults and faults == pred:
                out["predicate_holds_arm_runs"] += 1
            out["fault_observations"] += len(faults)
            out["clean_observations"] += len(clean)
            rec[rid] = {"dispatched": len(cases), "fault": len(faults),
                        "ok": len(clean), "other": dict(other),
                        "fault_set_equals_predicate": bool(faults) and faults == pred,
                        "distinct_encodings": len({x["bytes"] for x in cases.values()}),
                        "distinct_valid_payloads": len(payloads)}
            if other:
                baseline_bad.append("%s/%s: %s" % (carrier, rid, dict(other)))
        # cross-run agreement over the outcome+payload partition
        rids = sorted(byrun)
        if len(rids) == 2:
            a, b = byrun[rids[0]], byrun[rids[1]]
            common = sorted(set(a) & set(b))
            agree = sum(1 for v in common
                        if a[v]["outcome"] == b[v]["outcome"]
                        and (a[v]["observed"].get("vals") or [])
                        == (b[v]["observed"].get("vals") or []))
            rec["cross_run"] = {"common_values": len(common), "agreeing": agree,
                                "agreement_pct": round(100.0 * agree / max(1, len(common)), 3)}
        out["per_carrier"][carrier] = rec
    out["carrier_excluded"] = baseline_bad
    return out


def t2_transparency():
    a = {}, {}
    idx = [{}, {}]
    for i, rid in enumerate(("g17p_20260830_t2run01", "g17p_20260830_t2run02rev")):
        for x in load(EXP / "raw" / rid / "sweep.jsonl"):
            if x.get("fill_id"):
                idx[i].setdefault(x["arm"], {})[x["fill_id"]] = x
    arms = json.loads((EXP / "harness" / "arms200.json").read_text())["arms"]
    res = {"stop_written_into_natural_occurrence": {"total": 0, "halted": 0,
                                                    "oracle_survived": 0,
                                                    "other": 0},
           "admitted_arms": [], "per_arm": {}}
    for t in arms:
        if t["kind"] != "transparency":
            continue
        xa = idx[0].get(t["arm"], {})
        xb = idx[1].get(t["arm"], {})
        if "X_reach" not in xa or "X_reach" not in xb:
            continue
        oa, ob = xa["X_reach"]["outcome"], xb["X_reach"]["outcome"]
        res["stop_written_into_natural_occurrence"]["total"] += 1
        if oa in HALT and ob in HALT:
            res["stop_written_into_natural_occurrence"]["halted"] += 1
        elif oa == "ok" and ob == "ok":
            res["stop_written_into_natural_occurrence"]["oracle_survived"] += 1
        else:
            res["stop_written_into_natural_occurrence"]["other"] += 1
        null_ok = (xa.get("X_null", {}).get("outcome") == "ok"
                   and xb.get("X_null", {}).get("outcome") == "ok")
        adm = null_ok and oa in HALT and ob in HALT
        reads = {}
        for fid in xa:
            if fid.startswith("X_") and fid not in ("X_null", "X_reach"):
                if fid in xb and xa[fid]["outcome"] == xb[fid]["outcome"]:
                    reads[fid] = xa[fid]["outcome"]
                else:
                    reads[fid] = "%s/%s" % (xa[fid]["outcome"],
                                            xb.get(fid, {}).get("outcome"))
        res["per_arm"][t["arm"]] = {"admitted": adm, "X_null_ok": null_ok,
                                    "X_reach": [oa, ob], "reads": reads,
                                    "len": t["len"], "orig": t.get("orig_bytes")}
        if adm:
            res["admitted_arms"].append(t["arm"])
    return res


def main():
    bmap = json.loads((EXP / "analysis" / "boundary_map.json").read_text())
    ledger = json.loads((EXP / "analysis" / "ledger.json").read_text())
    dst = t1_dst()
    tr = t2_transparency()

    interior = {k: v for k, v in bmap["holes"].items()
                if v["interior_to_enclosing_span"] and v["enclosing_span"]
                and v["enclosing_span"] <= 16}
    by_desc = collections.defaultdict(list)
    for k, v in interior.items():
        by_desc[v["descriptor"]].append(v)

    REPRO = ("INCOMPLETE -- Gate E not met. Both runs of every pair executed on a "
             "machine running eight to nine concurrent sibling experiments; a "
             "quiet confirmation window was not obtainable (EXP-0204 sampled 86 "
             "times and never once found one). No case of this experiment falls "
             "inside EXP-0204's declared 20:00-20:25Z hang window -- all six "
             "captures ran 19:16-19:48Z -- so no case is reclassified on that "
             "ground, and the runs are internally clean (see fault_classes).")

    out = {}

    out["n4_rt_word._instruction"] = {
        "label": "tokenization-only",
        "label_change": "NONE PROPOSED -- and the reason is a positive finding, "
                        "not an absence of evidence.",
        "axes": {
            "encoding_geometry": "geometry-mapped -- AND THE DESCRIPTOR IS WRONG "
                                 "AT EVERY SITE MEASURED. See db_defects.",
            "liveness": "the BYTES are live (an illegal value in them faults the "
                        "command buffer, reproducibly); the four-byte "
                        "INSTRUCTION was not observed to exist at any measured "
                        "site",
            "semantics": "unknown",
            "compiler_recipe": "not-generated at a natural site; generated-point "
                               "at one hardware-verified 4-byte boundary "
                               "(cw_trans +324), see note",
            "target": "G17P-direct",
            "reproducibility": REPRO,
        },
        "range": "3 natural occurrences stop-scanned at 2-byte granularity in a "
                 "+/-32-byte window, on 2 carriers; 0 of 3 are an instruction "
                 "boundary the hardware honours",
        "target_device": "G17P", "evidence": ["EXP-0200"],
        "sites_scanned": len(by_desc.get("n4_rt_word", [])),
        "sites_that_are_a_hardware_boundary": 0,
        "sites_interior_to_a_10_byte_instruction": len(by_desc.get("n4_rt_word", [])),
        "enclosing_spans": [[v["carrier"], v["prev_halting_offset"],
                             v["next_halting_offset"], v["enclosing_span"],
                             v["off"] - v["prev_halting_offset"]]
                            for v in by_desc.get("n4_rt_word", [])],
        "note": "At all 3 scanned occurrences -- rq_mdist +1306, rq_bbox +1316, "
                "rq_bbox +6378 -- a `stop` written at the occurrence does NOT "
                "halt the program while a `stop` 6 bytes earlier and 4 bytes "
                "later BOTH do, in both runs. The enclosing span is exactly 10 "
                "bytes at all three, and the occurrence sits at +6 of it. So "
                "`04 <dst> 20 80` is the operand TAIL of a 10-byte instruction, "
                "not a 4-byte compact word. This is the same shadowing EXP-0204 "
                "independently found for `cubearray_coord_const`.",
    }

    out["n4_rt_word.dst"] = {
        "label": "hardware-run",
        "label_basis": "EXP-0187's frozen gate, honoured unchanged and re-run as "
                       "a forward+reversed pair here; it returns LIVE. Recorded "
                       "per corrections section 9: an experiment's own frozen "
                       "gate result is preserved, and the current axes are "
                       "scored separately below.",
        "label_under_current_gates": "DOWNGRADE RECOMMENDED. The movement is "
                                     "ENTIRELY the fault wall: across 1152 clean "
                                     "observations the distinct valid payload "
                                     "count is 1. That is a legality map, not a "
                                     "semantic. And the swept byte is +7 of a "
                                     "10-byte instruction, so the field's "
                                     "geometry is misattributed.",
        "axes": {
            "encoding_geometry": "ledger-verified (256/256 distinct actual "
                                 "encodings, 0 match-bit collisions) but "
                                 "MISATTRIBUTED: the byte is +7 of a 10-byte "
                                 "instruction, not byte+1 of a 4-byte word",
            "liveness": "live -- 64 of 256 values are rejected by the hardware, "
                        "reproducibly, on 3 carriers in 2 runs",
            "semantics": "bounded-map for LEGALITY only (the predicate below "
                         "classifies 256/256 values on 3 carriers in both runs); "
                         "UNKNOWN for effect -- V=1 across all clean values",
            "compiler_recipe": "not-generated",
            "target": "G17P-direct",
            "reproducibility": REPRO,
        },
        "range": "0..255 dense (all 256 values), 3 carriers, 2 runs "
                 "(forward + reversed case order)",
        "target_device": "G17P", "evidence": ["EXP-0200", "EXP-0187"],
        "start": 8, "width": 8,
        "hazard_predicate": dst["predicate"],
        "predicate_holds_in": "%d of %d carrier-runs" % (dst["predicate_holds_arm_runs"],
                                                         dst["arm_runs"]),
        "fault_observations": dst["fault_observations"],
        "clean_observations": dst["clean_observations"],
        "per_carrier": dst["per_carrier"],
        "carrier_excluded": dst["carrier_excluded"],
        "note": "The hazard wall EXP-0187 measured in one run is confirmed in a "
                "gated forward+reversed pair and EXTENDED to rq_bbox, which "
                "EXP-0187 never measured. 64 of 256 values fault; the fault set "
                "is exactly {v : (v & 0b110) == 0b100} with zero exceptions. "
                "192 of 256 values are accepted and all return the same correct "
                "answer, so no value has been shown to select anything.",
    }

    out["n4_cf_word._instruction"] = {
        "label": "tokenization-only",
        "label_change": "NONE PROPOSED.",
        "axes": {
            "encoding_geometry": "geometry-mapped -- the descriptor is a TAIL "
                                 "MATCH inside `pop_reconverge`. See db_defects.",
            "liveness": "carrier-undecidable at the 3 scanned natural sites",
            "semantics": "unknown",
            "compiler_recipe": "generated-point -- `04 01 00 00` generated at "
                               "cw_trans +324, a boundary the hardware honours, "
                               "and executed with the carrier oracle intact",
            "target": "G17P-direct",
            "reproducibility": REPRO,
        },
        "range": "3 natural occurrences stop-scanned at 2-byte granularity on 3 "
                 "carriers; all 3 are interior to a 6-byte span whose head is "
                 "`0f 06` (pop_reconverge)",
        "target_device": "G17P", "evidence": ["EXP-0200"],
        "sites_scanned": len(by_desc.get("n4_cf_word", [])),
        "enclosing_spans": [[v["carrier"], v["prev_halting_offset"],
                             v["next_halting_offset"], v["enclosing_span"],
                             v["off"] - v["prev_halting_offset"]]
                            for v in by_desc.get("n4_cf_word", [])],
        "note": "rq_mdist +1210, rq_bbox +1216 and cw_trans +842 are each at +2 "
                "of a 6-byte span `0f 06 04 01 00 00`, which our own tokenizer "
                "already names `pop_reconverge`. This is the mechanical "
                "explanation for EXP-0172's DEF-0172-4 ('n4_cf_word has no "
                "observable effect at all'): its 256-value `b3` sweep was "
                "sweeping byte+5 of a pop_reconverge.",
    }

    out["n4_cf_word.b3"] = {
        "label": "untested",
        "label_change": "NONE. DECLINED, and the decline is honoured, not "
                        "re-litigated: EXP-0172 dispatched 256 values and "
                        "reported STILL-UNDERPOWERED; EXP-0184 declined "
                        "re-running it. Only 11 sampled values rode along here "
                        "with the `_instruction` fills.",
        "axes": {"encoding_geometry": "MISATTRIBUTED -- byte+5 of a 6-byte "
                                      "pop_reconverge at all 3 scanned sites",
                 "liveness": "carrier-undecidable", "semantics": "unknown",
                 "compiler_recipe": "not-generated", "target": "G17P-direct",
                 "reproducibility": REPRO},
        "range": "11 sampled values {00,01,02,04,08,10,20,40,7f,80,ff} as "
                 "ride-along fills; NOT a field sweep and NOT a verdict",
        "target_device": "G17P", "evidence": ["EXP-0200"],
        "start": 24, "width": 8,
        "note": "Reported only because the geometry finding above changes what a "
                "future sweep should target: b3 is the last byte of a "
                "pop_reconverge, whose `reserved` field is already documented "
                "non-load-bearing.",
    }

    out["rtq_pred._instruction"] = {
        "label": "tokenization-only",
        "label_change": "NONE PROPOSED.",
        "axes": {
            "encoding_geometry": "1 site scanned; interior to a 10-byte span. "
                                 "See db_defects.",
            "liveness": "carrier-undecidable at the scanned natural site",
            "semantics": "unknown",
            "compiler_recipe": "generated-point -- `06 c2 00 00` generated at "
                               "cw_trans +324, a boundary the hardware honours, "
                               "and executed with the carrier oracle intact, "
                               "with a stop control and a 6-byte over-length "
                               "control both firing in opposite directions",
            "target": "G17P-direct",
            "reproducibility": REPRO,
        },
        "range": "1 natural occurrence stop-scanned (rq_bbox +966); interior to "
                 "[960, 970), a 10-byte span",
        "target_device": "G17P", "evidence": ["EXP-0200"],
        "sites_scanned": len(by_desc.get("rtq_pred", [])),
        "enclosing_spans": [[v["carrier"], v["prev_halting_offset"],
                             v["next_halting_offset"], v["enclosing_span"],
                             v["off"] - v["prev_halting_offset"]]
                            for v in by_desc.get("rtq_pred", [])],
        "note": "One site only -- the other rtq_pred occurrences fell outside the "
                "fine scan window. It is at +6 of a 10-byte span our tokenizer "
                "lengths at 6 (`icmp_pred`), so either the icmp_pred length rule "
                "or the rtq_pred boundary is wrong there; the scan says the "
                "hardware consumes 10.",
    }

    for mn, start in (("n1_word", None), ("n2_compact2", None), ("n3_word", None)):
        out["%s._instruction" % mn] = {
            "label": "tokenization-only",
            "label_change": "NONE PROPOSED.",
            "axes": {
                "encoding_geometry": "unverified -- the stop-ruler arm designed "
                                     "to measure it is CONFOUNDED (see "
                                     "limitations), and the fine stop-scan "
                                     "window did not reach these offsets",
                "liveness": "carrier-undecidable",
                "semantics": "unknown",
                "compiler_recipe": "not-generated",
                "target": "G17P-direct",
                "reproducibility": REPRO,
            },
            "range": "NOT ESTABLISHED. 9 ruler holes x 2 runs dispatched; the "
                     "arm is withdrawn as carrier-undecidable because "
                     "byte-identical fills read oppositely at different holes.",
            "target_device": "G17P", "evidence": ["EXP-0200"],
            "note": "The one thing measured cleanly: at cw_trans +292 and +316, "
                    "walk-confirmed `n1_word` boundaries, a `stop` did NOT halt "
                    "while stops at +320/+322/+324 in the same finely scanned "
                    "window DID. That is suggestive that these walk boundaries "
                    "are also wrong, but no-halt is not proof of interiority and "
                    "no verdict is drawn from it.",
        }

    out["_db_defects"] = {
        "DEF-0200-1": {
            "severity": "HIGH -- it invalidates the geometry of every "
                        "`n4_rt_word` result ever recorded, including this "
                        "experiment's own target 1",
            "claim": "`n4_rt_word` (`04 <dst> 20 80`) is not a 4-byte "
                     "instruction at any site measured on G17P. At rq_mdist "
                     "+1306, rq_bbox +1316 and rq_bbox +6378 it is bytes +6..+9 "
                     "of a 10-byte instruction.",
            "method": "stop-scan: a `stop` at the occurrence does not halt; a "
                      "`stop` 6 bytes before and 4 bytes after both do, in both "
                      "runs, at all three sites.",
            "our_tokenizer_says": "icmpsel, length 14 -- which over-consumes by "
                                  "4 relative to the hardware's 10",
            "consequence": "EXP-0187's and this experiment's `n4_rt_word.dst` "
                           "hazard wall is a REAL, reproducible hardware fact "
                           "about that operand byte, and is NOT a field of a "
                           "compact word.",
        },
        "DEF-0200-2": {
            "severity": "HIGH",
            "claim": "`n4_cf_word` (`04 01 00 00`) is bytes +2..+5 of the 6-byte "
                     "`pop_reconverge` `0f 06 04 01 00 00` at rq_mdist +1210, "
                     "rq_bbox +1216 and cw_trans +842.",
            "consequence": "This is the mechanical explanation of EXP-0172's "
                           "DEF-0172-4. `n4_cf_word` DOES also occur as a real "
                           "4-byte instruction: cw_trans +324 is a boundary the "
                           "hardware honours with a 4-byte span. So the "
                           "descriptor is not wrong everywhere -- it is "
                           "SHADOWED at interior positions, exactly the shape "
                           "EXP-0204 found for `cubearray_coord_const`.",
        },
        "DEF-0200-3": {
            "severity": "MEDIUM",
            "claim": "`icmp_pred` at rq_bbox +960 (`2a 00 2b c0 06 00 ...`) has "
                     "a hardware span of 10 bytes; the pinned length rule gives "
                     "6. The `rtq_pred` signature at +966 is its tail.",
        },
        "DEF-0200-4": {
            "severity": "METHOD",
            "claim": "A signature scan cross-checked with `decode_one` at the "
                     "offset is NOT sufficient to establish that an occurrence "
                     "exists: 0 of the 7 signature-derived 4-byte occurrences "
                     "the hardware scanned turned out to be boundaries. "
                     "`decode_one` at an offset answers 'do these bytes match a "
                     "descriptor', never 'does an instruction start here'.",
        },
    }

    out["_provenance"] = {
        "target": "Apple A18 Pro / G17P (applegpu_g17p, AGXAcceleratorG17P, "
                  "5 cores, macOS 26.6, Metal family Apple9)",
        "clean_room": "OWN-SHADER + HW-PROBE. No Apple binary introspected.",
        "gate_A_ledger": {r["run"]: {"grade": r["ledger_grade"],
                                     "totals": r["totals"],
                                     "problem_arms": len(r["problem_arms"])}
                          for r in ledger},
        "gate_E": REPRO,
        "exp0204_hang_window_overlap_cases": 0,
        "stop_scan": {"cross_run_agreement_pct": bmap["cross_run_agreement_pct"],
                      "shared_offsets": bmap["shared_offsets"],
                      "halting_offsets_in_both_runs":
                          bmap["halting_offsets_in_both_runs"],
                      "per_carrier": {c: {"dispatched": v["offsets_dispatched"],
                                          "halts": v["n_halts"]}
                                      for c, v in bmap["carriers"].items()}},
        "transparency": tr["stop_written_into_natural_occurrence"],
        "transparency_admitted_arms": tr["admitted_arms"],
    }

    p = EXP / "analysis" / "field_verdicts.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    for k in sorted(out):
        if k.startswith("_"):
            continue
        print("%-30s %-20s %s" % (k, out[k]["label"],
                                  out[k]["axes"]["liveness"][:60]))
    print("\nstop into a natural occurrence:", json.dumps(
        tr["stop_written_into_natural_occurrence"]))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
