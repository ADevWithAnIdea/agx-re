#!/usr/bin/env python3
"""EXP-0168 verdicts: the pre-registered promotion gate, applied to the gated runs.

  python3 analysis/verdicts.py --runs raw/g17p_*_run0{2,3,4}

Produces `analysis/field_verdicts.json` in the FLAT `<mnemonic>.<field>` schema
of FIELD-SWEEP-PROTOCOL section 5, plus a `db_defects` section and a human
summary on stdout.

THE GATE (frozen in PRE_REGISTRATION section 7, and deliberately ABOVE the
orchestrator's own >=99% / >=2x bar):

  1. >=99.5% per-value cross-run agreement on `outcome`, over values BOTH runs
     actually dispatched;
  2. movement >= 4x the disagreement count;
  3. the arm's LIVENESS LADDER passed in every gated run (>=2 distinct digests);
  4. the arm's FALSIFIER failed in every gated run;
  5. dense coverage for width <= 8;
  6. no case counted whose `validity != "valid"`;
  7. the byte-mate control reported.

Two things this script refuses to do, both because EXP-0164 showed what happens
otherwise:

  * **it never counts a skip placeholder as an observation.** A case that was
    never dispatched (hang budget exhausted) carries `role`/`note` saying so and
    is excluded. EXP-0164 scored 248 of EXP-0144's `pack_convert.b7` placeholders
    as measurements and withheld a field that, measured against the runs that
    actually measured, agrees 256/256.
  * **it never labels a genuinely inert field `hardware-run` on its own.** A
    field that is inert everywhere CANNOT satisfy clause 2, by construction. It
    is labelled `proven-dont-care` and reported WITH ITS LADDER NUMBERS so the
    orchestrator decides.

Labels are the eight from `docs/evidence-classification.md` plus the explicit
`proven-dont-care` / `still-underpowered` reporting states, which are NOT
promotions and are flagged as such in the output.

CLEAN-ROOM: derived analysis of our own raw observations. No device, no Apple
binary.
"""
from __future__ import print_function

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent

AGREE_PCT = 99.5
MOVE_OVER_DISAGREE = 4.0
ORCH_AGREE_PCT = 99.0
ORCH_MOVE_OVER_DISAGREE = 2.0


def load(rundir):
    p = Path(rundir) / "sweep.jsonl"
    recs = []
    if not p.exists():
        return recs
    with p.open() as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                recs.append(json.loads(ln))
            except Exception:
                pass
    return recs


POISON = 0xDEADBEEF
EXPECTED_PRE = 0x5A5A5A5A & 0x7F          # 90
SENT_POST = 111
SENT_WITNESS = 77                          # the STOP/terminal post-stop witness


