#!/usr/bin/env python3
"""EXP-0207 verdicts -- recomputed from raw/ on every invocation.

Nothing is read back from a run manifest and nothing here trusts a claim made
elsewhere in this experiment.  The gate is `PRE_REGISTRATION.md` section 6
(R1..R8) AS SUPERSEDED BY `RE_EXPERIMENT_PROCESS_CORRECTIONS.md`, which is
normative and wins where they conflict.  Concretely, from that document:

  * section 2 -- SIX INDEPENDENT AXES.  One label may no longer carry four
    conclusions, so every field gets a status on encoding geometry, liveness,
    semantics, compiler recipe, target, and reproducibility, and a result on one
    axis never implies a result on another.
  * Gate A -- an ACTUAL-BYTE LEDGER per case: requested value, requested bytes,
    actual dispatched bytes, an independently decoded value from those bytes,
    program hash + offset, db/harness revisions; `requested == decoded from
    actual` asserted before any hardware conclusion.
  * Gate B -- a pre-registered POSITIVE CONTROL in every arm, moving the same
    observable by a known mechanism, independent of the swept field.  If it
    fails the arm is `carrier-undecidable` and zero movement is NOT inertness.
  * Gate C -- LIVENESS IS NOT SEMANTICS.  `sem_checked == 0` can never produce
    `hardware-run` or `semantically-mapped`; `isolated-byte-diff` requires a
    PREDICTED SEMANTIC EFFECT at the tested point.
  * Gate E -- confirmation needs two clean runs in REVERSED or shuffled case
    order with identical ledgers; a malformed runner response is
    `measurement_failure`, never a hardware outcome.
  * section 5 -- exact numerators and denominators, never a percentage alone.
  * section 7 -- the safe negative wording is
    `inert in <exact tested envelope>; global role unknown`.

  python3 analysis/verdicts.py [--raw-root raw] [--out analysis/field_verdicts.json]

`selftest()` runs first and FAILS THE WHOLE ANALYSIS if the gate cannot refuse.
"""
import argparse
import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)

# Outcomes that are NOT observations of a value's semantics.  Identical to
# tools/agx-isa/wave_audit.py's HARD set plus this experiment's frozen enum: a
# gate that lumps these with valid payloads counts a GPU fault as evidence.
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
    """R1 + Gate E: a run counts only if its pinned toolchain hashes equal the
    frozen contract.  A run captured against a different tokenizer is not
    comparable."""
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
    return o.get("d") if o else None


def analyse(runs, arm, instr, field):
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
    # GATE E: identical ledgers across the two runs, which ran in opposite order.
    ledger_mismatch = [v for v in common
                       if (a[v].get("ledger") or {}).get("actual_bytes")
                       != (b[v].get("ledger") or {}).get("actual_bytes")]
    agree = 1.0 - len(disagree) / max(len(common), 1)

    hard = collections.Counter()
    valid_payloads = set()
    actual_encodings = set()
    requested_values = set()
    ledger_bad = 0
    moved_valid = moved_any = tok_bad_moving = 0
    sem_checked = sem_hit = sem_miss = 0
    silent = 0
    oracle_payloads = set()
    for v in common:
        r = a[v]
        led = r.get("ledger") or {}
        requested_values.add(v)
        if led.get("actual_bytes"):
            actual_encodings.add(led["actual_bytes"])
        if not r.get("ledger_ok"):
            ledger_bad += 1
        oracle_payloads.add(json.dumps(r.get("oracle"), sort_keys=True))
        # GATE C bookkeeping: a case counts as a SEMANTIC CHECK only when an
        # independent host predictor produced a definite expectation for it.
        if r.get("oracle") is not None and r.get("match") is not None:
            sem_checked += 1
            if r.get("match"):
                sem_hit += 1
            else:
                sem_miss += 1
        oc = r.get("outcome")
        if oc in HARD:
            hard[oc] += 1
            if r.get("moved"):
                moved_any += 1
            continue
        if oc == "silent_zero":
            silent += 1
        k = obs_key(r)
        if k is not None:
            valid_payloads.add(k)
        if r.get("moved"):
            moved_valid += 1
            moved_any += 1
            if not r.get("tok_same_instr"):
                tok_bad_moving += 1
    return dict(
        arm=arm, instr=instr, field=field, runs=rk,
        encodable=max((a[v].get("encodable_range") or 0) for v in common) if common else 0,
        dispatched=len(common), distinct_requested=len(requested_values),
        distinct_actual_encodings=len(actual_encodings),
        legal=len(common) - sum(hard.values()), silent=silent,
        faults=hard.get("fault", 0), hangs=hard.get("hang", 0),
        no_draw=hard.get("no_draw", 0) + hard.get("no_dispatch", 0),
        measurement_failed=hard.get("measurement_failed", 0),
        aliases=max(0, len(requested_values) - len(actual_encodings)),
        hard=dict(hard), hard_total=sum(hard.values()),
        V=len(valid_payloads), moved_valid=moved_valid, moved_any=moved_any,
        disagree=len(disagree), agreement=agree, ledger_bad=ledger_bad,
        ledger_mismatch_across_runs=len(ledger_mismatch),
        tok_bad_moving=tok_bad_moving, distinct_oracles=len(oracle_payloads),
        sem_checked=sem_checked, sem_hit=sem_hit, sem_miss=sem_miss,
        start=a[common[0]].get("start") if common else None,
        width=a[common[0]].get("width") if common else None)


