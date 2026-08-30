#!/usr/bin/env python3
"""EXP-0201 PROMOTION GATE. Recomputes every verdict from raw/ on every call.

    python3 analysis/verdicts.py raw/<run01> raw/<run02> [...]

Implements PRE_REGISTRATION.md section 7 and nothing else. Verdicts are never
read back from a run manifest; they are re-derived from the append-only records.

THE GATE MUST BE ABLE TO SAY NO. Thirteen checks in this corpus could not, and
each of those failures is encoded here as an assertion in `selftest()`:

  * a GPU **fault** is not movement (a gate counted one; so did a case where our
    own disassembler failed to decode -- both with STATUS OK and byte-identical
    output);
  * a round trip is symmetric and is **not** an emitter gate, so nothing here
    consults one;
  * a width-1 field must be able to pass: the rule is
    `moved >= 2*disagree AND moved > 0`, never `moved >= 2*max(disagree,1)`,
    which refuses every 1-bit field by arithmetic rather than by evidence;
  * an INERT verdict needs a **detection-power conjunct** or it cannot fail
    either -- an arm whose observable never moves returns moved = 0 by
    construction;
  * **V <= 1 (one distinct valid payload over many legal values) is NOT
    PROMOTED** whatever else is true: the values ran legally and were
    indistinguishable. That is the shape that left `copysign.operands` at
    `untested` after a dense 256-value, 256-distinct-encoding M4 sweep.

CROSS-RUN COMPARISON USES THE DETERMINISTIC PAYLOAD ONLY. `observed` in this
experiment's raw carries no timer; `gputime_ns` is a top-level key. An indexer
that hashes the whole `observed` dict measures the nanosecond timer along with
the data, which alone moved one field's apparent agreement from 100 % to 39 %.
"""
import collections
import glob
import json
import os
import sys

MIN_AGREE = 99.0
MOVED_OVER_DISAGREE = 2.0
HARD = {"fault", "hang", "undecodable", "measurement_failure", "invalid_run",
        "nondeterministic", "not_written_all", "carrier_start_failed"}
TARGETS = [("falu3", "op"), ("falu3_ext", "op"), ("fspecial_est", "srcA"),
           ("falu3_srcmod12", "opsel"), ("falu3_srcmod12", "ctrl"),
           ("copysign", "operands")]


def sig(rec):
    """The deterministic observation signature: the read-back payload only."""
    o = rec.get("observed") or {}
    return json.dumps({k: o.get(k) for k in
                       ("status", "vals_u32", "aux_u32", "sent_u32", "tail_u32",
                        "unwritten", "sentinel_ok", "tail_ok")},
                      sort_keys=True)


def load(run_dirs):
    recs = []
    for d in run_dirs:
        run = os.path.basename(os.path.normpath(d))
        for f in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
            if os.path.basename(f) != "sweep.jsonl":
                continue
            for ln in open(f, errors="replace"):
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                r["_run"] = run
                recs.append(r)
    return recs


def quiet(run_dirs):
    """A run is QUIET only if no sample saw a foreign GPU-runner process."""
    out = {}
    for d in run_dirs:
        run = os.path.basename(os.path.normpath(d))
        p = os.path.join(d, "gpuwatch.jsonl")
        if not os.path.exists(p):
            out[run] = {"samples": 0, "quiet": None,
                        "note": "no gpuwatch.jsonl -- quietness UNMEASURED"}
            continue
        n = f = d = 0
        comms = set()
        for ln in open(p, errors="replace"):
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            n += 1
            foreign = [x for x in r.get("procs", []) if not x["ours"]]
            if foreign:
                f += 1
                comms |= {x["comm"].split("/")[-1] for x in foreign}
            # A DISPATCH runner is the contamination mechanism named in
            # FIELD-SWEEP-PROTOCOL section 7: a hang triggers a DEVICE RESET that
            # kills in-flight command buffers in other contexts. A sibling's
            # `shdump`/`MTLCompilerService` compiles a shader; it does not submit
            # the work that resets the device. Both figures are reported; the
            # GATE uses the STRICT one, so this distinction can never loosen a
            # verdict -- it only lets a reader see what the concurrency was.
            if any(k in x["comm"] for k in ("agxrun", "gfrun", "rendersweep",
                                            "agxrender", "renderpersist")
                   for x in foreign):
                d += 1
        out[run] = {"samples": n, "samples_with_foreign_gpu_proc": f,
                    "samples_with_foreign_DISPATCH_runner": d,
                    "quiet": (n > 0 and f == 0),
                    "quiet_dispatch": (n > 0 and d == 0),
                    "foreign_comms": sorted(comms)}
    return out