def recorrect_terminating(recs):
    """RE-DERIVE `validity`/`outcome` for the STOP/midprogram arm from each
    record's OWN preserved observation, uniformly across every run.

    WHY THIS EXISTS. That arm places the stop under test BEFORE the register
    dump, so if the stop does its documented job the dump never runs, the
    register window stays 0xDEADBEEF and the POST sentinel is never
    materialized. **That absence IS the measurement.** The generic
    run-integrity rule scores it as corruption, and it did: in gated run02,
    835 of 836 STOP/midprogram cases were written `invalid_sentinel` /
    `undecodable`, which excluded them from every count and reduced
    `stop.reserved`, `stop.b1`, `stop.b2` and `stop.b3` to ONE carrier each --
    silently gutting the only carrier in which a program-end token's field can
    express what it controls. Two of my own rules were in direct conflict and
    the integrity one won without saying so.

    `harness/sweeprun.py::validity_of(terminating=True)` now records this
    correctly at the point of measurement. This function applies the SAME rule
    to runs already on disk, so run02, run03 and any later run are scored
    identically rather than one of them being re-run under a different rule.
    Nothing in `raw/` is edited -- raw is append-only evidence; the correction
    is computed here, from fields the raw already carries
    (`observed.pre`, `observed.post`, `observed.regs`, `observed.tail_ok`),
    and every corrected record is counted and reported.

    The rule, which is a discriminator and not a waiver -- PRE is written to
    MEMORY BEFORE the stop under test, so a correct dispatch must always show it:
        tail written                              -> invalid_sentinel
        PRE absent                                -> invalid_sentinel
        PRE present, POST poison, window poison   -> valid, outcome `ok`
                                                     (the stop TERMINATED)
        PRE present, dump present                 -> valid, outcome
                                                     `wrong_value`
                                                     (it did NOT terminate)
    """
    n = 0
    for r in recs:
        arm = r.get("arm")
        if arm not in ("STOP/midprogram", "STOP/terminal"):
            continue
        if not r.get("attempts"):
            continue
        atts = r.get("attempts") or [{}]
        if (atts[-1].get("status") or "OK") != "OK":
            continue                       # a genuine fault/hang IS a result
        o = r.get("observed") or {}
        if "pre" not in o or "post" not in o or not o.get("regs"):
            continue
        old_v, old_o, old_m = r.get("validity"), r.get("outcome"), r.get("moved")
        if not o.get("tail_ok", True):
            v, oc, mv = "invalid_sentinel", old_o, old_m
        elif o["pre"] != EXPECTED_PRE:
            v, oc, mv = "invalid_sentinel", old_o, old_m
        elif arm == "STOP/midprogram":
            # the stop under test sits BEFORE the dump: terminating leaves the
            # whole register window poison and POST never materialized.
            term = (o["post"] == POISON and all(x == POISON for x in o["regs"]))
            v, oc, mv = "valid", ("ok" if term else "wrong_value"), (not term)
        else:
            # STOP/terminal: the dump has ALREADY run in every case, so the 16
            # registers are identical by construction and cannot carry the
            # measurement. The discriminator is the POST-STOP WITNESS word
            # (W_PROBE): the stop under test is followed by a write of
            # SENT_WITNESS into it, so
            #     probe == POISON        -> the stop TERMINATED (correct)
            #     probe == SENT_WITNESS  -> it did NOT terminate
            # `classify_slots` compares only the register dump, so it scored the
            # falsifier -- which shows probe 0x4d vs the baseline's 0xdeadbeef,
            # i.e. plainly firing -- as `ok`, failing the arm's own
            # falsifier_contrast ladder and blocking all four `stop` fields.
            # It also meant the terminal arm's sweep could not see ANYTHING:
            # all 836 cases read `ok` / moved=False.
            if o["post"] != SENT_POST:
                v, oc, mv = "invalid_sentinel", old_o, old_m
            else:
                pr = o.get("probe")
                term = (pr == POISON)
                v, oc, mv = "valid", ("ok" if term else "wrong_value"), (not term)
        if (v, oc, mv) != (old_v, old_o, old_m):
            r["validity"], r["outcome"], r["moved"] = v, oc, mv
            r["_recorrected"] = {"from": [old_v, old_o, old_m],
                                 "rule": "terminating:" + arm.split("/")[-1]}
            n += 1
    return n


