#!/usr/bin/env python3
"""EXP-0207 verdicts -- recomputed from raw/ on every invocation.

Nothing is read back from a run manifest, and nothing here trusts a claim made
anywhere else in this experiment.  The gate is PRE_REGISTRATION.md section 6,
rules R1..R8, and this file implements it and nothing else.

  python3 analysis/verdicts.py [--raw-root raw] [--out analysis/field_verdicts.json]

`selftest()` runs first and FAILS THE WHOLE ANALYSIS if the gate cannot refuse.
Three refusals are asserted, because each has been the corpus's actual defect:
  * a field whose entire movement is HARD outcomes must be refused (R4)
  * a WIDTH-1 field with one move and no disagreements must be ACCEPTED (R5)
  * an INERT claim from an arm whose controls never moved must be refused (R6)
"""
import argparse
import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)

# Outcomes that are NOT observations of a value's semantics.  Kept identical to
# tools/agx-isa/wave_audit.py's HARD set plus this experiment's own frozen enum,
# because a gate that lumps them counts a GPU fault as evidence.
HARD = {"fault", "hang", "no_draw", "no_dispatch", "undecodable", "not_written",
        "invalid_run", "measurement_failed", "timeout", "wedge"}

AGREE_MIN = 0.99


def load_runs(raw_root):
    runs = {}
    for d in sorted(glob.glob(os.path.join(raw_root, "*"))):
        f = os.path.join(d, "sweep.jsonl")
        if not os.path.isfile(f):
            continue
        recs = []
        for line in open(f, errors="replace"):
            try:
                recs.append(json.loads(line))
            except Exception:                                  # noqa: BLE001
                continue
        env = {}
        ef = os.path.join(d, "00_env.json")
        if os.path.isfile(ef):
            env = json.load(open(ef))
        runs[os.path.basename(d)] = {"recs": recs, "env": env, "dir": d}
    return runs


def gated_runs(runs, contract):
    """R1: a run counts only if its pinned toolchain hashes equal the frozen
    contract.  A run captured against a different tokenizer is not comparable."""
    want = contract.get("pinned_inputs_sha256", {})
    out = {}
    for k, v in runs.items():
        if not k.startswith("g17p_"):
            continue
        got = v["env"].get("pinned", {})
        if want and any(got.get(n) != h for n, h in want.items()):
            continue
        out[k] = v
    return out


def obs_key(r):
    o = r.get("observed")
    if not o:
        return None
    return o.get("d")


def analyse(runs, arm, instr, field):
    """Per-(arm, instr, field) evidence, from raw only."""
    per_run = {}
    for rid, v in runs.items():
        cells = {}
        for r in v["recs"]:
            if r.get("kind") != "case":
                continue
            if r.get("arm") != arm or r.get("instr") != instr or r.get("field") != field:
                continue
            cells[r.get("value")] = r
        if cells:
            per_run[rid] = cells
    if len(per_run) < 2:
        return None
    rk = sorted(per_run)
    a, b = per_run[rk[0]], per_run[rk[1]]
    common = sorted(set(a) & set(b))
    disagree = [v for v in common
                if (a[v].get("outcome"), obs_key(a[v])) != (b[v].get("outcome"), obs_key(b[v]))]
    agree = 1.0 - len(disagree) / max(len(common), 1)

    hard = collections.Counter()
    valid_payloads = set()
    moved_valid = 0
    moved_any = 0
    tok_bad_moving = 0
    oracle_payloads = set()
    for v in common:
        r = a[v]
        oc = r.get("outcome")
        oracle_payloads.add(json.dumps(r.get("oracle"), sort_keys=True))
        if oc in HARD:
            hard[oc] += 1
            if r.get("moved"):
                moved_any += 1
            continue
        k = obs_key(r)
        if k is not None:
            valid_payloads.add(k)
        if r.get("moved"):
            moved_valid += 1
            moved_any += 1
            if not r.get("tok_same_instr"):
                tok_bad_moving += 1
    return dict(arm=arm, instr=instr, field=field, runs=rk,
                values_common=len(common), disagree=len(disagree), agreement=agree,
                hard=dict(hard), hard_total=sum(hard.values()),
                V=len(valid_payloads), moved_valid=moved_valid, moved_any=moved_any,
                tok_bad_moving=tok_bad_moving,
                distinct_oracles=len(oracle_payloads),
                values_dispatched=max((a[v].get("values_dispatched") or 0) for v in common)
                if common else 0,
                distinct_bytes=len({a[v].get("bytes") for v in common}),
                encodable_range=max((a[v].get("encodable_range") or 0) for v in common)
                if common else 0,
                start=a[common[0]].get("start") if common else None,
                width=a[common[0]].get("width") if common else None)