DISPATCH_RUNNERS = ("agxrun", "gfrun", "rendersweep", "agxrender", "renderpersist")
FOREIGN_COMPILERS = ("shdump",)
# XPC services launchd owns. See quiet_v2() for why these cannot be attributed.
XPC_UNATTRIBUTABLE = ("MTLCompilerService",)


def quiet_v2(run_dirs):
    """AMENDMENT B (2026-08-30) -- the quiet model, corrected. Stated, not silent.

    THE DEFECT. `quiet()` above counts ANY process matching gpuwatch's pattern
    list that is not a descendant of the sampler's own process tree. That is a
    check which, for one of those patterns, CANNOT COME OUT THE OTHER WAY:

      * `MTLCompilerService` is an **XPC service**. launchd spawns it, so it is
        never a descendant of the requesting process and ppid attribution is
        STRUCTURALLY IMPOSSIBLE -- "ours" can never be true for it.
      * `run.py` compiles 21 carriers per run through `shdump`, so our own run
        NECESSARILY causes compiler-service processes to exist while it samples.

    Together those two facts mean the strict model can only ever move towards
    CONTAMINATED, and it did: on `g17p_quiet02` it flagged **1 sample of 273**,
    holding a single `MTLCompilerService` at 0.0 % CPU, and refused six fields
    that agreed 100 % across a reversed-order pair. That is the mirror of the
    inertness defect this corpus already documents -- there a gate could not
    doubt; here a gate could not acquit.

    THE CORRECTION, and its exact scope. `quiet_v2` counts as contamination:
      * any foreign **GPU dispatch runner** (`agxrun*`, `gfrun*`, `rendersweep`,
        `agxrender`, `renderpersist`) -- the mechanism FIELD-SWEEP-PROTOCOL
        section 7 names, because a hang triggers a DEVICE RESET that kills
        in-flight command buffers in other contexts; and
      * any foreign `shdump` -- not because compiling perturbs the GPU, but
        because it is positive evidence that ANOTHER AGENT IS ACTIVE.
    It does NOT count `MTLCompilerService`, on the stated ground above.

    This is a LOOSENING and it is recorded as one. Both figures are returned on
    every run, `quiet_v1_strict` is never removed, and the corroborating
    independent instrument (EXP-0210's `quietcheck.json`, which carries
    GPU-level counters this sampler does not read) is cited in RESULTS.md rather
    than substituted for our own measurement.
    """
    out = {}
    for d in run_dirs:
        run = os.path.basename(os.path.normpath(d))
        p = os.path.join(d, "gpuwatch.jsonl")
        if not os.path.exists(p):
            out[run] = {"samples": 0, "quiet_v1_strict": None, "quiet_v2": None,
                        "note": "no gpuwatch.jsonl -- quietness UNMEASURED"}
            continue
        n = strict = disp = comp = xpc = 0
        comms = set()
        for ln in open(p, errors="replace"):
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            n += 1
            foreign = [x for x in r.get("procs", []) if not x["ours"]]
            if foreign:
                strict += 1
                comms |= {x["comm"].split("/")[-1] for x in foreign}
            if any(k in x["comm"] for k in DISPATCH_RUNNERS for x in foreign):
                disp += 1
            if any(k in x["comm"] for k in FOREIGN_COMPILERS for x in foreign):
                comp += 1
            if any(k in x["comm"] for k in XPC_UNATTRIBUTABLE for x in foreign):
                xpc += 1
        out[run] = {
            "samples": n,
            "samples_with_any_foreign_proc": strict,
            "samples_with_foreign_DISPATCH_runner": disp,
            "samples_with_foreign_shdump": comp,
            "samples_with_unattributable_MTLCompilerService": xpc,
            "quiet_v1_strict": (n > 0 and strict == 0),
            "quiet_v2": (n > 0 and disp == 0 and comp == 0),
            "foreign_comms": sorted(comms),
        }
    return out