def _db_defects():
    """The descriptor defects this experiment measured, for the orchestrator.

    `db.json` is NOT edited here -- EXP-0165 owns it. These rows carry the
    corrected model plus the evidence, so the fix can be made without re-running
    anything. Source: analysis/bitcheck.json, which checks EXHAUSTIVELY over
    every value that the harness's bit surgery equals `isadb.assemble` -- 79
    fields agree exactly, 0 mismatches, and these 4 are a field DECLARED over
    bits its own descriptor's `match` constant PINS. Same self-contradiction
    EXP-0162 fixed in `pixel_order.flags`: the field is undecodable and
    unemittable at every value outside the pin, because those values are a
    DIFFERENT INSTRUCTION.
    """
    bc = HERE / "bitcheck.json"
    out = {}
    if bc.exists():
        try:
            data = json.loads(bc.read_text())
        except Exception:
            return out
        for d in data.get("db_defect_suspects", []):
            lo, hi = d["match_pins_bits"]
            free = [b for b in range(d["start"], d["start"] + d["width"])
                    if not (lo <= b <= hi)]
            key = "%s.%s" % (d["instr"], d["field"])
            out[key] = {
                "kind": "field declared over match-pinned bits",
                "declared": {"start": d["start"], "width": d["width"]},
                "match_pins_bits": [lo, hi],
                "free_bits": free,
                "real_encodable_range": 1 << len(free),
                "evidence": "analysis/bitcheck.json (exhaustive over all 256 "
                            "values; 79/83 fields agree exactly, 0 mismatches)",
                "consequence": "every value outside the pin is a DIFFERENT "
                               "instruction, not a value of this field, so the "
                               "field is unemittable there and a dense sweep of "
                               "2**width is not achievable even in principle",
                "precedent": "same shape as the pixel_order.flags defect "
                             "EXP-0162 fixed",
                "not_edited_here": "tools/agx-isa/db.json (EXP-0165 owns it)",
            }
    if "iter_at.grp" in out:
        out["iter_at.grp"]["also_explains"] = (
            "why no run has ever swept this field past ~25 of 256 values: 254 "
            "of the 256 are out-of-descriptor bit patterns, i.e. a decode "
            "desync. EXP-0155 hung at 0x00, 0x01, 0x0f, 0x12, 0x16, 0x18 and "
            "EXP-0163 at 0x00 and 0x50, and BOTH tripped the two-hang-per-field "
            "stop rule. The two legal values are 0x2f and 0xaf.")
    if "reg_move_cb.form" in out:
        out["reg_move_cb.form"]["measured_here"] = (
            "EXP-0168 sweeps byte+2 as a whole BYTE rather than as the declared "
            "field, so the sweep itself is valid; run02/run03 show byte+2 = 0x0b "
            "behaving differently from the other 13 form values (dst tracks the "
            "field at 1/15 rather than 15/15), which is consistent with 0x0b "
            "being a distinct form and not a value of a wider `form` field.")
    if "shift_amt_move.kind" in out:
        out["shift_amt_move.kind"]["measured_here"] = (
            "also swept as a whole byte, not as the declared field; "
            "shift_amt_move.src_flag is hardware-run at 100.000% agreement "
            "(2 values, 26 distinct encodings, 22 moved).")
    return out


def is_placeholder(r):
    """Never dispatched. Excluded from every count."""
    if r.get("role") == "arm_not_run":
        return True
    if not r.get("attempts"):
        return True
    return False


def key_of(r):
    """The per-value identity a cross-run comparison joins on.

    Joined on BYTES, not on the field label: EXP-0144's committed raw can no
    longer be joined by `field` because db.json's label strings moved out from
    under it. `bytes` is stable.
    """
    return (r.get("arm"), r.get("role"), r.get("field"), r.get("cross_value"),
            r.get("bytes"))


def _load_db():
    for c in (HERE.parent / "work" / "frozen" / "db.json",
              HERE.parents[2] / "tools" / "agx-isa" / "db.json"):
        if c.exists():
            try:
                return json.loads(c.read_text())
            except Exception:
                pass
    return {}


DB = _load_db()


