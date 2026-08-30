#!/usr/bin/env python3
"""EXP-0178 headline answers, computed MECHANICALLY from the two gated runs.

RESULTS.md must answer two questions in plain words. This script derives both
from `raw/`, so the prose in RESULTS.md is a reading of a committed artefact
rather than a recollection.

  Q1  Can a compiler back end emit a system-value read on G17P?
  Q2  Does EXP-0147's silent-zero tile-read hazard reproduce on G17P?

For Q1 it also re-tests the M4 priors as CROSS-TARGET hypotheses -- they are
hypotheses here, never premises:

  H2  `sr_sel` bit 7 is a structural discriminator: 0x80-0xFF reads the
      special-register file, 0x00-0x7F materialises the selector byte ITSELF,
      and NO value anywhere in 0x00-0xFF faults        (EXP-0092, M4)
  H3  the SR namespace is stage-contextual              (EXP-0031)

For Q2 the M4 priors under test are:

  read_en   byte+6 bit 0 gates the read: odd correct, EVEN -> SILENT ZERO, no fault
  rt_index  correct only on a small set; every other index SILENTLY ZEROES
  fmt       correct only at {0x2e,0x2f,0x6e,0x6f,0xae,0xaf,0xee,0xef}
                                                        (all EXP-0147, M4)

  python3 analysis/answers.py --run01 raw/<id1> --run02 raw/<id2>
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))

M4_FMT_LEGAL = {0x2e, 0x2f, 0x6e, 0x6f, 0xae, 0xaf, 0xee, 0xef}


def load(rundir):
    out = []
    with open(os.path.join(rundir, "sweep.jsonl")) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def index(recs, kind):
    return [r for r in recs if r.get("kind") == kind]


def measurement_health(r1, r2, arm):
    """DEF-0178-1 surfacing. A `measurement_failed` case is a malformed or
    unparseable runner response -- NOT an observation, and specifically not a
    hang and not a fault. The defect has widened: a mere watchdog TIMEOUT, not a
    real hang, is enough to start the false cascade on the shared driver, so the
    suspect set is any run whose runner ever timed out. Reporting the count per
    arm lets a reviewer see at a glance whether an arm's null result is sitting
    on top of a measurement problem."""
    out = {}
    for tag, recs in (("run01", r1), ("run02", r2)):
        cases = [x for x in recs if x.get("kind") == "case" and x["arm"] == arm]
        mf = [x for x in cases if x["outcome"] == "measurement_failed"]
        hangs = [x for x in cases if x["outcome"] == "hang"]
        out[tag] = {
            "cases": len(cases),
            "measurement_failed": len(mf),
            "measurement_failed_pct": round(100.0 * len(mf) / len(cases), 3) if cases else 0.0,
            "measurement_failed_by_field": dict(collections.Counter(
                x["field"] for x in mf)),
            "hang": len(hangs),
            "invalid_run_victims": sum(1 for x in cases if x["outcome"] == "invalid_run"),
            "victim_strings": dict(collections.Counter(
                (x.get("victim") or "")[:60] for x in cases
                if x["outcome"] == "invalid_run")),
            "not_written": sum(1 for x in cases if x["outcome"] == "not_written"),
            "no_draw_or_dispatch": sum(1 for x in cases
                                       if x["outcome"] in ("no_draw", "no_dispatch")),
            "runner_restarts": sum(x.get("restarts") or 0 for x in cases),
            "sample_raw_lines": next((x.get("raw_lines") for x in mf if x.get("raw_lines")),
                                     None),
        }
    out["verdict"] = ("CLEAN" if all(v["measurement_failed"] == 0 and
                                     v["invalid_run_victims"] == 0
                                     for k, v in out.items() if k.startswith("run"))
                      else "MEASUREMENT FAILURES PRESENT -- read the null results here "
                           "with suspicion; check raw_lines and victim_strings")
    return out


NON_OBSERVATIONS = ("measurement_failed", "invalid_run")


def agreeing(r1, r2, arm, field):
    """Values whose OUTCOME agrees across both gated runs, with the record.

    NON_OBSERVATIONS are dropped first: a malformed runner response and an
    `InnocentVictim` (another context's reset discarding our in-flight command
    buffer) both say nothing about our encoding, so scoring them either way
    would be wrong. FIELD-SWEEP-PROTOCOL section 7."""
    a = {r["value"]: r for r in r1 if r.get("kind") == "case"
         and r["arm"] == arm and r["field"] == field
         and r["outcome"] not in NON_OBSERVATIONS}
    b = {r["value"]: r for r in r2 if r.get("kind") == "case"
         and r["arm"] == arm and r["field"] == field
         and r["outcome"] not in NON_OBSERVATIONS}
    both, dis = {}, []
    for v in sorted(set(a) & set(b)):
        if a[v]["outcome"] == b[v]["outcome"]:
            both[v] = a[v]
        else:
            dis.append({"value": v, "run01": a[v]["outcome"], "run02": b[v]["outcome"]})
    return both, dis, len(set(a) & set(b))


def q1(r1, r2):
    out = {"question": "Can a compiler back end emit a system-value read on G17P?",
           "arms": {}}
    for arm in ("sr_compute", "sr_frag", "sr_vertex"):
        meta = [m for m in index(r1, "arm_meta") if m["arm"] == arm]
        na = [m for m in index(r1, "arm_not_attempted") if m["arm"] == arm]
        if not meta:
            out["arms"][arm] = {"status": "NOT_ATTEMPTED",
                                "why": na[0]["why"] if na else "no arm_meta"}
            continue
        e = {"status": "RAN", "anchor": meta[0]["instr_hex"],
             "anchor_how": meta[0]["how"], "baseline_fields": meta[0]["baseline_field_values"],
             "measurement_health": measurement_health(r1, r2, arm)}
        for tag, recs in (("run01", r1), ("run02", r2)):
            L = [x for x in index(recs, "ladder") if x["arm"] == arm]
            S = [x for x in index(recs, "sensitivity") if x["arm"] == arm]
            P = [x for x in index(recs, "power_probe") if x["arm"] == arm]
            C = [x for x in index(recs, "calibration") if x["arm"] == arm]
            e[tag] = {
                "ladder": {x["field"]: {"moved": x.get("moved"), "outcome": x["outcome"]}
                           for x in L},
                "ladder_all_moved": bool(L) and all(x.get("moved") for x in L),
                "falsifier": [{"outcome": x["outcome"], "moved": x.get("moved")} for x in S],
                "falsifier_failed_as_preregistered": bool(S) and all(
                    x.get("moved") is True or x["outcome"] in
                    ("fault", "hang", "no_draw", "no_dispatch", "not_written") for x in S),
                "power_probe": [{"field": x["field"], "outcome": x["outcome"]} for x in P],
                "calibration": {k: v for k, v in (C[0] if C else {}).items()
                                if k not in ("kind", "arm", "idx", "t", "predicted")},
            }
        both, dis, ncommon = agreeing(r1, r2, arm, "sr_sel")
        oc = collections.Counter(r["outcome"] for r in both.values())
        faults = sorted(v for v, r in both.items()
                        if r["outcome"] in ("fault", "hang"))
        moved = sorted(v for v, r in both.items() if r.get("moved"))
        tokdiff = sorted(v for v, r in both.items() if r.get("tok_same_instr") is False)
        hi = [v for v in both if v & 0x80]
        lo = [v for v in both if not (v & 0x80)]
        e["sr_sel"] = {
            "values_agreeing_across_runs": len(both),
            "values_common": ncommon,
            "agreement_pct": round(100.0 * len(both) / ncommon, 3) if ncommon else 0.0,
            "disagreements": dis[:40],
            "outcomes": dict(oc),
            "moved_count": len(moved),
            "faulting_values": faults,
            "H2_no_value_faults": not faults,
            "H2_bit7_split": {
                "bit7_set_moved": sum(1 for v in hi if both[v].get("moved")),
                "bit7_set_total": len(hi),
                "bit7_clear_moved": sum(1 for v in lo if both[v].get("moved")),
                "bit7_clear_total": len(lo),
            },
            "tokenizes_as_a_different_instruction": tokdiff,
        }
        out["arms"][arm] = e
    # H3: is the same selector byte read differently in different stages?
    out["H3_stage_contextual"] = stage_contrast(r1, r2)
    out["vertex_software_offset"] = vertex_offset(r1, r2)
    return out


def vertex_offset(r1, r2):
    """MEASURE the compiler-inserted constant in the vertex carrier, and report
    the vertex SR readings DIFFERENTIALLY against it.

    `v_sr` writes `float(iid)` where `iid` is MSL's `[[instance_id]]`. If the
    compiler lowers that as `get_sr(0xd8) + baseInstance` -- adding the base in
    SOFTWARE rather than reading a base-inclusive register -- then every spliced
    selector's reading carries the same constant K, and an ABSOLUTE oracle can
    match for the wrong reason. (It did: `0x8a` scored `ok` because the oracle
    predicted 5 and K itself is 5.)

    K is measured, not assumed: several selectors have no vertex-stage meaning
    and must read 0 there, so their common observed value IS K. Reporting how
    many independent selectors agree on it is what makes it a measurement."""
    ZERO_EXPECTED = {0x9c: "threadgroup_position_in_grid.x", 0x9d: "…y", 0x9e: "…z",
                     0xa0: "thread_position_in_grid.x", 0xa1: "…y",
                     0xa4: "thread_position_in_threadgroup.x",
                     0xc5: "front_facing (fragment-only)"}
    both, _, _ = agreeing(r1, r2, "sr_vertex", "sr_sel")
    obs = {}
    for v, r in both.items():
        px = (r.get("observed") or {}).get("pixels")
        if px:
            obs[v] = [p[0] for p in px]
    flats = {}
    for v, vals in obs.items():
        if len(set(round(x, 6) for x in vals)) == 1:
            flats[v] = vals[0]
    cand = {v: flats[v] for v in ZERO_EXPECTED if v in flats}
    ks = sorted(set(cand.values()))
    K = ks[0] if len(ks) == 1 else None
    out = {
        "selectors_expected_to_read_zero_in_a_vertex_program":
            {("0x%02x" % v): ZERO_EXPECTED[v] for v in sorted(ZERO_EXPECTED)},
        "their_observed_values": {("0x%02x" % v): cand[v] for v in sorted(cand)},
        "independent_agreements": len(cand),
        "K_measured": K,
        "K_is_a_measurement_not_an_assumption": (
            "%d independent selectors with no vertex-stage meaning all read the "
            "same value" % len(cand)) if K is not None else
            "NOT DETERMINED: those selectors disagree, so no single constant explains them",
    }
    if K is not None:
        named = {0xdd: "vertex_id", 0xd8: "instance_id",
                 0x88: "base_vertex (db.json enum)", 0x8a: "base_instance (db.json enum)"}
        diff = {}
        for v, label in named.items():
            if v in obs:
                vals = [round(x - K, 6) for x in obs[v]]
                uniq = sorted(set(vals))
                diff["0x%02x" % v] = {
                    "label": label,
                    "raw_SR_after_subtracting_K": (uniq[0] if len(uniq) == 1
                                                   else "ramp %s" % uniq[:4]),
                    "flat": len(uniq) == 1,
                }
        out["raw_SR_values"] = diff
        out["oracle_confound_disclosure"] = (
            "The vertex arm's ABSOLUTE semantic oracle is confounded by K, so an `ok` there "
            "may be right for the wrong reason and is NOT cited as a validation. The "
            "differential readings above are the sound result.")
    return out


def stage_contrast(r1, r2):
    """For each selector, did the three stages CLASS it differently? A selector
    whose class differs by stage is direct evidence the namespace is
    stage-contextual (EXP-0031's claim, tested here rather than assumed)."""
    per = collections.defaultdict(dict)
    for arm in ("sr_compute", "sr_frag", "sr_vertex"):
        both, _, _ = agreeing(r1, r2, arm, "sr_sel")
        for v, r in both.items():
            per[v][arm] = (r["outcome"], r.get("class"))
    differing = {("0x%02x" % v): d for v, d in sorted(per.items())
                 if len({x for x in d.values()}) > 1}
    return {"selectors_with_a_stage_dependent_class": len(differing),
            "examples": dict(list(differing.items())[:24])}


def q2(r1, r2):
    out = {"question": "Does EXP-0147's silent-zero tile-read hazard reproduce on G17P?",
           "arms": {}}
    for arm in ("tile_ct1", "tile_ct2", "mrt_cm1", "mrt_cm2"):
        meta = [m for m in index(r1, "arm_meta") if m["arm"] == arm]
        na = [m for m in index(r1, "arm_not_attempted") if m["arm"] == arm]
        if not meta:
            out["arms"][arm] = {"status": "NOT_ATTEMPTED",
                                "why": na[0]["why"] if na else "no arm_meta"}
            continue
        instr = meta[0]["instr"]
        e = {"status": "RAN", "resolved_instr": instr, "anchor": meta[0]["instr_hex"],
             "baseline_fields": meta[0]["baseline_field_values"],
             "measurement_health": measurement_health(r1, r2, arm)}

        # read_en: the headline safety fact.
        both, dis, ncommon = agreeing(r1, r2, arm, "read_en")
        e["read_en"] = {
            "per_value": {str(v): both[v]["outcome"] for v in sorted(both)},
            "disagreements": dis,
            "M4_rule_reproduces": (both.get(1, {}).get("outcome") == "ok" and
                                   both.get(0, {}).get("outcome") == "silent_zero"),
            "any_fault": any(both[v]["outcome"] in ("fault", "hang") for v in both),
        }
        # b6_hi: EXP-0147 called bits 1-7 don't-care on M4.
        both6, dis6, n6 = agreeing(r1, r2, arm, "b6_hi")
        oc6 = collections.Counter(r["outcome"] for r in both6.values())
        e["b6_hi"] = {"outcomes": dict(oc6), "values_agreeing": len(both6),
                      "all_ok": bool(both6) and all(r["outcome"] == "ok"
                                                    for r in both6.values()),
                      "disagreements": dis6[:20]}
        # rt_index: correct set + the silent-zero-vs-fault question.
        bothr, disr, nr = agreeing(r1, r2, arm, "rt_index")
        ok = sorted(v for v, r in bothr.items() if r["outcome"] == "ok")
        sz = sorted(v for v, r in bothr.items() if r["outcome"] == "silent_zero")
        fl = sorted(v for v, r in bothr.items() if r["outcome"] in ("fault", "hang"))
        e["rt_index"] = {
            "correct_values": ["0x%02x" % v for v in ok],
            "silent_zero_count": len(sz), "faulting_values": ["0x%02x" % v for v in fl],
            "wrong_value_count": sum(1 for r in bothr.values()
                                     if r["outcome"] == "wrong_value"),
            "silent_zero_attachment_labels": dict(collections.Counter(
                str(bothr[v].get("class")) for v in sz)),
            "M4_shape_reproduces_bit0_and_bit7_dontcare": (
                len(ok) == 4 and len({v & 0x7E for v in ok}) == 1) if ok else False,
            "disagreements": disr[:20],
        }
        # fmt, on the mrt descriptor.
        bothf, disf, nf = agreeing(r1, r2, arm, "fmt")
        if bothf:
            okf = sorted(v for v, r in bothf.items() if r["outcome"] == "ok")
            e["fmt"] = {"correct_values": ["0x%02x" % v for v in okf],
                        "matches_M4_legal_set": set(okf) == M4_FMT_LEGAL,
                        "M4_legal_set": ["0x%02x" % v for v in sorted(M4_FMT_LEGAL)],
                        "silent_zero_count": sum(1 for r in bothf.values()
                                                 if r["outcome"] == "silent_zero"),
                        "disagreements": disf[:20]}
        # dst: the known hang-risk region.
        bothd, disd, nd = agreeing(r1, r2, arm, "dst")
        hz = sorted(v for v, r in bothd.items() if r["outcome"] in ("fault", "hang"))
        e["dst"] = {"correct_values": ["0x%02x" % v for v in sorted(
                        v for v, r in bothd.items() if r["outcome"] == "ok")],
                    "hazard_values": ["0x%02x" % v for v in hz],
                    "hazard_is_contiguous": bool(hz) and
                        all(b - a == 1 for a, b in zip(hz, hz[1:])),
                    "hazard_span": ("0x%02x..0x%02x" % (hz[0], hz[-1])) if hz else None,
                    "disagreements": disd[:20]}
        out["arms"][arm] = e
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run01", required=True)
    ap.add_argument("--run02", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "answers.json"))
    a = ap.parse_args()
    r1, r2 = load(a.run01), load(a.run02)
    doc = {"runs": [os.path.basename(a.run01), os.path.basename(a.run02)],
           "target": "G17P (A18 Pro)",
           "note": "M4 results are CROSS-TARGET HYPOTHESES here, never premises.",
           "Q1": q1(r1, r2), "Q2": q2(r1, r2)}
    json.dump(doc, open(a.out, "w"), indent=1, sort_keys=True)
    summary = {"Q1_arms": {}, "Q2_arms": {}}
    for q in ("Q1", "Q2"):
        for k, v in doc[q]["arms"].items():
            mh = v.get("measurement_health", {})
            summary[q + "_arms"][k] = {
                "status": v.get("status"),
                "measurement": mh.get("verdict", "n/a"),
                "measurement_failed": [mh.get(t, {}).get("measurement_failed")
                                       for t in ("run01", "run02")],
            }
    print(json.dumps(summary, indent=1))