def arm_stats(recs, arm, run):
    """Per-value deterministic signature for one arm in one run, plus the
    baseline signature captured immediately before the arm.

    Returns (baseline_sig, valid_sigs, hard_counter, token_mismatch_values,
    all_sigs). `valid_sigs` feeds `moved`; `all_sigs` additionally carries hard
    outcomes as their own class and feeds the cross-run comparison."""
    base = None
    for r in recs:
        if r["_run"] == run and r.get("field") == "_baseline" \
                and r.get("arm") == arm + ":open":
            base = sig(r)
    vals, allv, hard, tokmis = {}, {}, collections.Counter(), set()
    for r in recs:
        if r["_run"] != run or r.get("arm") != arm or r.get("field") == "_baseline":
            continue
        oc = r.get("outcome")
        if oc in HARD:
            hard[oc] += 1
            # A hard outcome is NOT movement (C5) and never enters `vals`, but it
            # IS an observation about that value, so it enters the CROSS-RUN
            # comparison as its own class. Otherwise a value that faults in one
            # run and runs clean in the other silently drops out of `common`
            # instead of counting as the disagreement it is.
            allv[r["value"]] = "hard:" + str(oc)
            continue
        vals[r["value"]] = sig(r)
        allv[r["value"]] = sig(r)
        tok = (r.get("token") or {}).get("mnemonic")
        if tok != r.get("instr"):
            tokmis.add(r["value"])
    return base, vals, hard, tokmis, allv


def adjudicated(sig_a, sig_b):
    """PRE_REGISTRATION section 8, route (b) -- EXP-0160's evidence-validity
    filter, applied ONLY as a clearly-labelled SECONDARY figure.

    Two records describe the SAME hardware observation when both say the tested
    program produced no result: a contained command-buffer `fault` returns no
    read-back at all, and a `not_written` returns STATUS OK with every value word
    still holding its own poison and the sentinel present. The difference between
    them is whether the OS flagged the command buffer -- which is exactly what a
    sibling context's device reset changes -- not what the program computed.

    This never merges two records that both wrote something, and it never turns a
    written value into an unwritten one. It is reported next to the primary
    figure, never instead of it.
    """
    def norm(s):
        if s.startswith("hard:fault") or s.startswith("hard:hang"):
            return "NO-RESULT"
        try:
            o = json.loads(s)
        except ValueError:
            return s
        if o.get("unwritten") and len(o["unwritten"]) >= 8 and o.get("sentinel_ok"):
            return "NO-RESULT"
        return s
    return norm(sig_a) == norm(sig_b)


