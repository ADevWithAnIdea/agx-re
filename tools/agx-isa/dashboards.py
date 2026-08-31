#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""dashboards.py -- the seven progress dashboards (RE_EXPERIMENT_PROCESS_CORRECTIONS 9).

Section 9 replaces the single completion number with seven separate dashboards:

  1 encoding geometry coverage
  2 field/bit liveness coverage
  3 semantic-map coverage
  4 canonical generated-recipe coverage
  5 direct G17P revalidation coverage
  6 reproducible evidence-chain coverage
  7 finite-resource limit and overflow coverage

WHY SEVEN AND NOT ONE
---------------------
The single headline read 79, then 41, 55, 38, 37, 34, 33, 32. Not one of those moves
was a hardware discovery; every one was a re-scoring, because one number was absorbing
six different kinds of evidence. Section 9's design requirement is therefore that the
dashboards CANNOT RESET THEMSELVES: "An experiment may advance one dashboard and leave
the others unchanged. That is real progress. A later semantic correction does not erase
geometry or liveness evidence."

HOW THE MONOTONICITY IS ENFORCED
--------------------------------
Not by convention -- by construction. Each dashboard has an ordered status ladder. Every
run appends its observations to an APPEND-ONLY ledger
(experiments/EXP-0209-dashboards/ledger/dashboard_ledger.jsonl), one line per
(dashboard, key). The reported figure is the HIGH-WATER MARK per key over the whole
ledger, so no later run can lower it. Three numbers are reported side by side:

  attained    the high-water mark. Monotonic by construction: a later run can only
              add lines, and `attained` is a max over lines.
  current     what THIS run re-derives from raw right now.
  downgraded  keys where current < attained, each with the reason and the run that
              attained it -- section 9's "precisely scoped downgrades".

A downgrade is reported, never applied. Section 9: "A broken citation or missing raw
artifact downgrades auditability; it does not by itself prove the hardware fact false."
So a broken citation moves dashboard 6 and leaves 1, 2, 3, 5 and 7 where they were.

WHERE THERE IS NO DATA
----------------------
Section 5: "Never report only a percentage." Every bucket carries an exact numerator and
denominator, and `no-data` is a REPORTED BUCKET with a stated reason (format-unreadable,
never probed, no registry) rather than a silent zero.

CLEAN ROOM: reads only this repository's own committed artifacts.

Usage:
    python3 tools/agx-isa/dashboards.py                    # score and append
    python3 tools/agx-isa/dashboards.py --no-append        # score without recording
    python3 tools/agx-isa/dashboards.py --selftest
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import evidence_index as EI          # noqa: E402
import promotion_check as PC         # noqa: E402
import axes_sidecar as AX           # noqa: E402

EXPDIR = os.path.join(ROOT, "experiments", "EXP-0209-dashboards")
LEDGER = os.path.join(EXPDIR, "ledger", "dashboard_ledger.jsonl")
REPORTS = os.path.join(EXPDIR, "reports")

# ---------------------------------------------------------------- the ladders
# Each ladder is ordered weakest -> strongest. Rank is the index. `attained` is a max
# over ranks, which is what makes the dashboard unable to reset itself.

LADDERS = {
    "geometry": [
        "no-data",              # nothing in raw under any keying
        "bytes-seen",           # actual bytes recorded, no caller intent to compare
        "ledger-verified",      # Gate A: requested == decoded, no disagreement
        "geometry-mapped",      # ...and every encodable value reached the hardware
    ],
    "liveness": [
        "no-data",
        "records-no-control",   # dispatched, but no detection-power control fired
        "decided-one-carrier",  # a control fired in one carrier
        "decided-multi-carrier",  # a control fired in two or more carriers
    ],
    "semantics": [
        "no-semantic-check",
        "checks-present",       # sem_checked > 0
        "bounded-map",          # ...covering >= 2 behaviour buckets
        "semantically-mapped",  # ...with a discriminating oracle, over >= 2 runs
    ],
    "recipe": [
        "not-generated",
        "generated-point",      # a generated program containing it has executed
        "generated-no-donor",   # ...with no field supplied by a captured donor
        "canonical-recipe-proven",  # ...and no unmeasured field remains
    ],
    "target": [
        "no-direct-target-evidence",
        "G16G-direct-only",     # committed M4 evidence: valid on its own target
        "G17P-direct",          # ran on the documentation target
        "G17P-direct-repeated",  # ...in two or more raw runs
    ],
    "audit": [
        "incomplete",           # citation unresolvable / no raw / no authored probe
        "citation-resolves",
        "auditable",            # records in raw/, with a frozen pre-registration
        "independently-confirmed",  # >= 2 raw runs and a second carrier or experiment
    ],
    "limits": [
        "no-data",
        "partial-sweep",        # some of the finite domain reached the hardware
        "full-domain-swept",    # every encodable value reached the hardware
        "limit-mapped",         # ...and the legal/rejected boundary was crossed
    ],
}