def controls_fired(runs, arm):
    """R6: did ANY control record on this arm move the observable?

    An arm whose observable never moved for a known-live control cannot
    establish that anything is inert (DEF-0190-1).  This is a GATE on inert
    verdicts, not a measurement in its own right."""
    fired, tried = [], []
    for rid, v in runs.items():
        for r in v["recs"]:
            if r.get("arm") != arm:
                continue
            if r.get("kind") not in ("ladder", "power_probe", "sensitivity"):
                continue
            tried.append((rid, r.get("field")))
            if r.get("moved"):
                fired.append((rid, r.get("field"), r.get("outcome")))
    return fired, tried


def gate(ev, fired):
    """R2..R7.  Returns (verdict, reasons).  It can return `no`, and does."""
    reasons = []
    if ev is None:
        return "NO-PAIRED-RUNS", ["fewer than two gated runs carry this arm/field"]
    if ev["agreement"] < AGREE_MIN:
        reasons.append("R2 cross-run agreement %.4f < %.2f" % (ev["agreement"], AGREE_MIN))
    # R3, written EXACTLY as the protocol states.  NOT `2.0 * max(disagree, 1)`,
    # which refuses every width-1 field by arithmetic rather than by evidence.
    r3 = (ev["moved_valid"] >= 2.0 * ev["disagree"]) and (ev["moved_valid"] > 0)
    # R4: hard outcomes are not movement.  V counts distinct VALID payloads.
    r4 = ev["V"] > 1
    r7 = ev["tok_bad_moving"] == 0
    if not r7:
        reasons.append("R7 %d moving cells no longer decode as %s"
                       % (ev["tok_bad_moving"], ev["instr"]))
    if r3 and r4 and r7 and ev["agreement"] >= AGREE_MIN:
        return "LIVE", reasons
    if not r4 and ev["moved_any"] > 0:
        reasons.append("R4 V=%d distinct VALID payload(s) across %d values; movement is "
                       "%d hard outcome(s) -- a hazard map, not a semantic"
                       % (ev["V"], ev["values_common"], ev["hard_total"]))
        return "HAZARD-ONLY", reasons
    if ev["moved_any"] == 0:
        if not fired:
            reasons.append("R6 no control record moved on this arm: the arm has no "
                           "demonstrated detection power, so its null establishes nothing")
            return "STILL-UNDERPOWERED", reasons
        reasons.append("R6 satisfied: %d control record(s) moved" % len(fired))
        return "INERT", reasons
    if not r3:
        reasons.append("R3 moved=%d disagree=%d" % (ev["moved_valid"], ev["disagree"]))
    if not r4:
        reasons.append("R4 V=%d" % ev["V"])
    return "NOT-GATED", reasons


# ------------------------------------------------------------- self-test ----
def _mk(n, outcome, dkey, moved, value_from=0, width=8):
    return [{"kind": "case", "arm": "A", "instr": "I", "field": "F",
             "value": value_from + i, "outcome": outcome,
             "observed": {"d": dkey(i)}, "moved": moved(i), "tok_same_instr": True,
             "bytes": "%02x" % (value_from + i), "start": 0, "width": width,
             "values_dispatched": n, "encodable_range": 1 << width,
             "oracle": {"e": i}} for i in range(n)]


def selftest():
    ok = True

    def run2(recs):
        return {"r1": {"recs": recs, "env": {}}, "r2": {"recs": recs, "env": {}}}

    # (1) a field whose entire movement is HARD outcomes must be REFUSED.
    hardrecs = _mk(8, "fault", lambda i: None, lambda i: True)
    ev = analyse(run2(hardrecs), "A", "I", "F")
    v, _ = gate(ev, [("r1", "__power_x", "ok")])
    if v == "LIVE":
        print("SELFTEST FAIL: a fault-only field was promoted"); ok = False

    # (2) a WIDTH-1 field with one move and no disagreements must be ACCEPTED.
    w1 = _mk(2, "ok", lambda i: "d%d" % i, lambda i: i == 1, width=1)
    ev = analyse(run2(w1), "A", "I", "F")
    v, why = gate(ev, [])
    if v != "LIVE":
        print("SELFTEST FAIL: width-1 field with 1 move, 0 disagreements refused: %s %s"
              % (v, why)); ok = False

    # (3) an INERT claim from an arm with NO firing control must be REFUSED.
    inert = _mk(8, "ok", lambda i: "same", lambda i: False)
    ev = analyse(run2(inert), "A", "I", "F")
    v, _ = gate(ev, [])
    if v != "STILL-UNDERPOWERED":
        print("SELFTEST FAIL: inert verdict accepted from an arm with no detection "
              "power: %s" % v); ok = False
    v, _ = gate(ev, [("r1", "__power_x", "ok")])
    if v != "INERT":
        print("SELFTEST FAIL: inert verdict refused despite a firing control: %s" % v)
        ok = False

    # (4) a genuinely live field must be ACCEPTED.
    live = _mk(8, "ok", lambda i: "d%d" % i, lambda i: i > 0)
    ev = analyse(run2(live), "A", "I", "F")
    v, why = gate(ev, [])
    if v != "LIVE":
        print("SELFTEST FAIL: a live field was refused: %s %s" % (v, why)); ok = False
    return ok