def analyse(recs, mnem, field, runs):
    arms = sorted({r["arm"] for r in recs
                   if r.get("instr") == mnem and r.get("field") == field})
    per_arm = {}
    for arm in arms:
        carrier = next(r["carrier"] for r in recs if r.get("arm") == arm)
        occ = next(r.get("occ") for r in recs if r.get("arm") == arm)
        ctl = arm.rsplit("/", 1)[0] + "/_live_control"
        fal = arm.rsplit("/", 1)[0] + "/_falsifier"
        entry = {"carrier": carrier, "occ": occ, "runs": {}}
        for run in runs:
            base, vals, hard, tokmis, _all = arm_stats(recs, arm, run)
            moved = sorted(v for v, s in vals.items()
                           if base is not None and s != base and v not in tokmis)
            moved_by_token = sorted(v for v in tokmis
                                    if base is not None and vals.get(v) != base)
            entry["runs"][run] = {
                "n_values": len(vals), "n_distinct_payloads": len(set(vals.values())),
                "moved": len(moved), "moved_by_relabelled_token": len(moved_by_token),
                "hard": dict(hard), "baseline_present": base is not None}
        # cross-run agreement over the values common to the first two runs
        agree_pct, dis, common = None, None, None
        if len(runs) >= 2:
            _, _, _, _, va = arm_stats(recs, arm, runs[0])
            _, _, _, _, vb = arm_stats(recs, arm, runs[1])
            keys = set(va) & set(vb)
            d = [v for v in keys if va[v] != vb[v]]
            common, dis = len(keys), len(d)
            agree_pct = 100.0 * (1 - len(d) / max(len(keys), 1))
            d2 = [v for v in d if not adjudicated(va[v], vb[v])]
            entry["disagree_adjudicated"] = len(d2)
            entry["agree_pct_adjudicated"] = 100.0 * (1 - len(d2) / max(len(keys), 1))
            entry["disagreeing_values"] = sorted(d)[:64]
            entry["disagreeing_values_after_adjudication"] = sorted(d2)[:64]
        # controls
        cmoved = 0
        for run in runs:
            cb, cv, _, _, _ = arm_stats(recs, ctl, run)
            if cb is not None:
                cmoved = max(cmoved, sum(1 for s in cv.values() if s != cb))
        fmoved = 0
        for run in runs:
            fb, fv, _, _, _ = arm_stats(recs, fal, run)
            if fb is not None:
                fmoved = max(fmoved, sum(1 for s in fv.values() if s != fb))
        # payload / encoding census, from raw only
        cases = [r for r in recs if r.get("arm") == arm
                 and r.get("field") == field]
        valid = [r for r in cases if r.get("outcome") not in HARD]
        # ---- GATE A: caller -> ACTUAL dispatched bytes ----------------------
        led = [r.get("ledger") for r in cases if r.get("ledger")]
        led_bad = [l for l in led if not l.get("ok")]
        actual_bytes = {l["actual_bytes"] for l in led if l.get("actual_bytes")}
        entry_ledger = {
            "cases_with_ledger": len(led), "cases_total": len(cases),
            "ledger_mismatches": len(led_bad),
            "distinct_requested_values": len({r["value"] for r in cases}),
            "distinct_actual_encodings": len(actual_bytes),
            "match_bit_collision": (len(actual_bytes) > 0
                                    and len(actual_bytes)
                                    < len({r["value"] for r in cases})),
            "program_hashes": len({l.get("program_sha256") for l in led}),
        }
        # ---- GATE C: semantic checks against the independent predictor ------
        sem = [r for r in cases
               if (r.get("oracle") or {}).get("predicted_fn") is not None
               and (r.get("oracle") or {}).get("vals") is not None]
        sem_ok = [r for r in sem if r.get("match")]
        buckets = collections.Counter()
        for r in cases:
            oc = r.get("outcome")
            if oc == "ok":
                buckets["correct_effect"] += 1
            elif oc in ("fault", "hang"):
                buckets["rejected_or_faulted"] += 1
            elif oc in ("silent_zero", "not_written"):
                buckets["silent_zero_or_no_write"] += 1
            elif oc in ("invalid_run", "measurement_failure", "nondeterministic"):
                buckets["invalid_or_contaminated"] += 1
            elif r.get("observed_fn"):
                buckets["different_but_coherent"] += 1
            else:
                buckets["different_unclassified"] += 1
        entry.update({
            "cross_run_agree_pct": agree_pct, "disagree": dis, "common": common,
            "moved": max(e["moved"] for e in entry["runs"].values()) if runs else 0,
            "moved_min": min(e["moved"] for e in entry["runs"].values()) if runs else 0,
            "V_distinct_valid_payloads": len({sig(r) for r in valid}),
            "L_legal_values": len({r["value"] for r in cases}),
            "distinct_bytes": len({r["bytes"] for r in cases if r.get("bytes")}),
            "distinct_oracles": len({json.dumps(r.get("oracle"), sort_keys=True)
                                     for r in cases}),
            "hard_outcomes": dict(collections.Counter(
                r["outcome"] for r in cases if r.get("outcome") in HARD)),
            "observed_fns": dict(collections.Counter(
                r.get("observed_fn") for r in valid)),
            "n_ok": sum(1 for r in valid if r.get("outcome") == "ok"),
            "accept_values": sorted({r["value"] for r in valid
                                     if r.get("outcome") == "ok"}),
            "control_moved": cmoved, "falsifier_moved": fmoved,
            "gateA_ledger": entry_ledger,
            "sem_checked": len(sem), "sem_confirmed": len(sem_ok),
            "semantic_buckets": dict(buckets),
            "agree_pct_adjudicated": entry.get("agree_pct_adjudicated"),
            "disagree_adjudicated": entry.get("disagree_adjudicated"),
            "disagreeing_values": entry.get("disagreeing_values"),
            "disagreeing_values_after_adjudication":
                entry.get("disagreeing_values_after_adjudication"),
            "token_mismatch_values": sorted(
                {r["value"] for r in cases
                 if (r.get("token") or {}).get("mnemonic") != mnem}),
        })
        per_arm[arm] = entry
    return per_arm


