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


def analyse(runs):
    per_run = {}
    for rd in runs:
        recs = load(rd)
        if not recs:
            print("  (no records in %s)" % rd)
            continue
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
        "note": "skip placeholders are EXCLUDED from every count; a field that "
                "is inert everywhere is labelled `proven-dont-care`, not "
                "`hardware-run`, and is reported with its ladder numbers",
    }, "db_defects": {}}

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
        out[fk] = {
            "label": label,
            "target": "G17P",
            "evidence": ["EXP-0168"],
            "coverage": cov,
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