TITLES = {
    "geometry": "1. Encoding geometry coverage",
    "liveness": "2. Field/bit liveness coverage",
    "semantics": "3. Semantic-map coverage",
    "recipe": "4. Canonical generated-recipe coverage",
    "target": "5. Direct G17P revalidation coverage",
    "audit": "6. Reproducible evidence-chain coverage",
    "limits": "7. Finite-resource limit and overflow coverage",
}

POPULATION = {
    "geometry": "every field of every db.json descriptor",
    "liveness": "every field of every db.json descriptor",
    "semantics": "every field of every db.json descriptor",
    "recipe": "every emitter-relevant instruction (db.json descriptors whose "
              "`emitter_role` is not `data-word`)",
    "target": "every field of every db.json descriptor",
    "audit": "every claim row in validation.json (fields plus `_instruction` rows)",
    "limits": "every db.json field whose width is at most 8 bits, i.e. every finite "
              "selector Phase 2 says to dispatch exhaustively",
}


def rank(dash, status):
    return LADDERS[dash].index(status)


# ------------------------------------------------------------------- scoring


class Scorer(object):
    def __init__(self, index_dir=None, labels=None, root=None):
        self.e = PC.Evidence(index_dir=index_dir, root=root)
        self.spec = EI.load_db()
        self.rows = PC.claims_from_validation(labels)
        self.by_key = {r["key"]: r for r in self.rows}
        self.ev = {}

    def evidence(self, row):
        if row["key"] not in self.ev:
            self.ev[row["key"]] = self.e.gather(row)
        return self.ev[row["key"]]

    def field_rows(self):
        """One row per db.json field, whether or not validation.json labels it."""
        out = []
        for m, s in sorted(self.spec.items()):
            for f, (st, w) in sorted(s["fields"].items()):
                row = self.by_key.get("%s.%s" % (m, f))
                if row is None:
                    row = {"key": "%s.%s" % (m, f), "mnemonic": m, "field": f,
                           "label": "untested", "range": "", "target": "",
                           "evidence": [], "note": "", "axes": None,
                           "values_dispatched": None, "distinct_bytes": None,
                           "encodable_range": None, "start": st, "width": w}
                out.append((row, st, w))
        return out

    # -- 1 -------------------------------------------------------------
    def geometry(self):
        obs = {}
        for row, st, w in self.field_rows():
            ev = self.evidence(row)
            enc = 1 << w
            got = ev["n_actual_field_values"]
            if ev["ledger_disagree"] or ev["byte_ledger_disagree"]:
                s, why = "bytes-seen", ("ledger present but %d record(s) disagree; "
                                        "Gate A unmet"
                                        % (ev["ledger_disagree"] +
                                           ev["byte_ledger_disagree"]))
            elif ev["ledger_agree"] or ev["byte_ledger_agree"]:
                if got >= enc:
                    s, why = "geometry-mapped", ("%d/%d encodable values reached the "
                                                 "hardware" % (got, enc))
                else:
                    s, why = "ledger-verified", ("Gate A holds; %d/%d encodable values "
                                                 "reached the hardware" % (got, enc))
            elif ev["ledger_records"]:
                s, why = "bytes-seen", ("%d record(s) carried actual bytes but stated "
                                        "no requested value" % ev["ledger_records"])
            else:
                s, why = "no-data", self._nodata(ev)
            obs[row["key"]] = (s, why, ev["resolved"])
        return obs

    # -- 2 -------------------------------------------------------------
    def liveness(self):
        obs = {}
        for row, st, w in self.field_rows():
            ev = self.evidence(row)
            fired = ev.get("controls_fired") or []
            ncarr = len(set(ev["carriers"]))
            if ev["records"] == 0:
                s, why = "no-data", self._nodata(ev)
            elif not fired:
                s, why = "records-no-control", (
                    "%d record(s) but %s -- Gate B: zero movement without a firing "
                    "control is carrier-undecidable, not inertness"
                    % (ev["records"],
                       "no detection-power control in the cited raw"
                       if not ev["controls"] else
                       "none of the %d control arm(s) moved" % len(ev["controls"])))
            elif ncarr >= 2:
                s, why = "decided-multi-carrier", ("%d control arm(s) fired across %d "
                                                   "carriers" % (len(fired), ncarr))
            else:
                s, why = "decided-one-carrier", ("%d control arm(s) fired, 1 carrier "
                                                 "(%s)" % (len(fired),
                                                           ",".join(ev["carriers"]) or "unnamed"))
            obs[row["key"]] = (s, why, ev["resolved"])
        return obs

    # -- 3 -------------------------------------------------------------
    def semantics(self):
        obs = {}
        for row, st, w in self.field_rows():
            ev = self.evidence(row)
            nb = len(ev["sem_buckets"])
            if ev["sem_checks"] == 0:
                extra = []
                if ev["liveness_predictions"]:
                    extra.append("%d liveness prediction(s)" % ev["liveness_predictions"])
                if ev["prose_predictions"]:
                    extra.append("%d prose prediction(s)" % ev["prose_predictions"])
                if ev["baseline_oracle"]:
                    extra.append("%d baseline-comparison oracle(s)" % ev["baseline_oracle"])
                s = "no-semantic-check"
                why = ("0 semantic checks" +
                       (" (raw carries instead: %s)" % ", ".join(extra) if extra
                        else "; " + self._nodata(ev)))
            elif nb >= 2 and ev["n_oracle_digests"] > 1 and len(ev["raw_runs"]) >= 2:
                s, why = "semantically-mapped", (
                    "%d checks over %d buckets, %d distinct oracle payloads, %d runs"
                    % (ev["sem_checks"], nb, ev["n_oracle_digests"], len(ev["raw_runs"])))
            elif nb >= 2:
                s, why = "bounded-map", (
                    "%d checks over %d buckets, but %s"
                    % (ev["sem_checks"], nb,
                       "the oracle took ONE value across the sweep"
                       if ev["n_oracle_digests"] <= 1 else
                       "only %d raw run(s)" % len(ev["raw_runs"])))
            else:
                s, why = "checks-present", ("%d check(s) covering %d behaviour "
                                            "bucket(s) (%s)"
                                            % (ev["sem_checks"], nb,
                                               ",".join(ev["sem_buckets"]) or "none"))
            obs[row["key"]] = (s, why, ev["resolved"])
        return obs

    # -- 4 -------------------------------------------------------------
    def recipe(self):
        obs = {}
        reg = self.e.recipes()
        for m, s0 in sorted(self.spec.items()):
            if s0.get("emitter_role") == "data-word":
                continue
            rec = reg.get(m)
            if rec is None:
                s, why = "not-generated", ("no entry for %s in any committed "
                                           "analysis/template_dependency.json or "
                                           "analysis/generated_recipe.json" % m)
            elif not rec.get("in_generated_corpus"):
                s, why = "not-generated", ("%s (source %s)" % (rec.get("verdict"),
                                                               rec.get("_source")))
            else:
                donors = rec.get("donor_fields") or {}
                unmeasured = rec.get("n_unmeasured")
                if donors:
                    s, why = "generated-point", ("generated, but %d field(s) still "
                                                 "donor-supplied: %s"
                                                 % (len(donors), ",".join(sorted(donors))))
                elif isinstance(unmeasured, int) and unmeasured == 0:
                    s, why = "canonical-recipe-proven", ("generated with no donor "
                                                         "field and 0 unmeasured fields "
                                                         "(%s)" % rec.get("verdict"))
                else:
                    s, why = "generated-no-donor", ("generated with no donor field; "
                                                    "%s unmeasured field(s) remain"
                                                    % ("unknown" if unmeasured is None
                                                       else unmeasured))
            obs[m] = (s, why, [rec.get("_source")] if rec else [])
        return obs

    # -- 5 -------------------------------------------------------------
    def target(self):
        obs = {}
        for row, st, w in self.field_rows():
            ev = self.evidence(row)
            t = ev["targets"]
            g17 = t.get("G17P", 0)
            g16 = t.get("G16G", 0)
            n_g17_runs = len([r for r in ev["raw_runs"]
                              if EI._target_of_run(r) == "G17P"])
            if g17 and n_g17_runs >= 2:
                s, why = "G17P-direct-repeated", ("%d record(s) over %d G17P raw runs"
                                                  % (g17, n_g17_runs))
            elif g17:
                s, why = "G17P-direct", ("%d record(s) in %d G17P raw run(s)"
                                         % (g17, n_g17_runs))
            elif g16:
                s, why = "G16G-direct-only", ("%d record(s) on G16G/M4 only. Committed "
                                              "M4 evidence stays valid on its own "
                                              "target; it does not close a G17P row"
                                              % g16)
            else:
                s, why = "no-direct-target-evidence", self._nodata(ev)
            obs[row["key"]] = (s, why, ev["resolved"])
        return obs

    # -- 6 -------------------------------------------------------------
    def audit(self):
        obs = {}
        for row in self.rows:
            ev = self.evidence(row)
            if not row.get("evidence"):
                s, why = "incomplete", "no evidence citation"
            elif ev["unresolved"] or ev["no_raw"] or ev["no_authored"] or \
                    ev["quarantined"]:
                bits = []
                if ev["unresolved"]:
                    bits.append("unresolvable citation(s) %s" % ",".join(ev["unresolved"]))
                if ev["no_raw"]:
                    bits.append("no raw/ in %s" % ",".join(ev["no_raw"]))
                if ev["no_authored"]:
                    bits.append("no authored probe in %s" % ",".join(ev["no_authored"]))
                if ev["quarantined"]:
                    bits.append("QUARANTINED: %s" % ",".join(ev["quarantined"]))
                s, why = "incomplete", "; ".join(bits)
            elif ev["in_raw"] == 0:
                s = "citation-resolves"
                why = ("citation resolves with raw/ and an authored probe, but no "
                       "record for this row was found under any keying inside raw/"
                       + ("; %d derived record(s) exist outside raw/ (%s)"
                          % (ev["derived_records"], ",".join(ev["derived_only"][:3]))
                          if ev["derived_records"] else "")
                       + ("; %d non-record file(s) hold the evidence in an "
                          "unreadable format" % ev["nonrecord_files"]
                          if ev["nonrecord_files"] else ""))
            elif len(ev["raw_runs"]) >= 2 and (len(set(ev["carriers"])) >= 2
                                               or len(ev["indexed"]) >= 2):
                s, why = "independently-confirmed", (
                    "%d record(s) over %d raw runs, %d carrier(s), %d cited experiment(s)"
                    % (ev["in_raw"], len(ev["raw_runs"]), len(set(ev["carriers"])),
                       len(ev["indexed"])))
            else:
                s, why = "auditable", ("%d record(s) in raw/ over %d run(s), %d "
                                       "carrier(s)"
                                       % (ev["in_raw"], len(ev["raw_runs"]),
                                          len(set(ev["carriers"]))))
            obs[row["key"]] = (s, why, ev["resolved"])
        return obs

    # -- 7 -------------------------------------------------------------
    def limits(self):
        obs = {}
        for row, st, w in self.field_rows():
            if w > 8:
                continue
            ev = self.evidence(row)
            enc = 1 << w
            got = ev["n_actual_field_values"]
            hard = sum(ev["hard"].values())
            legal = sum(v for k, v in ev["outcomes"].items()
                        if k not in EI.HARD)
            if ev["records"] == 0:
                s, why = "no-data", self._nodata(ev)
            elif got < enc:
                s, why = "partial-sweep", ("%d of %d encodable values reached the "
                                           "hardware" % (got, enc))
            elif hard and legal:
                s, why = "limit-mapped", ("all %d encodable values dispatched; %d legal "
                                          "and %d rejected/hard outcome(s) -- the "
                                          "boundary was crossed" % (enc, legal, hard))
            else:
                s, why = "full-domain-swept", (
                    "all %d encodable values dispatched, but %s. Section 6: a nominal "
                    "size without excess-capacity behaviour is an incomplete result"
                    % (enc, "no value was rejected" if not hard
                       else "no value ran legally"))
            obs[row["key"]] = (s, why, ev["resolved"])
        return obs

    @staticmethod
    def _nodata(ev):
        if ev["unresolved"]:
            return "cited %s, which resolves to no directory" % ",".join(ev["unresolved"])
        if not ev["cited"]:
            return "no experiment cites this row"
        if ev["derived_records"]:
            return ("%d record(s) exist only outside raw/ (%s) -- derived artifacts, "
                    "not dispatches" % (ev["derived_records"],
                                        ",".join(ev["derived_only"][:3])))
        if ev["nonrecord_files"]:
            return ("cited raw holds %d non-record file(s) (.txt/.log/.hex) and 0 "
                    "machine-readable records: FORMAT-UNREADABLE, not absent"
                    % ev["nonrecord_files"])
        return "cited raw holds no record for this row under any keying"

    def notes(self):
        """Facts a reader needs before comparing a numerator to its denominator."""
        widths = [w for _r, _st, w in self.field_rows()]
        wide = sum(1 for w in widths if w > 16)
        n = {}
        n["geometry"] = [
            "%d of %d fields are wider than 16 bits. For those, `geometry-mapped` "
            "(every encodable value dispatched) is unreachable by construction -- "
            "2^24 is 16.7M dispatches -- so FIELD-SWEEP-PROTOCOL 3.3 prescribes a "
            "sampled set plus a dense per-byte sweep instead. They can reach "
            "`ledger-verified` and no further on this dashboard; that is a property "
            "of the ladder, not a gap in the evidence." % (wide, len(widths)),
        ]
        n["liveness"] = [
            "`records-no-control` is NOT a negative result about the hardware. Gate B: "
            "zero movement without a firing detection-power control is "
            "`carrier-undecidable`. These rows need a control arm, not a re-sweep.",
        ]
        n["semantics"] = [
            "A semantic check here is an explicit host prediction compared against the "
            "observation (`sem_match`/`oracle_match`, or a `predict` naming a known "
            "outcome). A liveness ladder prediction, free prose, and an oracle equal "
            "to the run's baseline are counted separately and are NOT semantic checks "
            "-- Gate C: \"A difference from baseline is not a semantic oracle.\"",
        ]
        n["recipe"] = [
            "The registry is whatever the corpus commits as "
            "`analysis/template_dependency.json` or `analysis/generated_recipe.json`. "
            "Today that is one file (EXP-0173), covering %d mnemonic(s). Every "
            "instruction absent from it scores `not-generated` because NO generated "
            "program containing it has been recorded -- which is a statement about the "
            "registry's coverage as much as about the hardware."
            % len(self.e.recipes()),
        ]
        n["target"] = [
            "`G16G-direct-only` is not a failure. Committed M4/G16G evidence stays "
            "valid on its own target and is not retracted; it simply does not close a "
            "row whose claimed target is G17P.",
        ]
        n["audit"] = [
            "`citation-resolves` means the directory, its raw/ and its authored probe "
            "all exist but no record for this row was found inside raw/ under any of "
            "the four keyings. For pre-EXP-0138 experiments that is usually "
            "FORMAT-UNREADABLE (.txt/.log/.hex), not absence -- the per-key reason "
            "string in dashboard_detail.json says which.",
        ]
        n["limits"] = [
            "Population is db.json fields of width <= 8. Section 6 also requires "
            "limits for finite RESOURCES -- base slots, texture selectors, register "
            "banks, scoreboards, queues, nesting stacks, descriptor tables. This "
            "corpus commits no machine-readable registry of those, so they are "
            "0 of 0 here: NOT scored zero, NOT counted as covered. Building that "
            "registry is the prerequisite for scoring them.",
        ]
        return n

    def score_all(self):
        return {
            "geometry": self.geometry(), "liveness": self.liveness(),
            "semantics": self.semantics(), "recipe": self.recipe(),
            "target": self.target(), "audit": self.audit(),
            "limits": self.limits(),
        }