def rule(e, n_runs, quiet_ok):
    """The frozen gate, as amended by RE_EXPERIMENT_PROCESS_CORRECTIONS.md.

    Returns (verdict, reasons[]). `PROMOTE` here means the LEGACY emitter-grade
    label; the six independent axes are computed separately by `axes()` and are
    never collapsed into it. In particular liveness never rounds up into
    semantics: `sem_checked == 0` can never produce `hardware-run`."""
    why = []
    g = e.get("gateA_ledger") or {}
    if g.get("cases_with_ledger", 0) < g.get("cases_total", 1):
        why.append("GATE A: %d of %d cases carry no actual-byte ledger"
                   % (g.get("cases_with_ledger", 0), g.get("cases_total", 0)))
    if g.get("ledger_mismatches"):
        why.append("GATE A: %d cases where the requested value != the value "
                   "decoded from the ACTUAL dispatched bytes"
                   % g["ledger_mismatches"])
    if g.get("match_bit_collision"):
        why.append("GATE A: ALIASED -- %d distinct actual encodings for %d "
                   "distinct requested values"
                   % (g.get("distinct_actual_encodings"),
                      g.get("distinct_requested_values")))
    if not e.get("sem_checked"):
        why.append("GATE C: sem_checked == 0 -- movement is LIVENESS only; "
                   "`live; role unknown` cannot become hardware-run")
    elif not e.get("sem_confirmed"):
        why.append("GATE C: no case confirmed the independent predictor")
    if n_runs < 2:
        why.append("fewer than 2 gated runs")
    if e["V_distinct_valid_payloads"] <= 1 and e["L_legal_values"] > 1:
        why.append("V=%d distinct valid payloads over %d legal values -- ran "
                   "legally and INDISTINGUISHABLE (Case C)"
                   % (e["V_distinct_valid_payloads"], e["L_legal_values"]))
    if e["distinct_bytes"] < 2:
        why.append("distinct_bytes=%d" % e["distinct_bytes"])
    if e["distinct_bytes"] < e["L_legal_values"]:
        why.append("ALIASED: %d distinct encodings for %d legal values"
                   % (e["distinct_bytes"], e["L_legal_values"]))
    if e["distinct_oracles"] <= 1:
        why.append("CONSTANT ORACLE: predicts the instruction, not the field")
    if e["moved_min"] <= 0:
        why.append("moved=0 in at least one run")
    if e["disagree"] is not None and not (
            e["moved_min"] >= MOVED_OVER_DISAGREE * e["disagree"]):
        why.append("moved(%d) < 2*disagree(%d)" % (e["moved_min"], e["disagree"]))
    if e["cross_run_agree_pct"] is None or e["cross_run_agree_pct"] < MIN_AGREE:
        why.append("cross-run agreement %.2f%% < %.1f%%"
                   % (e["cross_run_agree_pct"] or 0.0, MIN_AGREE))
    if e["moved_min"] <= 0 and e["control_moved"] <= 0:
        why.append("no detection power: the arm's live control never moved, so "
                   "an inert reading cannot be supported either")
    if e["falsifier_moved"] <= 0:
        why.append("the pre-registered falsifier did not fire -- instrument blind")
    if not quiet_ok:
        why.append("CONTAMINATED: quietness not established for a confirmation run")
    return ("PROMOTE" if not why else "NOT PROMOTED"), why