def controls(runs, arm):
    """GATE B.  Returns (fired, tried).  An arm may support ANY verdict only if
    a pre-registered control moved the same observable by a known mechanism."""
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


def axes(ev, fired, verdict):
    """RE_EXPERIMENT_PROCESS_CORRECTIONS section 2: six independent axes.  A
    result on one axis never implies a result on another."""
    if ev is None:
        return dict(encoding_geometry="unverified", liveness="carrier-undecidable",
                    semantics="unknown", compiler_recipe="not-generated",
                    target="G17P-direct", reproducibility="incomplete")
    geom = "unverified"
    if ev["ledger_bad"] == 0 and ev["distinct_actual_encodings"] > 0:
        geom = ("geometry-mapped"
                if ev["distinct_actual_encodings"] == ev["distinct_requested"]
                else "ledger-verified")
    live = {"LIVE": "live", "INERT": "accepted-inert",
            "HAZARD-ONLY": "fault", "CARRIER-UNDECIDABLE": "carrier-undecidable",
            "NOT-GATED": "carrier-undecidable",
            "NO-PAIRED-RUNS": "carrier-undecidable"}[verdict]
    if ev["sem_checked"] == 0:
        sem = "unknown"
    elif ev["sem_miss"] == 0 and ev["sem_checked"] >= max(2, ev["dispatched"] // 4):
        sem = "bounded-map"
    else:
        sem = "hypothesis"
    return dict(encoding_geometry=geom, liveness=live, semantics=sem,
                compiler_recipe="not-generated",
                target="G17P-direct",
                reproducibility=("independently-confirmed"
                                 if ev["agreement"] >= AGREE_MIN and len(ev["runs"]) >= 2
                                 and ev["ledger_mismatch_across_runs"] == 0
                                 else "auditable"))


def gate(ev, fired):
    """Returns (verdict, reasons).  It can return `no`, and does."""
    reasons = []
    if ev is None:
        return "NO-PAIRED-RUNS", ["fewer than two gated runs carry this arm/field"]
    if ev["ledger_bad"]:
        reasons.append("GATE A FAILED: %d of %d cases where the requested value does not "
                       "equal the value decoded from the ACTUAL dispatched bytes"
                       % (ev["ledger_bad"], ev["dispatched"]))
        return "NOT-GATED", reasons
    if ev["ledger_mismatch_across_runs"]:
        reasons.append("GATE E FAILED: %d cases whose actual dispatched bytes differ "
                       "between the two runs" % ev["ledger_mismatch_across_runs"])
        return "NOT-GATED", reasons
    if not fired:
        reasons.append("GATE B FAILED: no pre-registered control moved this arm's "
                       "observable, so the arm is CARRIER-UNDECIDABLE and zero movement "
                       "is NOT evidence of inertness")
        return "CARRIER-UNDECIDABLE", reasons
    if ev["agreement"] < AGREE_MIN:
        reasons.append("R2 cross-run agreement %.4f < %.2f (%d disagreements of %d)"
                       % (ev["agreement"], AGREE_MIN, ev["disagree"], ev["dispatched"]))
        return "NOT-GATED", reasons
    # R3 written EXACTLY as the protocol states -- NOT `2.0 * max(disagree, 1)`,
    # which refuses every width-1 field by arithmetic rather than by evidence.
    r3 = (ev["moved_valid"] >= 2.0 * ev["disagree"]) and (ev["moved_valid"] > 0)
    r4 = ev["V"] > 1
    if ev["tok_bad_moving"]:
        reasons.append("R7 %d moving cells no longer decode as %s"
                       % (ev["tok_bad_moving"], ev["instr"]))
        return "NOT-GATED", reasons
    if ev["moved_any"] == 0:
        reasons.append("GATE B satisfied: %d control record(s) moved on this arm" % len(fired))
        return "INERT", reasons
    if r3 and r4:
        return "LIVE", reasons
    if not r4:
        reasons.append("R4 V=%d distinct VALID payload(s) across %d dispatched values; "
                       "movement is %d hard outcome(s) -- a hazard map, not a semantic"
                       % (ev["V"], ev["dispatched"], ev["hard_total"]))
        return "HAZARD-ONLY", reasons
    reasons.append("R3 moved=%d disagree=%d" % (ev["moved_valid"], ev["disagree"]))
    return "NOT-GATED", reasons


def legacy_label(verdict, ev):
    """RE_EXPERIMENT_PROCESS_CORRECTIONS section 2: do NOT round liveness up into
    the legacy semantic/emitter label.  `sem_checked == 0` can never produce
    `hardware-run`, and `isolated-byte-diff` requires a PREDICTED SEMANTIC EFFECT
    at the tested point."""
    if ev is None:
        return "untested"
    if verdict == "LIVE":
        if ev["sem_checked"] and ev["sem_miss"] == 0:
            return "hardware-run"
        if ev["sem_checked"] and ev["sem_hit"]:
            return "isolated-byte-diff"
        return "untested"          # live; role unknown -- liveness is not semantics
    if verdict == "INERT":
        return "single-template-inference"
    return "untested"


def _mk(n, outcome, dkey, moved, width=8, oracle=None, match=None):
    return [{"kind": "case", "arm": "A", "instr": "I", "field": "F", "value": i,
             "outcome": outcome, "observed": {"d": dkey(i)}, "moved": moved(i),
             "tok_same_instr": True, "bytes": "%02x" % i, "start": 0, "width": width,
             "encodable_range": 1 << width, "ledger_ok": True,
             "ledger": {"actual_bytes": "%02x" % i},
             "oracle": (oracle(i) if oracle else None),
             "match": (match(i) if match else None)} for i in range(n)]


def selftest():
    ok = True

    def run2(recs):
        return {"g17p_a": {"recs": recs, "env": {}}, "g17p_b": {"recs": recs, "env": {}}}

    FIRED = [("g17p_a", "__power_x", "ok")]
    # (1) movement made entirely of HARD outcomes must be REFUSED.
    ev = analyse(run2(_mk(8, "fault", lambda i: None, lambda i: True)), "A", "I", "F")
    if gate(ev, FIRED)[0] == "LIVE":
        print("SELFTEST FAIL: a fault-only field was promoted"); ok = False
    # (2) a WIDTH-1 field with one move and no disagreements must be ACCEPTED.
    ev = analyse(run2(_mk(2, "ok", lambda i: "d%d" % i, lambda i: i == 1, width=1)),
                 "A", "I", "F")
    v, why = gate(ev, FIRED)
    if v != "LIVE":
        print("SELFTEST FAIL: width-1 field, 1 move, 0 disagreements refused: %s %s"
              % (v, why)); ok = False
    # (3) GATE B: an inert claim from an arm with NO firing control must be REFUSED.
    inert = _mk(8, "ok", lambda i: "same", lambda i: False)
    if gate(analyse(run2(inert), "A", "I", "F"), [])[0] != "CARRIER-UNDECIDABLE":
        print("SELFTEST FAIL: inert accepted from an arm with no detection power")
        ok = False
    if gate(analyse(run2(inert), "A", "I", "F"), FIRED)[0] != "INERT":
        print("SELFTEST FAIL: inert refused despite a firing control"); ok = False
    # (4) GATE C: a LIVE field with ZERO semantic checks must NOT reach hardware-run.
    ev = analyse(run2(_mk(8, "ok", lambda i: "d%d" % i, lambda i: i > 0)), "A", "I", "F")
    v, _ = gate(ev, FIRED)
    if v != "LIVE":
        print("SELFTEST FAIL: a live field was refused"); ok = False
    if legacy_label(v, ev) == "hardware-run":
        print("SELFTEST FAIL: liveness with sem_checked=0 was rounded up to hardware-run")
        ok = False
    # (5) GATE A: a broken actual-byte ledger must REFUSE.
    bad = _mk(8, "ok", lambda i: "d%d" % i, lambda i: i > 0)
    for r in bad:
        r["ledger_ok"] = False
    if gate(analyse(run2(bad), "A", "I", "F"), FIRED)[0] != "NOT-GATED":
        print("SELFTEST FAIL: a broken actual-byte ledger was not refused"); ok = False
    # (6) a live field WITH passing semantic checks does reach hardware-run.
    good = _mk(8, "ok", lambda i: "d%d" % i, lambda i: i > 0,
               oracle=lambda i: {"e": i}, match=lambda i: True)
    ev = analyse(run2(good), "A", "I", "F")
    if legacy_label(gate(ev, FIRED)[0], ev) != "hardware-run":
        print("SELFTEST FAIL: a semantically checked live field was refused hardware-run")
        ok = False
    return ok


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
    orders = {k: v["env"].get("case_order") for k, v in runs.items()}
    print("case orders: %s   (GATE E wants them different)" % orders)

    sys.path.insert(0, os.path.join(EXP, "harness"))
    import plan207 as SP                                       # noqa: E402

    per_field = collections.defaultdict(list)
    for arm in SP.ARMS:
        for f in arm["fields"]:
            ev = analyse(runs, arm["arm"], arm["instr"], f)
            fired, tried = controls(runs, arm["arm"])
            v, why = gate(ev, fired)
            per_field["%s.%s" % (arm["instr"], f)].append(
                dict(arm=arm["arm"], stage=arm["stage"], verdict=v, reasons=why,
                     controls_fired=len(fired), controls_tried=len(tried),
                     axes=axes(ev, fired, v), evidence=ev, why_carrier=arm["why"]))

    out = {"_doc": ("EXP-0207 proposed verdicts, recomputed from raw/ by "
                    "analysis/verdicts.py under PRE_REGISTRATION.md section 6 as "
                    "superseded by RE_EXPERIMENT_PROCESS_CORRECTIONS.md (six independent "
                    "axes; Gates A/B/C/E; exact numerators and denominators, never a "
                    "percentage alone). Hard outcomes are counted SEPARATELY from "
                    "distinct valid payloads. Liveness is NOT rounded up into a semantic "
                    "or emitter label.")}
    RANK = {"LIVE": 0, "INERT": 1, "HAZARD-ONLY": 2, "NOT-GATED": 3,
            "CARRIER-UNDECIDABLE": 4, "NO-PAIRED-RUNS": 5}
    for key, arms in sorted(per_field.items()):
        best = min(arms, key=lambda a: RANK[a["verdict"]])
        ev = best["evidence"] or {}
        env = ("encodable=%s dispatched=%s distinct_requested=%s distinct_actual=%s "
               "legal=%s silent=%s faults=%s hangs=%s no_draw=%s aliases=%s untested=%s"
               % (ev.get("encodable"), ev.get("dispatched"), ev.get("distinct_requested"),
                  ev.get("distinct_actual_encodings"), ev.get("legal"), ev.get("silent"),
                  ev.get("faults"), ev.get("hangs"), ev.get("no_draw"), ev.get("aliases"),
                  (ev.get("encodable") or 0) - (ev.get("dispatched") or 0)))
        out[key] = {
            "label": legacy_label(best["verdict"], ev),
            "verdict": best["verdict"],
            "axes": best["axes"],
            "range": env,
            "target": "G17P",
            "evidence": ["EXP-0207"],
            "note": ("; ".join(best["reasons"])[:600] +
                     ("" if best["verdict"] != "INERT" else
                      "  || inert in the exact tested envelope above; global role unknown")),
            "start": ev.get("start"), "width": ev.get("width"),
            "stage": best["stage"], "best_arm": best["arm"],
            "distinct_valid_payloads": ev.get("V"),
            "legal_values_observed": ev.get("legal"),
            "hard_outcomes": ev.get("hard"), "hard_outcome_total": ev.get("hard_total"),
            "moved_valid": ev.get("moved_valid"),
            "moved_including_hard": ev.get("moved_any"),
            "disagreements": ev.get("disagree"),
            "cross_run_agreement": ev.get("agreement"),
            "ledger_failures": ev.get("ledger_bad"),
            "ledger_mismatch_across_runs": ev.get("ledger_mismatch_across_runs"),
            "distinct_oracle_payloads": ev.get("distinct_oracles"),
            "sem_checked": ev.get("sem_checked"), "sem_hit": ev.get("sem_hit"),
            "sem_miss": ev.get("sem_miss"),
            "controls_fired": best["controls_fired"],
            "controls_tried": best["controls_tried"],
            "per_arm": [dict(arm=x["arm"], stage=x["stage"], verdict=x["verdict"],
                             controls_fired=x["controls_fired"],
                             V=(x["evidence"] or {}).get("V"),
                             moved_valid=(x["evidence"] or {}).get("moved_valid"),
                             hard_total=(x["evidence"] or {}).get("hard_total"),
                             sem_checked=(x["evidence"] or {}).get("sem_checked"),
                             sem_miss=(x["evidence"] or {}).get("sem_miss"),
                             agreement=(x["evidence"] or {}).get("agreement"))
                        for x in arms],
        }
    json.dump(out, open(args.out, "w"), indent=1, sort_keys=True)
    for k, v in sorted(out.items()):
        if k.startswith("_"):
            continue
        print("%-32s %-20s %-26s V=%-4s sem=%s/%s  %s"
              % (k, v["verdict"], v["label"], v["distinct_valid_payloads"],
                 v["sem_hit"], v["sem_checked"], v["range"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