# --------------------------------------------------------- the append-only ledger


def read_ledger(path=LEDGER):
    """High-water mark per (dashboard, key). A max over an append-only file."""
    hi = {}
    n = 0
    if not os.path.exists(path):
        return hi, n
    for line in open(path, errors="replace"):
        line = line.strip()
        if not line or line[0] != "{":
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        n += 1
        d, k = r.get("dashboard"), r.get("key")
        if d not in LADDERS or k is None:
            continue
        try:
            rk = rank(d, r.get("status"))
        except ValueError:
            continue
        cur = hi.get((d, k))
        if cur is None or rk > cur["rank"]:
            hi[(d, k)] = {"rank": rk, "status": r["status"], "run": r.get("run_id"),
                          "ts": r.get("ts"), "why": r.get("why"),
                          "evidence": r.get("evidence")}
    return hi, n


def _scores_digest(scores):
    """Content hash of a run's scored rows, ignoring timestamp and run id."""
    h = hashlib.sha256()
    for dash, obs in sorted(scores.items()):
        for key, (status, why, evid) in sorted(obs.items()):
            h.update(("%s|%s|%s|%s\n" % (dash, key, status, rank(dash, status))).encode())
    return h.hexdigest()


def append_ledger(scores, run_id, path=LEDGER, meta=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # The ledger is append-only BY DESIGN -- it is the monotonicity mechanism and
    # `attained` is a max over its lines. But it appended ~6,525 lines on EVERY
    # invocation, so merely INSPECTING the dashboards grew the evidence file: one
    # session added 39,630 lines and 34 MB without a single score changing.
    # Appending identical content adds no monotonic information, so skip it and
    # say so. A run whose scores DIFFER in any row still appends in full.
    digest = _scores_digest(scores)
    if os.path.exists(path):
        last = None
        with open(path) as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                d = (rec.get("meta") or {}).get("scores_digest")
                if d:
                    last = d
        if last == digest:
            print("ledger: scores identical to the last recorded run (%s) -- "
                  "nothing appended (inspection must not grow the evidence file)"
                  % digest[:12])
            return
    meta = dict(meta or {})
    meta["scores_digest"] = digest
    with open(path, "a") as fh:
        for dash, obs in sorted(scores.items()):
            for key, (status, why, evid) in sorted(obs.items()):
                fh.write(json.dumps({
                    "ts": ts, "run_id": run_id, "dashboard": dash, "key": key,
                    "status": status, "rank": rank(dash, status), "why": why,
                    "evidence": evid, "tool": "tools/agx-isa/dashboards.py",
                    "meta": meta or {},
                }, sort_keys=True) + "\n")


def combine(scores, hi, notes=None):
    """attained (high-water), current (this run), downgraded (scoped, not applied)."""
    out = {}
    for dash, obs in scores.items():
        ladder = LADDERS[dash]
        cur = collections.Counter()
        att = collections.Counter()
        downs = []
        for key, (status, why, _e) in obs.items():
            cur[status] += 1
            h = hi.get((dash, key))
            best = status
            if h and h["rank"] > rank(dash, status):
                best = h["status"]
                downs.append({"key": key, "attained": h["status"],
                              "attained_run": h["run"], "current": status,
                              "reason": why})
            att[best] += 1
        out[dash] = {
            "population": POPULATION[dash], "ladder": ladder,
            "notes": (notes or {}).get(dash, []),
            "denominator": len(obs),
            "current": {s: cur.get(s, 0) for s in ladder},
            "attained": {s: att.get(s, 0) for s in ladder},
            "downgraded": downs,
        }
    return out


# ------------------------------------------------------------------- reporting


def write_report(combined, run_id, outdir=REPORTS, index_note=""):
    os.makedirs(outdir, exist_ok=True)
    L = []
    L.append("# The seven dashboards — section 9 progress accounting\n")
    L.append("**Generated by `tools/agx-isa/dashboards.py`; do not hand-edit.**  \n"
             "Run id `%s`.%s\n" % (run_id, "  \n" + index_note if index_note else ""))
    L.append("Section 9 replaces the single completion number with seven dashboards, "
             "because one number absorbing six kinds of evidence read 79, then 41, 55, "
             "38, 37, 34, 33, 32 — and not one of those moves was a hardware "
             "discovery. **An experiment may advance one dashboard and leave the "
             "others unchanged. That is real progress.**\n")
    L.append("Three columns, always:\n")
    L.append("- **attained** — the high-water mark over the append-only ledger "
             "`ledger/dashboard_ledger.jsonl`. Monotonic *by construction*: the ledger "
             "is append-only and `attained` is a max over its lines, so no later run "
             "can lower it.\n"
             "- **current** — what this run re-derives from raw right now.\n"
             "- **downgraded** — keys where current < attained, each with a reason. "
             "Section 9: a downgrade is *reported and scoped*, never applied. "
             "A broken citation moves dashboard 6 and leaves 1, 2, 3, 5 and 7 alone.\n")
    L.append("Every figure below is a numerator over a stated denominator. Section 5: "
             "**never report only a percentage.** `no-data` is a reported bucket with "
             "a stated reason, not a silent zero.\n")

    L.append("## Summary — the seven, side by side\n")
    L.append("| # | dashboard | population | denominator | top rung (attained) | "
             "top rung (current) | has data (attained) | downgrades |")
    L.append("|---|---|---|---:|---|---|---|---:|")
    order = ["geometry", "liveness", "semantics", "recipe", "target", "audit", "limits"]
    for i, d in enumerate(order, 1):
        c = combined[d]
        top = c["ladder"][-1]
        bottom = c["ladder"][0]
        nodata_a = c["attained"][bottom]
        L.append("| %d | %s | %s | %d | %d/%d `%s` | %d/%d `%s` | %d/%d | %d |"
                 % (i, TITLES[d].split(". ", 1)[1], c["population"].split(",")[0],
                    c["denominator"], c["attained"][top], c["denominator"], top,
                    c["current"][top], c["denominator"], top,
                    c["denominator"] - nodata_a, c["denominator"],
                    len(c["downgraded"])))
    L.append("")
    L.append("The seven numbers are **not summable and not comparable**. A row can sit "
             "at `geometry-mapped` and `no-semantic-check` simultaneously; that is the "
             "state section 2 requires the axes to be able to express.\n")

    for i, d in enumerate(order, 1):
        c = combined[d]
        L.append("## %s\n" % TITLES[d])
        L.append("**Population:** %s.  \n**Denominator:** %d.\n"
                 % (c["population"], c["denominator"]))
        for nt in c.get("notes") or []:
            L.append("> %s\n" % nt)
        L.append("| rung | status | attained | current | of |")
        L.append("|---:|---|---:|---:|---:|")
        for rk, s in enumerate(c["ladder"]):
            L.append("| %d | `%s` | %d | %d | %d |"
                     % (rk, s, c["attained"][s], c["current"][s], c["denominator"]))
        L.append("")
        top = c["ladder"][-1]
        L.append("At or above the top rung: **%d of %d** attained (%.1f%%), "
                 "**%d of %d** current (%.1f%%).\n"
                 % (c["attained"][top], c["denominator"],
                    100.0 * c["attained"][top] / max(c["denominator"], 1),
                    c["current"][top], c["denominator"],
                    100.0 * c["current"][top] / max(c["denominator"], 1)))
        if c["downgraded"]:
            L.append("### Downgrades (reported and scoped, NOT applied)\n")
            L.append("| key | attained | attained in run | current | reason |")
            L.append("|---|---|---|---|---|")
            for x in c["downgraded"][:40]:
                L.append("| `%s` | %s | %s | %s | %s |"
                         % (x["key"], x["attained"], x["attained_run"], x["current"],
                            (x["reason"] or "")[:160].replace("|", "\\|")))
            L.append("")
        else:
            L.append("No key on this dashboard is below its high-water mark.\n")

    open(os.path.join(outdir, "dashboards.md"), "w").write("\n".join(L) + "\n")
    json.dump({"run_id": run_id, "dashboards": combined},
              open(os.path.join(outdir, "dashboards.json"), "w"), indent=1,
              default=str)


def write_detail(scores, outdir=REPORTS):
    """Per-key statuses, so a reader can check any single figure by hand."""
    json.dump({d: {k: {"status": s, "why": w, "evidence": e}
                   for k, (s, w, e) in obs.items()}
               for d, obs in scores.items()},
              open(os.path.join(outdir, "dashboard_detail.json"), "w"), indent=1,
              default=str)


# ------------------------------------------------------------------- self-test


def selftest():
    """The dashboards must not be able to reset themselves -- and must be able to move.

    A monotone counter that only ever rises is useless if it rises for free, and a
    dashboard that can be talked down is the defect section 9 exists to prevent. So
    both directions are asserted.
    """
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="dash-")
    ok = True

    def chk(name, cond):
        nonlocal ok
        print("%-4s %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            ok = False

    try:
        led = os.path.join(tmp, "ledger.jsonl")

        # A tiny synthetic score set, one dashboard, three keys.
        strong = {"geometry": {
            "a.x": ("geometry-mapped", "all 16 values", ["EXP-1"]),
            "a.y": ("ledger-verified", "Gate A holds", ["EXP-1"]),
            "a.z": ("no-data", "nobody looked", []),
        }}
        weak = {"geometry": {
            "a.x": ("no-data", "the citation broke", []),
            "a.y": ("no-data", "the citation broke", []),
            "a.z": ("no-data", "nobody looked", []),
        }}
        better = {"geometry": {
            "a.x": ("geometry-mapped", "all 16 values", ["EXP-1"]),
            "a.y": ("geometry-mapped", "all 16 values", ["EXP-2"]),
            "a.z": ("ledger-verified", "Gate A holds", ["EXP-2"]),
        }}

        append_ledger(strong, "run-1", led)
        hi, n = read_ledger(led)
        c1 = combine(strong, hi)["geometry"]
        chk("a first run records its statuses (3 keys on the ledger)", n == 3)
        chk("attained matches current on the first run",
            c1["attained"] == c1["current"]
            and c1["attained"]["geometry-mapped"] == 1)

        # The reset test. A later run that sees NOTHING must not lower `attained`.
        append_ledger(weak, "run-2", led)
        hi, n = read_ledger(led)
        c2 = combine(weak, hi)["geometry"]
        chk("a later empty run does NOT lower `attained` (the reset test)",
            c2["attained"]["geometry-mapped"] == 1
            and c2["attained"]["ledger-verified"] == 1)
        chk("...while `current` DOES fall, so the loss is visible",
            c2["current"]["no-data"] == 3
            and c2["current"]["geometry-mapped"] == 0)
        chk("...and both losses are reported as scoped downgrades, with reasons",
            len(c2["downgraded"]) == 2
            and all(x["reason"] for x in c2["downgraded"])
            and {x["key"] for x in c2["downgraded"]} == {"a.x", "a.y"})

        # The other direction. A dashboard that can only rise for free is useless.
        append_ledger(better, "run-3", led)
        hi, n = read_ledger(led)
        c3 = combine(better, hi)["geometry"]
        chk("a better run RAISES `attained` (the dashboard is not frozen)",
            c3["attained"]["geometry-mapped"] == 2
            and c3["attained"]["ledger-verified"] == 1
            and c3["attained"]["no-data"] == 0)
        chk("a better run clears the downgrade list", not c3["downgraded"])

        # A run whose statuses are all identical must add no downgrade and no rise.
        append_ledger(better, "run-4", led)
        hi, n = read_ledger(led)
        c4 = combine(better, hi)["geometry"]
        chk("a repeat run changes nothing in either direction",
            c4["attained"] == c3["attained"] and not c4["downgraded"])

        # The ledger really is append-only: every line of every run survives.
        lines = [l for l in open(led) if l.strip()]
        chk("the ledger is append-only (12 lines after 4 runs of 3 keys)",
            len(lines) == 12)
        runs = {json.loads(l)["run_id"] for l in lines}
        chk("every run's observations are still on the ledger",
            runs == {"run-1", "run-2", "run-3", "run-4"})

        # Cross-dashboard independence: section 9's central claim.
        two = {
            "geometry": {"a.x": ("geometry-mapped", "g", ["E"])},
            "semantics": {"a.x": ("semantically-mapped", "s", ["E"])},
        }
        two_led = os.path.join(tmp, "l2.jsonl")
        append_ledger(two, "r1", two_led)
        sem_corrected = {
            "geometry": {"a.x": ("geometry-mapped", "g", ["E"])},
            "semantics": {"a.x": ("no-semantic-check", "the model was refuted", [])},
        }
        append_ledger(sem_corrected, "r2", two_led)
        hi2, _ = read_ledger(two_led)
        cc = combine(sem_corrected, hi2)
        chk("a semantic correction leaves the GEOMETRY dashboard untouched",
            cc["geometry"]["current"]["geometry-mapped"] == 1
            and not cc["geometry"]["downgraded"])
        chk("...and is itself reported as a scoped semantic downgrade",
            len(cc["semantics"]["downgraded"]) == 1
            and cc["semantics"]["current"]["no-semantic-check"] == 1
            and cc["semantics"]["attained"]["semantically-mapped"] == 1)

        # A corrupt or foreign ledger line must be skipped, not crash or score.
        with open(two_led, "a") as fh:
            fh.write("not json\n")
            fh.write(json.dumps({"dashboard": "nope", "key": "a.x",
                                 "status": "invented"}) + "\n")
            fh.write(json.dumps({"dashboard": "geometry", "key": "a.x",
                                 "status": "invented-rung"}) + "\n")
        hi3, _ = read_ledger(two_led)
        chk("a corrupt or unknown ledger line is skipped, not scored",
            hi3[("geometry", "a.x")]["status"] == "geometry-mapped")

        # Every ladder must be strictly ordered and start at a no-data rung.
        lad_ok = all(len(set(v)) == len(v) and len(v) >= 2 for v in LADDERS.values())
        chk("all seven ladders are ordered and have no duplicate rungs", lad_ok)
        chk("all seven dashboards declare a population and a title",
            set(LADDERS) == set(POPULATION) == set(TITLES))
        print("--- section-2 axes cross-check (wired in from axes_sidecar.py) ---")
        chk("the axes cross-check self-tests clean in both directions",
            AX.selftest() == 0)

        print("\nDASHBOARD SELFTEST %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=LEDGER)
    # DEF-0212-2, second instance. The LEDGER is append-only by design -- that is
    # the monotonicity mechanism and appending to it is correct. The REPORTS
    # directory is not: defaulting there meant every run silently rewrote a
    # committed experiment's artifacts. Same fix as promotion_check.py: writing
    # reports is opt-in, the ledger still appends, and the summary always prints.
    ap.add_argument("--reports", default=os.path.join(ROOT, "work", "dashboard_reports"),
                    help="write the per-dashboard reports here. Defaults to a SCRATCH "
                         "path under work/, not into EXP-0209's committed reports/ -- "
                         "that default meant every run silently rewrote a committed "
                         "experiment's artifacts (DEF-0212-2, second instance). Pass "
                         "EXP-0209's path explicitly to regenerate them deliberately.")
    ap.add_argument("--labels", default=None)
    ap.add_argument("--index-dir", default=None)
    ap.add_argument("--no-append", action="store_true",
                    help="score and report without recording on the ledger")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    s = Scorer(index_dir=a.index_dir, labels=a.labels)
    scores = s.score_all()
    run_id = a.run_id or ("EXP-0209-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S"))
    idx = a.index_dir or EI.CACHE
    fps = sorted(os.path.basename(p) for p in
                 __import__("glob").glob(os.path.join(idx, "*.json")))
    def _sha(pth):
        try:
            return hashlib.sha256(open(pth, "rb").read()).hexdigest()[:16]
        except OSError:
            return "missing"
    lab = a.labels or os.path.join(HERE, "validation.json")
    note = ("Evidence index: %d experiment cache files under `%s`.  \n"
            "Inputs pinned: `db.json` sha256[:16] `%s`, `%s` sha256[:16] `%s`. "
            "Other agents may be writing the label sidecar concurrently, so the pin "
            "is what makes this run's figures reproducible."
            % (len(fps), os.path.relpath(idx, ROOT),
               _sha(os.path.join(HERE, "db.json")), os.path.relpath(lab, ROOT),
               _sha(lab)))
    if not a.no_append:
        append_ledger(scores, run_id, a.ledger,
                      meta={"index_files": len(fps),
                            "db_sha256": hashlib.sha256(
                                open(os.path.join(HERE, "db.json"), "rb").read()
                            ).hexdigest()[:16]})
    hi, nlines = read_ledger(a.ledger)
    combined = combine(scores, hi, s.notes())
    write_report(combined, run_id, a.reports, note)
    write_detail(scores, a.reports)
    axes, asrc, acounts = AX.collect(a.labels)
    acounts, aagree, ndis = AX.crosscheck(scores, axes, asrc, acounts,
                                          combined["geometry"]["denominator"],
                                          a.reports)

    print("run %s   ledger %s (%d lines)" % (run_id, os.path.relpath(a.ledger, ROOT),
                                             nlines))
    print()
    print("  %-42s %6s %6s %6s %8s" % ("dashboard (top rung)", "attn", "curr", "denom",
                                       "downgr"))
    for d in ["geometry", "liveness", "semantics", "recipe", "target", "audit",
              "limits"]:
        c = combined[d]
        top = c["ladder"][-1]
        print("  %-42s %6d %6d %6d %8d"
              % ("%s / %s" % (TITLES[d].split(". ", 1)[1][:26], top[:14]),
                 c["attained"][top], c["current"][top], c["denominator"],
                 len(c["downgraded"])))
    print()
    for d in ["geometry", "liveness", "semantics", "recipe", "target", "audit",
              "limits"]:
        c = combined[d]
        print("  %s" % TITLES[d])
        for s_ in c["ladder"]:
            print("      %-26s attained %5d / %d   current %5d / %d"
                  % (s_, c["attained"][s_], c["denominator"], c["current"][s_],
                     c["denominator"]))
    print()
    print("  section-2 `axes` sidecar census (absence is reported as absence)")
    for k, v in acounts.items():
        print("      %-52s %s" % (k, "file not present" if v is None else v))
    print("      %-52s %d of %d" % ("db.json fields with NO axes object",
                                    combined["geometry"]["denominator"] - len(axes),
                                    combined["geometry"]["denominator"]))
    print("      %-52s %d" % ("cross-check disagreements", ndis))
    for k in sorted(aagree):
        print("      %-52s %d" % ("  " + k, aagree[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