def selftest():
    """This gate must be able to return NO, and must not refuse a 1-bit field."""
    ok = True
    GOODLEDGER = {"cases_with_ledger": 2, "cases_total": 2,
                  "ledger_mismatches": 0, "distinct_requested_values": 2,
                  "distinct_actual_encodings": 2, "match_bit_collision": False}
    w1 = {"V_distinct_valid_payloads": 2, "L_legal_values": 2, "distinct_bytes": 2,
          "distinct_oracles": 2, "moved_min": 1, "moved": 1, "disagree": 0,
          "cross_run_agree_pct": 100.0, "control_moved": 3, "falsifier_moved": 1,
          "gateA_ledger": dict(GOODLEDGER), "sem_checked": 2, "sem_confirmed": 1,
          "semantic_buckets": {"correct_effect": 1, "silent_zero_or_no_write": 1,
                               "rejected_or_faulted": 1}}
    v, why = rule(w1, 2, True)
    if v != "PROMOTE":
        print("SELFTEST FAIL: a width-1 field with moved=1, disagree=0 was "
              "refused: %s" % why); ok = False
    dead = dict(w1, V_distinct_valid_payloads=1, moved_min=0, moved=0,
                control_moved=0)
    if rule(dead, 2, True)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: an indistinguishable, unmoved field was promoted")
        ok = False
    alias = dict(w1, L_legal_values=8, distinct_bytes=4)
    if rule(alias, 2, True)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: an aliased sweep was promoted"); ok = False
    const = dict(w1, distinct_oracles=1)
    if rule(const, 2, True)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: a constant oracle was promoted"); ok = False
    # GATE A: a requested bit that never reached the dispatched program
    ledbad = dict(w1, gateA_ledger=dict(GOODLEDGER, ledger_mismatches=1))
    if rule(ledbad, 2, True)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: a case whose requested value != the value decoded "
              "from the ACTUAL dispatched bytes was promoted"); ok = False
    ledmiss = dict(w1, gateA_ledger=dict(GOODLEDGER, cases_with_ledger=0))
    if rule(ledmiss, 2, True)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: an arm with no actual-byte ledger was promoted")
        ok = False
    ledalias = dict(w1, gateA_ledger=dict(GOODLEDGER, match_bit_collision=True,
                                          distinct_actual_encodings=1))
    if rule(ledalias, 2, True)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: a match-bit collision was promoted"); ok = False
    # GATE C: liveness must never round up into semantics
    nosem = dict(w1, sem_checked=0, sem_confirmed=0)
    if rule(nosem, 2, True)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: sem_checked == 0 produced hardware-run"); ok = False
    if axes(nosem, True, 2)["semantics"] != "unknown":
        print("SELFTEST FAIL: zero semantic checks did not read `unknown`")
        ok = False
    if axes(nosem, True, 2)["liveness"] != "live":
        print("SELFTEST FAIL: a moving field did not read `live`"); ok = False
    blind = dict(w1, moved_min=0, moved=0, control_moved=0, falsifier_moved=0)
    if axes(blind, True, 2)["liveness"] != "carrier-undecidable":
        print("SELFTEST FAIL: an arm with a dead control read as inert rather "
              "than carrier-undecidable"); ok = False
    # GATE E: a busy machine cannot confirm
    if rule(w1, 2, False)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: a contaminated run confirmed a field"); ok = False
    return ok


LABEL = {"PROMOTE": "hardware-run", "NOT PROMOTED": "untested"}


def axes(e, quiet_ok, n_runs):
    """The six independent axes of RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 2.
    A result on one axis must never imply a result on another."""
    g = e.get("gateA_ledger") or {}
    geom = "unverified"
    if g.get("cases_with_ledger") and not g.get("ledger_mismatches"):
        geom = ("geometry-mapped" if not g.get("match_bit_collision")
                else "ledger-verified (aliased)")
    # Gate B: an arm whose positive control failed cannot support an inert
    # reading, and cannot support "the rest of the domain is inert" either --
    # even when one value happens to move. Both halves are reported.
    ctl_ok = e.get("control_moved", 0) > 0 and e.get("falsifier_moved", 0) > 0
    if e.get("moved_min", 0) > 0 and ctl_ok:
        live = "live"
    elif e.get("moved_min", 0) > 0:
        live = ("live at %d of %d values; control FAILED so the remaining "
                "values are carrier-undecidable, not inert"
                % (e.get("moved_min", 0), e.get("L_legal_values", 0)))
    elif ctl_ok:
        live = ("accepted-inert in the tested envelope; global role unknown")
    else:
        live = "carrier-undecidable"
    if not e.get("sem_checked"):
        sem = "unknown"
    elif e.get("sem_confirmed") and len(e.get("semantic_buckets") or {}) >= 3:
        sem = "bounded-map"
    elif e.get("sem_confirmed"):
        sem = "hypothesis"
    else:
        sem = "unknown"
    repro = "incomplete"
    if n_runs >= 2 and (e.get("cross_run_agree_pct") or 0) >= MIN_AGREE:
        repro = "auditable" if not quiet_ok else "independently-confirmed"
    return {"encoding_geometry": geom, "liveness": live, "semantics": sem,
            "compiler_recipe": "not-generated", "target": "G17P-direct",
            "reproducibility": repro}