def analyse(runs):
    per_run = {}
    for rd in runs:
        recs = load(rd)
        if not recs:
            print("  (no records in %s)" % rd)
            continue
        nfix = recorrect_terminating(recs)
        if nfix:
            print("  %s: re-derived validity/outcome on %d STOP/midprogram "
                  "records (terminating rule; raw untouched)"
                  % (Path(rd).name, nfix))
        per_run[Path(rd).name] = recs

    # ---- ladders and falsifiers, per arm, per run --------------------------
    ladder = defaultdict(dict)      # arm -> run -> {"n":, "distinct":, "pass":}
    falsif = defaultdict(dict)
    for run, recs in per_run.items():
        by_arm_l = defaultdict(list)
        by_arm_f = defaultdict(list)
        for r in recs:
            if is_placeholder(r) or r.get("validity") != "valid":
                continue
            if r.get("role") == "ladder":
                by_arm_l[r["arm"]].append(r)
            elif r.get("role") == "falsifier":
                by_arm_f[r["arm"]].append(r)
        for arm, rs in by_arm_l.items():
            hs = set()
            for r in rs:
                o = r.get("observed") or {}
                hs.add(o.get("digest") or o.get("hash"))
            ladder[arm][run] = {"n": len(rs), "distinct": len(hs),
                                "pass": len(hs) >= 2}
        for arm, rs in by_arm_f.items():
            # the falsifier must NOT score ok
            bad = [r for r in rs if r.get("outcome") == "ok"]
            falsif[arm][run] = {"n": len(rs), "scored_ok": len(bad),
                                "pass": len(rs) > 0 and not bad}

    # Fields whose REAL encodable range is narrower than 2**width, because the
    # descriptor's own `match` constant pins some of the bits the field is
    # declared over. Measured exhaustively offline in analysis/bitcheck.json,
    # not assumed. db.json is NOT edited here (EXP-0165 owns it) -- these rows
    # carry the corrected number and the defect travels under `db_defects`.
    # Values a field DISPATCHED but which THIS CARRIER cannot DECIDE.
    # `dst = 15` on every 4-bit-dst instruction, because isa_helpers.R_IDX = 15
    # is our own device_store index register and store_word() re-seeds it with
    # mov_imm(15, 0) before every store, including the store that reads r15.
    # This is a property of the HARNESS, not of the hardware: EXP-0174 shows r15
    # is an ordinary writable GPR. A row must not claim dense 16/16 when one of
    # the 16 is undecidable, whatever the reason.
    UNDECIDABLE = {
        "uniform_mov.dst": [15], "falu2.dst": [15], "falu2i.dst": [15],
        "get_sr.dst": [15], "vtx_out_pos.dst": [15],
        "reg_move_c0.dst": [15], "reg_move_c1.dst": [15],
        "reg_move_c2var.dst": [15], "reg_move_c9.dst": [15],
        "reg_move_cb.dst": [15],
    }

    ENCODABLE_RANGE = {
        "iter_at.grp": 2,             # declared 0..7; match pins 0..6 -> bit 7 only
        "pixel_order.scope": 32,      # declared 24..31; match pins 28..30
        "reg_move_cb.form": 16,       # declared 16..23; match pins 16..19
        "shift_amt_move.kind": 16,    # declared 16..23; match pins 16..19
    }

    # ---- sweeps ------------------------------------------------------------
    # (mnemonic.field) -> arm -> run -> {value_key: outcome}
    sweeps = defaultdict(lambda: defaultdict(dict))
    moved_cnt = defaultdict(lambda: defaultdict(dict))
    covered = defaultdict(lambda: defaultdict(set))
    # DISTINCT INSTRUCTION BYTES, counted from the raw's own `bytes` key and
    # NEVER from the dispatched-value count. This is the only thing that reveals
    # the DEF-0166-1 signature -- a sweep that dispatches 256 values while the
    # hardware only ever sees 8 distinct encodings, because the field's bits
    # were narrower than the sweep believed, or because the descriptor pins some
    # of them. `values_dispatched` alone cannot show that, and a THIN or
    # UNDER-COVERED row is exactly what it hides.
    dbytes = defaultdict(lambda: defaultdict(set))
    starts, widths = {}, {}
    placeholders = defaultdict(lambda: defaultdict(int))
    invalids = defaultdict(lambda: defaultdict(int))
    bytemate = defaultdict(lambda: defaultdict(dict))
    for run, recs in per_run.items():
        for r in recs:
            role = r.get("role")
            if role not in ("sweep", "bytemate"):
                continue
            fname = r.get("field") or ""
            base = fname.split("@")[0]
            fk = "%s.%s" % (r.get("instr"), base)
            arm = r.get("arm")
            if is_placeholder(r):
                placeholders[fk][run] += 1
                continue
            if r.get("validity") != "valid":
                invalids[fk][run] += 1
                continue
            k = key_of(r)
            if role == "bytemate":
                bytemate[fk].setdefault(arm, {}).setdefault(run, {})[k] = \
                    (r.get("outcome"), bool(r.get("moved")))
                continue
            sweeps[fk][arm].setdefault(run, {})[k] = r.get("outcome")
            moved_cnt[fk][arm].setdefault(run, {})[k] = bool(r.get("moved"))
            covered[fk][arm].add(r.get("value"))
            if r.get("bytes"):
                dbytes[fk][arm].add(r["bytes"])
            if r.get("fwidth"):
                widths[fk] = r["fwidth"]
            if r.get("fstart") is not None:
                starts[fk] = r["fstart"]

    out = {"_meta": {
        "experiment": "EXP-0168-g17p-dst-resweep",
        "target": "G17P",
        "runs": sorted(per_run),
        "gate": {"cross_run_agreement_pct": AGREE_PCT,
                 "movement_over_disagreement": MOVE_OVER_DISAGREE,
                 "orchestrator_bar": {
                     "cross_run_agreement_pct": ORCH_AGREE_PCT,
                     "movement_over_disagreement": ORCH_MOVE_OVER_DISAGREE}},
        "schema": "FIELD-SWEEP-PROTOCOL section 5, flat <mnemonic>.<field>",
        "corrections_applied": [
            "STOP/midprogram validity/outcome/moved re-derived from each "
            "record's own observed.{pre,post,regs,tail_ok} -- on that carrier "
            "the ABSENCE of the POST sentinel is the measurement (the stop "
            "terminated before the dump), and the generic run-integrity rule "
            "scored it as corruption, discarding 835 of 836 cases in run02.",
            "STOP/terminal outcome/moved re-derived from observed.probe -- on "
            "that carrier the register dump has already run in every case and "
            "cannot carry the measurement; the discriminator is the post-stop "
            "WITNESS word (POISON = terminated, 77 = did not). classify_slots "
            "reads only the register dump, so it scored the plainly-firing "
            "falsifier (probe 0x4d vs baseline 0xdeadbeef) as `ok` and blocked "
            "all four `stop` fields on their own falsifier_contrast ladder.",
            "raw/ is NOT edited; both rules are applied identically to every "
            "run, and every corrected record keeps its prior values under "
            "`_recorrected`."],
        "note": "skip placeholders are EXCLUDED from every count; a field that "
                "is inert everywhere is labelled `proven-dont-care`, not "
                "`hardware-run`, and is reported with its ladder numbers",
    }, "db_defects": _db_defects()}

    for fk in sorted(sweeps):
        arms = sweeps[fk]
        best = None
        per_arm_report = {}
        total_moved = 0
        for arm, byrun in arms.items():
            runs_here = sorted(byrun)
            pairs = {}
            for i in range(len(runs_here)):
                for j in range(i + 1, len(runs_here)):
                    A, B = byrun[runs_here[i]], byrun[runs_here[j]]
                    common = sorted(set(A) & set(B))
                    if not common:
                        continue
                    dis = [k for k in common if A[k] != B[k]]
                    mv = sum(1 for k in common
                             if moved_cnt[fk][arm][runs_here[i]].get(k))
                    pairs["%s|%s" % (runs_here[i], runs_here[j])] = {
                        "common": len(common), "disagreements": len(dis),
                        "agree_pct": round(100.0 * (len(common) - len(dis))
                                           / len(common), 3),
                        "moved": mv,
                        "move_over_disagree": (float("inf") if not dis
                                               else round(mv / len(dis), 2)),
                    }
            armmoved = max((sum(1 for k, v in moved_cnt[fk][arm][r].items() if v)
                            for r in runs_here), default=0)
            total_moved = max(total_moved, armmoved)
            lad = ladder.get(arm, {})
            fal = falsif.get(arm, {})
            bm = bytemate.get(fk, {}).get(arm, {})
            bm_moved = 0
            for r, d in bm.items():
                bm_moved = max(bm_moved, sum(1 for v in d.values() if v[1]))
            per_arm_report[arm] = {
                "runs": runs_here,
                "values_dispatched": len(covered[fk][arm]),
                "distinct_bytes": len(dbytes[fk][arm]),
                "moved": armmoved,
                "pairs": pairs,
                "ladder": lad,
                # LADDER SUBSTITUTE, pre-declared and NAMED so it is never
                # invisible in a verdict row. `stop` has no known-live field --
                # every bit of it is either the opcode or the `reserved` field
                # under test -- so R3's "sweep a known-live control of the same
                # instruction" is unbuildable, and the arm's `ladder` is empty.
                # Its detection power instead comes from the FALSIFIER CONTRAST:
                # a mutation of this same instruction's own byte0 drives the
                # observable to a second, distinct state, measured on this exact
                # carrier. That is the same claim a ladder makes (the observable
                # CAN resolve a difference here), reached through the control
                # that does exist. It is accepted ONLY when the falsifier fires
                # in every gated run, and the row says which kind was used.
                "ladder_kind": ("field_control" if lad
                                else "falsifier_contrast"),
                "ladder_pass_all_runs": (
                    all(v["pass"] for v in lad.values()) if lad
                    else (bool(fal) and all(v["pass"] for v in fal.values()))),
                "falsifier": fal,
                "falsifier_pass_all_runs": bool(fal) and all(
                    v["pass"] for v in fal.values()),
                "bytemate_cases_that_moved": bm_moved,
                "outcomes": {r: dict(Counter(byrun[r].values()))
                             for r in runs_here},
            }
            for pname, p in pairs.items():
                cand = (p["agree_pct"], p["common"])
                if best is None or cand > best[0]:
                    best = (cand, arm, pname, p)

        w = widths.get(fk, 8)
        dense_needed = (1 << w) if w <= 8 else None
        maxcov = max((len(covered[fk][a]) for a in arms), default=0)
        dense_ok = (dense_needed is None) or (maxcov >= dense_needed)

        # --- verdict ------------------------------------------------------
        label = "untested"
        reason = []
        if best is None:
            label = "still-underpowered"
            reason.append("no run pair shares a dispatched value")
        else:
            (_ap, _cm), barm, bpair, bp = best
            armrep = per_arm_report[barm]
            ladder_ok = armrep["ladder_pass_all_runs"]
            fals_ok = armrep["falsifier_pass_all_runs"]
            agree_ok = bp["agree_pct"] >= AGREE_PCT
            move_ok = bp["move_over_disagree"] >= MOVE_OVER_DISAGREE
            n_carriers = len(arms)
            dims = sorted(set(
                next((r.get("dim") for run in per_run.values() for r in run
                      if r.get("arm") == a), "?") for a in arms))
            if not ladder_ok:
                label = "still-underpowered"
                reason.append("the liveness ladder (kind=%s) did not pass in "
                              "every run on the best arm -- an arm that cannot "
                              "show its ladder is not evidence of inertness"
                              % armrep.get("ladder_kind"))
            elif not fals_ok:
                label = "still-underpowered"
                reason.append("the pre-registered falsifier did not fail; the "
                              "sweep proves nothing about detection")
            elif not dense_ok:
                label = "still-underpowered"
                reason.append("coverage below FIELD-SWEEP-PROTOCOL 3.3 dense "
                              "requirement (%d of %d values)"
                              % (maxcov, dense_needed or 0))
            elif total_moved == 0:
                if len(dims) >= 2:
                    # ORCHESTRATOR RULING 2026-08-30, applied here rather than
                    # argued in prose: an inert field is emitter-grade ONLY if
                    # the carriers differ in the dimension the field controls
                    # AND the field's ROLE is known. Emitter-grade asserts the
                    # implementer may CHOOSE the value; "emit what the compiler
                    # emitted" is a captured-template dependency, so a
                    # proven-inert-but-unknown-role field is
                    # `single-template-inference`, never `hardware-run`
                    # (the EXP-0163 convention).
                    label = "proven-dont-care"
                    reason.append(
                        "0 movement across %d carriers that DIFFER in the "
                        "dimension the field controls, each passing its "
                        "liveness ladder, at %.3f%% cross-run agreement. The "
                        "movement clause of the gate is UNMEETABLE for an inert "
                        "field by construction; this is REPORTED with its "
                        "ladder numbers, not self-promoted. If the field's role "
                        "is not independently known, the orchestrator's label "
                        "is `single-template-inference`, NOT `hardware-run`."
                        % (n_carriers, bp["agree_pct"]))
                else:
                    label = "still-underpowered"
                    reason.append(
                        "0 movement, but only ONE distinct carrier dimension "
                        "was built -- exactly the EXP-0155 samp_extra / "
                        "iter_at.loc failure mode. A second carrier differing "
                        "in the dimension is required.")
            elif agree_ok and move_ok:
                label = "hardware-run"
                reason.append("%.3f%% agreement over %d shared values, %d moved "
                              "vs %d disagreements (%.2fx), ladder and "
                              "falsifier passed in every run"
                              % (bp["agree_pct"], bp["common"], bp["moved"],
                                 bp["disagreements"], bp["move_over_disagree"]))
            else:
                label = "still-underpowered"
                reason.append("best pair %s: %.3f%% agreement (need %.1f), "
                              "movement/disagreement %.2f (need %.1f)"
                              % (bpair, bp["agree_pct"], AGREE_PCT,
                                 bp["move_over_disagree"], MOVE_OVER_DISAGREE))

        # ---- machine-readable COVERAGE on every row ----------------------
        # Required so `tools/agx-isa/validate_labels.py` can flag THIN and
        # UNDER-COVERED rows instead of taking a label's word for it.
        # `distinct_bytes` is the max over arms of the number of DISTINCT
        # instruction byte strings the hardware actually saw for this field.
        maxbytes = max((len(dbytes[fk][a]) for a in arms), default=0)
        w = widths.get(fk, 8)
        enc = ENCODABLE_RANGE.get(fk, 1 << w)
        cov = {
            "values_dispatched": maxcov,
            "distinct_bytes": maxbytes,
            "encodable_range": enc,
            "start": starts.get(fk),
            "width": widths.get(fk),
            "dense_required": dense_needed,
            "dense_ok": dense_ok,
            # THE DEF-0166-1 CHECK, computed rather than asserted: if the
            # hardware saw far fewer distinct encodings than we dispatched
            # values, the sweep was narrower than it looks.
            "bytes_per_value": (round(maxbytes / maxcov, 3) if maxcov else None),
            "under_covered": bool(enc and maxcov < enc),
        }
        und = UNDECIDABLE.get(fk, [])
        if und:
            cov["undecidable_values"] = und
            cov["decidable_values"] = max(0, maxcov - len(und))
            cov["undecidable_why"] = (
                "CARRIER LIMIT, NOT A HARDWARE PROPERTY. isa_helpers.R_IDX = 15 "
                "is this harness's own device_store index register, and "
                "store_word() emits mov_imm(R_IDX, 0) before EVERY store -- "
                "including the store that reads r15 back. So r15 is clobbered "
                "to 0 immediately before it is observed, in every case, and "
                "dst=15 cannot be decided here whatever the hardware does. "
                "EXP-0174 confirms r15 is an ordinary writable GPR on a plan "
                "indexed on r7 (it holds its seed in all 64 baselines). "
                "EXP-0168's earlier claim that a 4-bit-nibble write to 15 is "
                "discarded is RETRACTED -- it was rule R-A (the observable must "
                "not co-vary with the field under test) violated in our own "
                "harness. The coverage accounting below is unchanged and still "
                "correct; only the cause is different.")
        # Is this a REAL db.json field, or a name this experiment invented for a
        # whole-byte sweep? `mov_imm.byte1`, `stop.b1/b2/b3`,
        # `uniform_mov.form_b2` and `uniform_mov.opdesc_b3` are OURS -- they are
        # byte-level companion sweeps, not declared fields -- and merging them as
        # fields would be a silent mis-attribution of exactly the kind this
        # experiment exists to prevent. Flagged so `merge_verdicts.py` can refuse
        # them by intent rather than by accident.
        mn, _, fldname = fk.partition(".")
        is_real = any(f.get("name") == fldname
                      for i in DB.get("instructions", [])
                      if i.get("mnemonic") == mn
                      for f in i.get("fields", []))
        out[fk] = {
            "label": label,
            "target": "G17P",
            "evidence": ["EXP-0168"],
            "coverage": cov,
            "is_declared_db_field": is_real,
            "synthetic_byte_sweep": (not is_real),
            "merge_note": ("" if is_real else
                           "NOT a declared db.json field -- this is a "
                           "whole-BYTE sweep this experiment named itself, run "
                           "as a companion/attribution control. It carries a "
                           "real measurement but must NOT be merged as a field "
                           "row; its value to the orchestrator is the byte-level "
                           "behaviour it documents, not a validation.json entry."),
            "range": "%d distinct values dispatched on the best arm%s"
                     % (maxcov, "" if dense_ok else " (BELOW dense requirement)"),
            "carriers": sorted(arms),
            "n_carriers": len(arms),
            "moved_total": total_moved,
            "per_arm": per_arm_report,
            "placeholders_excluded": dict(placeholders.get(fk, {})),
            "invalid_excluded": dict(invalids.get(fk, {})),
            "why": " | ".join(reason),
            "semantics": "",
            "note": "",
        }

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", default=str(HERE / "field_verdicts.json"))
    a = ap.parse_args()
    res = analyse(a.runs)
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True))

    print("=" * 78)
    counts = Counter(v["label"] for k, v in res.items()
                     if not k.startswith("_") and k != "db_defects")
    for fk in sorted(k for k in res if not k.startswith("_") and k != "db_defects"):
        v = res[fk]
        print("%-28s %-20s carriers=%-2d moved=%-5d %s"
              % (fk, v["label"], v["n_carriers"], v["moved_total"],
                 v["why"][:110]))
    print("-" * 78)
    print(json.dumps(dict(counts), sort_keys=True))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