LABEL = {
    # Only the eight labels of docs/evidence-classification.md are ever emitted.
    "LIVE": "hardware-run",
    "INERT": "single-template-inference",
    "HAZARD-ONLY": "untested",
    "STILL-UNDERPOWERED": "untested",
    "NOT-GATED": "untested",
    "NO-PAIRED-RUNS": "untested",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", default=os.path.join(EXP, "raw"))
    ap.add_argument("--out", default=os.path.join(HERE, "field_verdicts.json"))
    args = ap.parse_args()
    if not selftest():
        print("GATE SELF-TEST FAILED -- no verdicts written")
        return 2
    contract = {}
    cf = os.path.join(EXP, "CAPTURE_CONTRACT.json")
    if os.path.isfile(cf):
        contract = json.load(open(cf))
    runs = gated_runs(load_runs(args.raw_root), contract)
    print("gated runs: %s" % (sorted(runs) or "NONE"))

    sys.path.insert(0, os.path.join(EXP, "harness"))
    import plan207 as SP                                       # noqa: E402

    per_field = collections.defaultdict(list)
    for arm in SP.ARMS:
        for f in arm["fields"]:
            ev = analyse(runs, arm["arm"], arm["instr"], f)
            fired, tried = controls_fired(runs, arm["arm"])
            v, why = gate(ev, fired)
            per_field["%s.%s" % (arm["instr"], f)].append(
                dict(arm=arm["arm"], stage=arm["stage"], verdict=v, reasons=why,
                     controls_fired=len(fired), controls_tried=len(tried),
                     evidence=ev, why_carrier=arm["why"]))

    out = {"_doc": ("EXP-0207 proposed verdicts, recomputed from raw/ by "
                    "analysis/verdicts.py under PRE_REGISTRATION.md section 6 (R1..R8). "
                    "Hard outcomes are counted SEPARATELY from distinct valid payloads; "
                    "V<=1 across many legal values is a hazard map, not a semantic.")}
    for key, arms in sorted(per_field.items()):
        best = None
        for a in arms:
            rank = {"LIVE": 0, "INERT": 1, "HAZARD-ONLY": 2, "NOT-GATED": 3,
                    "STILL-UNDERPOWERED": 4, "NO-PAIRED-RUNS": 5}[a["verdict"]]
            if best is None or rank < best[0]:
                best = (rank, a)
        a = best[1]
        ev = a["evidence"] or {}
        out[key] = {
            "label": LABEL[a["verdict"]],
            "verdict": a["verdict"],
            "range": ("%d of %d encodable values, %d distinct byte strings, %d arm(s)"
                      % (ev.get("values_common", 0), ev.get("encodable_range", 0),
                         ev.get("distinct_bytes", 0), len(arms))),
            "target": "G17P",
            "evidence": ["EXP-0207"],
            "note": "; ".join(a["reasons"])[:900],
            "start": ev.get("start"), "width": ev.get("width"),
            "stage": a["stage"], "best_arm": a["arm"],
            "distinct_valid_payloads": ev.get("V"),
            "legal_values_observed": ev.get("values_common"),
            "hard_outcomes": ev.get("hard"),
            "hard_outcome_total": ev.get("hard_total"),
            "moved_valid": ev.get("moved_valid"),
            "moved_including_hard": ev.get("moved_any"),
            "disagreements": ev.get("disagree"),
            "cross_run_agreement": ev.get("agreement"),
            "distinct_oracle_payloads": ev.get("distinct_oracles"),
            "controls_fired": a["controls_fired"],
            "controls_tried": a["controls_tried"],
            "per_arm": [{k: x[k] for k in ("arm", "stage", "verdict", "controls_fired")}
                        | {"V": (x["evidence"] or {}).get("V"),
                           "moved_valid": (x["evidence"] or {}).get("moved_valid"),
                           "hard_total": (x["evidence"] or {}).get("hard_total"),
                           "agreement": (x["evidence"] or {}).get("agreement")}
                        for x in arms],
        }
    json.dump(out, open(args.out, "w"), indent=1, sort_keys=True)
    for k, v in sorted(out.items()):
        if k.startswith("_"):
            continue
        print("%-38s %-20s %-22s V=%s L=%s hard=%s moved=%s agree=%s"
              % (k, v["verdict"], v["label"], v["distinct_valid_payloads"],
                 v["legal_values_observed"], v["hard_outcome_total"],
                 v["moved_valid"], v["cross_run_agreement"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