def main():
    if not selftest():
        return 2
    runs = sys.argv[1:]
    if not runs:
        print(__doc__)
        return 2
    exp = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    recs = load(runs)
    rnames = [os.path.basename(os.path.normpath(d)) for d in runs]
    q = quiet(runs)
    out, flat = {}, {}
    for mnem, field in TARGETS:
        arms = analyse(recs, mnem, field, rnames)
        if not arms:
            flat["%s.%s" % (mnem, field)] = {
                "label": "untested", "verdict": "NO RECORDS",
                "target": "G17P", "evidence": ["EXP-0201"]}
            continue
        # the arm that best supports a promotion; every arm is reported.
        best, bestv, bestwhy = None, "NOT PROMOTED", ["no arm"]
        for a, e in arms.items():
            qok = all(q.get(r, {}).get("quiet") for r in rnames)
            v, why = rule(e, len(rnames), qok)
            e["verdict"], e["reasons"] = v, why
            if v == "PROMOTE" and best is None:
                best, bestv, bestwhy = a, v, why
        if best is None:
            # report the arm with the fewest blocking reasons
            a = min(arms, key=lambda k: len(arms[k]["reasons"]))
            best, bestv, bestwhy = a, arms[a]["verdict"], arms[a]["reasons"]
        out["%s.%s" % (mnem, field)] = {"arms": arms, "chosen_arm": best,
                                        "verdict": bestv, "reasons": bestwhy}
        e = arms[best]
        flat["%s.%s" % (mnem, field)] = {
            "label": LABEL[bestv],
            "verdict": bestv,
            "range": "%d values dispatched, %d distinct encodings, %d legal"
                     % (e["L_legal_values"], e["distinct_bytes"], e["L_legal_values"]),
            "target": "G17P",
            "evidence": ["EXP-0201"],
            "start": next(r["start"] for r in recs
                          if r.get("instr") == mnem and r.get("field") == field),
            "width": next(r["width"] for r in recs
                          if r.get("instr") == mnem and r.get("field") == field),
            "values_dispatched": e["L_legal_values"],
            "distinct_bytes": e["distinct_bytes"],
            "distinct_oracles": e["distinct_oracles"],
            "V_distinct_valid_payloads": e["V_distinct_valid_payloads"],
            "moved": e["moved"], "moved_min": e["moved_min"],
            "disagree": e["disagree"], "common": e["common"],
            "cross_run_agree_pct": e["cross_run_agree_pct"],
            "cross_run_agree_pct_adjudicated": e.get("agree_pct_adjudicated"),
            "disagree_adjudicated": e.get("disagree_adjudicated"),
            "disagreeing_values": e.get("disagreeing_values"),
            "control_moved": e["control_moved"],
            "falsifier_moved": e["falsifier_moved"],
            "hard_outcomes": e["hard_outcomes"],
            "observed_fns": e["observed_fns"],
            "accept_values": e["accept_values"],
            "n_arms": len(arms),
            "chosen_arm": best,
            "reasons": bestwhy,
            "gateA_ledger": e.get("gateA_ledger"),
            "sem_checked": e.get("sem_checked"),
            "sem_confirmed": e.get("sem_confirmed"),
            "semantic_buckets": e.get("semantic_buckets"),
            "axes": axes(e, all(q.get(r, {}).get("quiet") for r in rnames),
                         len(rnames)),
        }
    res = {"_meta": {"runs": rnames, "quiet": q,
                     "thresholds": {"min_agree_pct": MIN_AGREE,
                                    "moved_over_disagree": MOVED_OVER_DISAGREE,
                                    "rule": "moved >= 2*disagree AND moved > 0"}},
           "fields": out}
    ap = os.path.join(exp, "analysis")
    json.dump(res, open(os.path.join(ap, "verdicts_full.json"), "w"), indent=1,
              default=str)
    json.dump(flat, open(os.path.join(ap, "field_verdicts.json"), "w"), indent=1,
              default=str)
    print("runs: %s" % ", ".join("%s(%s)" % (r, "QUIET" if q[r]["quiet"] else
                                             ("BUSY" if q[r]["quiet"] is False
                                              else "UNMEASURED")) for r in rnames))
    for k, v in flat.items():
        print("  %-28s %-13s V=%-4s L=%-4s bytes=%-4s orc=%-4s moved=%-4s "
              "dis=%-4s agree=%s"
              % (k, v.get("verdict"), v.get("V_distinct_valid_payloads"),
                 v.get("values_dispatched"), v.get("distinct_bytes"),
                 v.get("distinct_oracles"), v.get("moved_min"),
                 v.get("disagree"),
                 ("%.2f%%" % v["cross_run_agree_pct"])
                 if v.get("cross_run_agree_pct") is not None else "-"))
        for r in v.get("reasons", []):
            print("        - %s" % r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
