#!/usr/bin/env python3
"""EXP-0201 GATE-E RE-EMISSION -- verdicts recomputed with a satisfied quiet gate.

    python3 analysis/gate_e_reemit.py     -> analysis/field_verdicts_gateE.json

DOES NOT OVERWRITE `analysis/field_verdicts.json`. That file records the verdicts
this experiment reached under its own frozen gate on a busy machine, and
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` section 9 says a superseded result is
preserved, not erased.

WHAT CHANGED, AND WHAT DID NOT
------------------------------
Changed: EXP-0210 ran THIS experiment's frozen harness (`arms201.json`
sha256 80b13594...0f02, identical to the contract; pinned db 2412eac1...; 23/23
remote blobs matching) on an idle, serialized device, forward in `g17p_quiet01`
and REVERSED in `g17p_quiet02`. Gate E's clean-confirmation requirement is met.

Not changed: no hypothesis, no arm, no oracle, no coverage. Every number below is
re-derived from `raw/` by `verdicts.py`'s own functions, never copied from
EXP-0210's summary.

THE LABEL RULE APPLIED HERE (corrections section 2). `hardware-run` requires
semantic checks against an independent predictor OVER THE STATED RANGE, and
`sem_checked == 0` can never produce it. So each label's `range` is the value set
where `analysis/sem_coverage.py` shows the PRE-REGISTERED predictor was confirmed
IN BOTH QUIET RUNS -- not the dispatched domain, which is wider. Where a field has
liveness but no confirmed predictor beyond a single point, the label is
`isolated-byte-diff`; where the carrier could not see the field at all, it stays
`untested`.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import verdicts as V                                            # noqa: E402

PAIR = [os.path.join(EXP, "raw", "g17p_quiet01"),
        os.path.join(EXP, "raw", "g17p_quiet02")]

# label, stated range, and the semantics-axis wording -- one entry per field,
# each justified by analysis/sem_coverage.json and RESULTS-GATE-E.md.
DECISION = {
    "falu3.op": {
        "label": "hardware-run",
        "range": "0..255 dense (256 values, 256 distinct ACTUAL dispatched "
                 "encodings). Pre-registered predictor CONFIRMED on 48 of 256 in "
                 "both quiet runs: the 16 values with (v & 0xC0) == 0 and "
                 "(v & 7) in {4,6}, which compute -b and a*b+c bit-exactly, and "
                 "the 32 values with (v & 7) == 7, which are contained faults. "
                 "REFUTED on 176. Outside those 48 the field is live with role "
                 "unknown; do not extrapolate.",
        "semantics": "bounded-map over 48 of 256 values; live, role unknown "
                     "elsewhere",
    },
    "falu3_ext.op": {
        "label": "hardware-run",
        "range": "0..255 dense (256 values, 256 distinct ACTUAL dispatched "
                 "encodings). Pre-registered predictor CONFIRMED on 40 of 256 in "
                 "both quiet runs: the 8 values (v & 0xC7) == 0x06, which compute "
                 "the saturating a*b+c bit-exactly, and the 32 values "
                 "(v & 7) == 7, which are contained faults. REFUTED on 184. "
                 "Outside those 40 the field is live with role unknown.",
        "semantics": "bounded-map over 40 of 256 values; live, role unknown "
                     "elsewhere",
    },
    "fspecial_est.srcA": {
        "label": "untested",
        "range": "0..255 dense (256 values, 256 distinct ACTUAL dispatched "
                 "encodings) on 5 carriers. NOT a coverage gap -- a DETECTION "
                 "POWER gap: gate B fails on every arm.",
        "semantics": "unknown -- carrier-undecidable",
    },
    "falu3_srcmod12.opsel": {
        "label": "isolated-byte-diff",
        "range": "0..7 dense, 8 distinct ACTUAL dispatched encodings, but the "
                 "ENCODABLE range inside this mnemonic is 4 values {2,3,6,7} "
                 "(DEF-0201-1: the field span overlaps its own match bit 17). "
                 "Predicted effect confirmed at ONE point, v = 6 (a*b+c); the "
                 "other three in-mnemonic values move but are unpredicted.",
        "semantics": "hypothesis -- confirmed at 1 of 4 encodable values",
    },
    "falu3_srcmod12.ctrl": {
        "label": "isolated-byte-diff",
        "range": "0..127 dense, 128 distinct ACTUAL dispatched encodings. "
                 "Predicted effect confirmed at ONE point, v = 0x03; the accept "
                 "set is exactly {0x03}. The length model 6 + 2*(v & 3) is not "
                 "contradicted, but that is FRAMING, not operand semantics.",
        "semantics": "hypothesis -- confirmed at 1 of 128 values, plus an "
                     "uncontradicted framing rule",
    },
    "copysign.operands": {
        "label": "hardware-run",
        "range": "0..255 dense (256 values, 256 distinct ACTUAL dispatched "
                 "encodings). Predictor confirmed over the FULL range: the accept "
                 "rule (v & 0x7E) == 0x00 holds 4/4, all 252 other values fail as "
                 "predicted, and the inert-bit equivalence f(v) == f(v ^ 0x81) "
                 "holds 128/128 pairs on three arms in both quiet runs with ZERO "
                 "violations. THE LABEL LICENSES ONLY: emit 0x00, 0x01, 0x80 or "
                 "0x81. It licenses NO inference about which operand or register "
                 "the byte names -- see DEF-0201-3, the operand ROLE is not in "
                 "this byte.",
        "semantics": "bounded-map for the ACCEPT RULE over the full range; the "
                     "operand ROLE is unknown (DEF-0201-3). If the merge prefers "
                     "a single axis value, `live; role unknown` is the honest "
                     "reading of the role and is not contradicted here.",
    },
}


def main():
    recs = V.load(PAIR)
    rnames = [os.path.basename(p) for p in PAIR]
    q1 = V.quiet(PAIR)
    q2 = V.quiet_v2(PAIR)
    sem = json.load(open(os.path.join(HERE, "sem_coverage.json")))
    prior = json.load(open(os.path.join(HERE, "field_verdicts.json")))

    quiet_ok = all(q2[r]["quiet_v2"] for r in rnames)
    out = {}
    for mnem, field in V.TARGETS:
        key = "%s.%s" % (mnem, field)
        arms = V.analyse(recs, mnem, field, rnames)
        chosen = sem[key]["best_arm"] if sem[key]["best_arm"] in arms else \
            min(arms, key=lambda k: len(V.rule(arms[k], len(rnames), quiet_ok)[1]))
        e = arms[chosen]
        verdict, why = V.rule(e, len(rnames), quiet_ok)
        d = DECISION[key]
        s = sem[key]["arms"][sem[key]["best_arm"]]
        out[key] = {
            "label": d["label"],
            "range": d["range"],
            "target": "G17P",
            "evidence": ["EXP-0201", "EXP-0210"],
            "start": e_start(recs, mnem, field), "width": e_width(recs, mnem, field),
            "note": "",                       # filled by notes() below
            "gate_verdict": verdict,
            "gate_blocking_reasons": why,
            "values_dispatched": e["L_legal_values"],
            "distinct_bytes": e["distinct_bytes"],
            "distinct_actual_encodings":
                e["gateA_ledger"]["distinct_actual_encodings"],
            "encodable_range": 4 if key == "falu3_srcmod12.opsel"
                               else e["L_legal_values"],
            "distinct_oracles": e["distinct_oracles"],
            "V_distinct_valid_payloads": e["V_distinct_valid_payloads"],
            "moved": e["moved"], "moved_min": e["moved_min"],
            "disagree": e["disagree"], "common": e["common"],
            "cross_run_agree_pct": e["cross_run_agree_pct"],
            "control_moved": e["control_moved"],
            "falsifier_moved": e["falsifier_moved"],
            "hard_outcomes": e["hard_outcomes"],
            "accept_values": e["accept_values"],
            "n_arms": len(arms),
            "chosen_arm": chosen,
            "gateA_ledger": e["gateA_ledger"],
            "sem_checked": e["sem_checked"], "sem_confirmed": e["sem_confirmed"],
            "semantic_buckets": e["semantic_buckets"],
            "sem_coverage": {
                "arm": sem[key]["best_arm"],
                "vector_predicted": s["vector_predicted"],
                "vector_confirmed": s["vector_confirmed"],
                "vector_refuted": s["vector_refuted"],
                "fault_predicted": s["fault_predicted"],
                "fault_confirmed": s["fault_confirmed"],
                "inert_bit_equivalence": s["inert_bit_equivalence"],
                "confirmed_total_both_runs": sem[key]["sem_confirmed_total"],
            },
            "axes": dict(V.axes(e, quiet_ok, len(rnames)),
                         semantics=d["semantics"]),
            "quiet_confirmation": True,
            "superseded_verdict": {
                "source": "analysis/field_verdicts.json",
                "label": prior.get(key, {}).get("label"),
                "verdict": prior.get(key, {}).get("verdict"),
                "reason": "busy-machine pair; gate E CONTAMINATED",
                "cross_run_agree_pct": prior.get(key, {}).get("cross_run_agree_pct"),
            },
        }
    notes(out)
    out["_meta"] = meta(q1, q2, rnames)
    out["db_defects"] = json.load(open(os.path.join(HERE, "field_verdicts.json")))["db_defects"]
    json.dump(out, open(os.path.join(HERE, "field_verdicts_gateE.json"), "w"),
              indent=1, default=str)
    print("quiet gate: v1_strict=%s  v2=%s" %
          ([q1[r]["quiet"] for r in rnames], [q2[r]["quiet_v2"] for r in rnames]))
    for k, v in out.items():
        if k.startswith("_") or k == "db_defects":
            continue
        print("  %-24s %-19s conf=%-4s/%-4s moved=%-4s dis=%-3s agree=%s"
              % (k, v["label"], v["sem_coverage"]["confirmed_total_both_runs"],
                 v["values_dispatched"], v["moved_min"], v["disagree"],
                 ("%.4f%%" % v["cross_run_agree_pct"])
                 if v["cross_run_agree_pct"] is not None else "-"))
    return 0


def e_start(recs, m, f):
    return next(r["start"] for r in recs if r.get("instr") == m and r.get("field") == f)


def e_width(recs, m, f):
    return next(r["width"] for r in recs if r.get("instr") == m and r.get("field") == f)


def notes(out):
    src = json.load(open(os.path.join(HERE, "field_verdicts.json")))
    add = {
        "falu3.op": " GATE E NOW SATISFIED (EXP-0210 quiet pair, forward + "
                    "reversed): 0 cross-run disagreements. NOTE THE FAULT-CLASS "
                    "CORRECTION: on the quiet device (v&7)==7 is 32/32 CONTAINED "
                    "FAULTS; the busy pair reported the same 32 values as "
                    "not_written. The busy machine MASKED faults as OK-but-wrote-"
                    "nothing, so any fault-class claim is scoped to machine state.",
        "falu3_ext.op": " GATE E NOW SATISFIED. Same fault-class correction: "
                        "(v&7)==7 is 32/32 contained faults on the quiet device "
                        "vs 8 fault + 24 not_written on the busy pair.",
        "fspecial_est.srcA": " GATE E NOW SATISFIED and IT CHANGES NOTHING: the "
                             "blocker was never E. Gate B fails on all five arms "
                             "and still does on the quiet pair. The inert-bit "
                             "equivalence f(v)==f(v^0x80) is REFUTED at exactly "
                             "one pair, which is the 0x81 effect.",
        "falu3_srcmod12.opsel": " GATE E NOW SATISFIED: 0 cross-run "
                               "disagreements over all 8 dispatched values.",
        "falu3_srcmod12.ctrl": " GATE E NOW SATISFIED: 0 cross-run "
                              "disagreements over all 128 values.",
        "copysign.operands": " GATE E NOW SATISFIED: 0 cross-run disagreements "
                             "over all 256 values, both orders.",
    }
    for k, v in out.items():
        v["note"] = (src.get(k, {}).get("note", "") + add.get(k, "")).strip()


def meta(q1, q2, rnames):
    return {
        "experiment": "EXP-0201-g17p-float-alu-sixfield",
        "supersedes": "analysis/field_verdicts.json (busy-machine pair, all six "
                      "NOT PROMOTED on gate E)",
        "confirmation_pair": ["g17p_quiet01 (forward)", "g17p_quiet02 (reverse)"],
        "captured_by": "EXP-0210-quiet-confirmation, running THIS experiment's "
                       "frozen harness: arms201.json sha256 "
                       "80b13594060525d33654b1690040aa9ca6764a475680d0920a3547a02de789d5 "
                       "(identical to CAPTURE_CONTRACT.json), pinned db.json "
                       "2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4",
        "quiet_model_v1_strict": {r: q1[r] for r in rnames},
        "quiet_model_v2_amended": {r: q2[r] for r in rnames},
        "quiet_model_amendment": "AMENDMENT B, verdicts.quiet_v2(): "
            "MTLCompilerService is an XPC service launchd owns, so it can never "
            "be a descendant of the sampler and ppid attribution is structurally "
            "impossible; our own run compiles 21 carriers and therefore "
            "necessarily produces one. The strict model could only ever move "
            "toward CONTAMINATED and did, on 1 sample of 273 in g17p_quiet02. "
            "v2 counts foreign DISPATCH runners and foreign shdump only. This is "
            "a LOOSENING, recorded as one; both figures are reported.",
        "corroborating_independent_instrument":
            "experiments/EXP-0210-quiet-confirmation/raw/e0201_q01/quietcheck.json "
            "and .../e0201_q02/quietcheck.json -- max_foreign_runner 0, "
            "max_foreign_legacy_incl_compiler_svc 0, busy_count 0, renderer_util 0, "
            "Q2a_no_foreign_reset true, 274 samples over 554 s each.",
        "fault_class_caveat": "Silent-no-write outcomes on the busy pair became "
            "contained faults on the quiet pair (not_written 444/449 -> 160, "
            "fault 37/31 -> 355, identical in both orders). The ok/not-ok "
            "partition is UNCHANGED: 0 differences over 5272 target cases, and "
            "ok = 86 in all four runs. Severity labels are scoped to machine "
            "state; the accept sets are not.",
        "label_rule": "RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 2 -- "
                      "hardware-run only over the range where the pre-registered "
                      "predictor was confirmed in BOTH quiet runs.",
    }


if __name__ == "__main__":
    sys.exit(main())
