#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""promotion_check.py -- the evidence-promotion gate (RE_EXPERIMENT_PROCESS_CORRECTIONS 8).

`validate_labels.py` keeps its job: schema and label consistency for
tools/agx-isa/validation.json. Section 8 says it "must not be used as the
evidence-promotion gate by itself", because it validates CITATIONS, not EVIDENCE --
it checks that a cited directory exists, never that the directory contains what the
claim says it contains.

This program OPENS THE CITED RAW AND DERIVED FILES (via evidence_index.py, which
re-derives per-(instruction, field) facts from raw under four independent keyings)
and REJECTS promotion when any of section 8's nine conditions is true:

  R1 EVIDENCE-MISSING        evidence path or authored input is missing
  R2 TARGET-MISMATCH         target does not match the claimed target
  R3 LEDGER                  actual-byte ledger missing, or requested and decoded
                             values disagree
  R4 RANGE-NOT-COVERED       distinct actual encodings do not cover the claimed range
  R5 SEMANTICS               semantic checks are zero, or do not cover the claimed
                             behaviour buckets
  R6 DETECTION-POWER         the carrier's detection-power control failed
  R7 REPETITION              required isolated repetitions or a second method missing
  R8 DONOR-FIELDS            copied donor fields remain in a claimed generated recipe
  R9 CASCADE                 fault/hang/limit claims not confirmed free of cascade
                             contamination

It emits SEPARATE geometry, liveness, semantics, recipe, target and audit reports.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not derive a single `N of 166 emittable` headline from field labels. Section 9
records why: one number absorbed six different kinds of evidence and consequently read
79, then 41, 55, 38, 37, 34, 33, 32 -- each move a re-scoring, not a hardware
discovery. The label is an INPUT to this program only as the CLAIM BEING TESTED; no
verdict here is computed from a label. `--selftest` asserts both properties: that a
row labelled `hardware-run` is rejected when its raw has no semantic checks, and that
no report contains a combined emittable count.

Verdict vocabulary (three-valued on purpose -- section 5 forbids silently scoring
zero where data does not exist):

  PASS          the raw meets the rule
  REJECT        the raw CONTRADICTS the rule (ledger disagreed, control failed)
  INSUFFICIENT  the raw does not contain what the rule needs (no ledger, 0 sem checks)
  N/A           the rule does not apply to this claim

PASS is the only verdict that permits promotion. REJECT and INSUFFICIENT are counted
and reported separately, because "we looked and it is wrong" and "nobody has measured
it" are different states and section 9 forbids collapsing them.

CLEAN ROOM: reads only this repository's own committed artifacts.

Usage:
    python3 tools/agx-isa/promotion_check.py --report-dir experiments/EXP-0209-dashboards/reports
    python3 tools/agx-isa/promotion_check.py --row falu2.opsel -v
    python3 tools/agx-isa/promotion_check.py --verdicts experiments/EXP-XXXX/analysis/field_verdicts.json
    python3 tools/agx-isa/promotion_check.py --selftest
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import evidence_index as EI  # noqa: E402

EMIT_GRADE = ("hardware-run", "isolated-byte-diff")

PASS, REJECT, INSUFFICIENT, NA = "PASS", "REJECT", "INSUFFICIENT", "N/A"
BLOCKING = (REJECT, INSUFFICIENT)

# Which rules each of the six reports owns. A rule may appear in one report only, so
# that "geometry is fine, semantics is not" stays readable as two facts.
REPORTS = {
    "geometry": ["R3", "R4"],
    "liveness": ["R6", "R9"],
    "semantics": ["R5"],
    "recipe": ["R8"],
    "target": ["R2"],
    "audit": ["R1", "R7"],
}
RULE_TITLE = {
    "R1": "evidence path and authored input exist",
    "R2": "target matches the claimed target",
    "R3": "actual-byte ledger present and requested == decoded",
    "R4": "distinct actual encodings cover the claimed range",
    "R5": "semantic checks nonzero and covering the behaviour buckets",
    "R6": "the carrier's detection-power control fired",
    "R7": "isolated repetitions and a second method",
    "R8": "no copied donor field remains in a claimed generated recipe",
    "R9": "fault/hang/limit claims free of cascade contamination",
}


# ------------------------------------------------------------------- claim rows


def claims_from_validation(path=None):
    val = json.load(open(path or os.path.join(HERE, "validation.json")))
    rows = []
    for m, entry in sorted(val["instructions"].items()):
        for f, r in sorted(entry.items()):
            if not isinstance(r, dict):
                continue
            rows.append({
                "key": "%s.%s" % (m, f),
                "mnemonic": m,
                "field": None if f == "_instruction" else f,
                "label": r.get("label"),
                "range": r.get("range"),
                "target": r.get("target"),
                "evidence": r.get("evidence") or [],
                "note": r.get("note") or "",
                "axes": r.get("axes"),
                "values_dispatched": r.get("values_dispatched"),
                "distinct_bytes": r.get("distinct_bytes"),
                "encodable_range": r.get("encodable_range"),
                "start": r.get("start"),
                "width": r.get("width"),
            })
    return rows


def claims_from_verdicts(paths):
    rows = []
    for p in paths:
        doc = json.load(open(p))
        src = os.path.basename(os.path.dirname(os.path.dirname(p)))
        for key, v in doc.items():
            if key.startswith("_") or "." not in key or not isinstance(v, dict):
                continue
            m, f = key.split(".", 1)
            rows.append({
                "key": key, "mnemonic": m,
                "field": None if f == "_instruction" else f,
                "label": v.get("label"), "range": v.get("range"),
                "target": v.get("target"), "evidence": v.get("evidence") or [src],
                "note": v.get("note") or "", "axes": v.get("axes"),
                "values_dispatched": v.get("values_dispatched"),
                "distinct_bytes": v.get("distinct_bytes"),
                "encodable_range": v.get("encodable_range"),
                "start": v.get("start"), "width": v.get("width"),
            })
    return rows


# ------------------------------------------------------- claimed-range parsing

_RX_SPAN = re.compile(r"(\d+)\s*\.\.\s*(\d+)")
_RX_ALL = re.compile(r"all\s+(\d+)\s+values")
_RX_NVAL = re.compile(r"(\d+)\s+(?:distinct\s+)?values?\b")


def claimed_cardinality(row):
    """How many distinct values the claim says were exercised.

    Returns (n, how). `how` is "unparsable" when the prose does not state one --
    reported as such rather than scored as zero (section 5: never report only a
    percentage, and never invent a denominator).
    """
    if isinstance(row.get("values_dispatched"), int):
        return row["values_dispatched"], "values_dispatched"
    rng = row.get("range") or ""
    mo = _RX_ALL.search(rng)
    if mo:
        return int(mo.group(1)), "range:all-N-values"
    mo = _RX_SPAN.search(rng)
    if mo:
        a, b = int(mo.group(1)), int(mo.group(2))
        if b >= a:
            return b - a + 1, "range:A..B"
    mo = _RX_NVAL.search(rng)
    if mo:
        return int(mo.group(1)), "range:N-values"
    if re.fullmatch(r"\s*[\d\s,]+\s*", rng or "") and rng.strip():
        return len({x for x in re.split(r"[,\s]+", rng.strip()) if x}), "range:list"
    return None, "unparsable"


# ------------------------------------------------------------- evidence loading


class Evidence(object):
    """All committed facts the cited experiments hold about one claim row."""

    def __init__(self, index_dir=None, root=None):
        self.index_dir = index_dir or EI.CACHE
        self.root = root or ROOT
        self.exps = os.path.join(self.root, "experiments")
        self._docs = {}
        self._recipes = None
        try:
            self._spec = EI.load_db()
        except Exception:
            self._spec = {}

    # -- directory resolution (the project validator's own glob rule) -------
    def resolve(self, slug):
        base = slug.split("/")[0]
        return sorted(os.path.basename(d)
                      for d in glob.glob(os.path.join(self.exps, base + "*"))
                      if os.path.isdir(d))

    def doc(self, name):
        if name not in self._docs:
            p = os.path.join(self.index_dir, name + ".json")
            try:
                self._docs[name] = json.load(open(p))
            except Exception:
                self._docs[name] = None
        return self._docs[name]

    # -- authored input ----------------------------------------------------
    def authored_input(self, name):
        """Did the experiment commit the probe it ran?

        Section 4 requires the authored inputs to be frozen with the raw. A raw tree
        with no committed probe cannot be re-derived by anyone, so a promotion
        resting on it is not auditable.
        """
        d = os.path.join(self.exps, name)
        for sub in ("kernels", "harness", "probe", "probes", "src", "shaders",
                    "analysis"):
            if os.path.isdir(os.path.join(d, sub)) and os.listdir(
                    os.path.join(d, sub)):
                return True
        return bool(glob.glob(os.path.join(d, "*.metal")) or
                    glob.glob(os.path.join(d, "*.py")))

    # -- the generated-recipe registry (EXP-0173 and any successor) ---------
    def recipes(self):
        if self._recipes is None:
            reg = {}
            for p in sorted(glob.glob(os.path.join(
                    self.exps, "*", "analysis", "template_dependency.json"))) + \
                    sorted(glob.glob(os.path.join(
                        self.exps, "*", "analysis", "generated_recipe.json"))):
                try:
                    doc = json.load(open(p))
                except Exception:
                    continue
                src = os.path.basename(os.path.dirname(os.path.dirname(p)))
                for rec in (doc.get("instructions") or []):
                    if isinstance(rec, dict) and rec.get("mnemonic"):
                        rec = dict(rec)
                        rec["_source"] = src
                        reg[rec["mnemonic"]] = rec
            self._recipes = reg
        return self._recipes

    # -- the aggregate cell ------------------------------------------------
    def gather(self, row):
        """Merge every cited experiment's cell for this row. Never a label read."""
        agg = {
            "cited": [], "resolved": [], "unresolved": [], "indexed": [],
            "no_raw": [], "no_authored": [], "quarantined": [],
            "records": 0, "in_raw": 0,
            "n_req_values": 0, "n_actual_bytes": 0, "n_actual_field_values": 0,
            "ledger_records": 0, "ledger_decoded": 0, "ledger_agree": 0,
            "ledger_disagree": 0, "ledger_examples": [],
            "byte_ledger_records": 0, "byte_ledger_agree": 0,
            "byte_ledger_disagree": 0,
            "sem_checks": 0, "sem_true": 0, "sem_false": 0,
            "sem_buckets": collections.Counter(),
            "baseline_oracle": 0, "host_oracle": 0,
            "liveness_predictions": 0, "prose_predictions": 0,
            "outcomes": collections.Counter(), "hard": collections.Counter(),
            "contamination": collections.Counter(),
            "V": 0, "n_oracle_digests": 0,
            "raw_runs": set(), "targets": collections.Counter(),
            "carriers": set(), "arms": set(), "probes": set(),
            "controls": {}, "control_fired": None,
            "nonrecord_files": 0, "record_files": 0,
            "keying": collections.Counter(),
            "derived_only": [],       # cited experiments whose only records for this
                                      # row live outside raw/ (analysis/ or work/)
            "derived_records": 0,
        }
        key = row["key"]
        for ev in row.get("evidence") or []:
            if not isinstance(ev, str):
                continue
            agg["cited"].append(ev)
            dirs = self.resolve(ev)
            if not dirs:
                agg["unresolved"].append(ev)
                continue
            for d in dirs:
                agg["resolved"].append(d)
                doc = self.doc(d)
                if doc is None:
                    continue
                agg["indexed"].append(d)
                m = doc["_meta"]
                if not m.get("has_raw"):
                    agg["no_raw"].append(d)
                if m.get("quarantined"):
                    agg["quarantined"].append(d)
                if not self.authored_input(d):
                    agg["no_authored"].append(d)
                agg["nonrecord_files"] += m.get("nonrecord_files", 0)
                agg["record_files"] += m.get("record_files", 0)
                cell = doc["cells"].get(key)
                if cell:
                    self._merge(agg, cell)
                dcell = (doc.get("derived_cells") or {}).get(key)
                if dcell:
                    agg["derived_records"] += dcell.get("records", 0)
                    if not cell:
                        agg["derived_only"].append(d)
                # Gate B controls are per instruction, not per field.
                for ck, cc in doc["controls"].items():
                    if ck.split(".")[0] == row["mnemonic"]:
                        agg["controls"][d + "/" + ck] = {
                            "records": cc["records"], "V": cc["V"],
                            "outcomes": cc["outcomes"], "hard": cc["hard"],
                            "n_actual_bytes": cc["n_actual_bytes"],
                        }
        agg["raw_runs"] = sorted(agg["raw_runs"])
        for s in ("carriers", "arms", "probes"):
            agg[s] = sorted(agg[s])[:32]
        for c in ("sem_buckets", "outcomes", "hard", "contamination", "targets",
                  "keying"):
            agg[c] = dict(agg[c])
        # Did any control fire? A control that never moved has no detection power,
        # so zero movement in the swept field is not evidence of inertness.
        if agg["controls"]:
            fired = [k for k, c in agg["controls"].items()
                     if c["V"] >= 2 or c["n_actual_bytes"] >= 2]
            agg["control_fired"] = bool(fired)
            agg["controls_fired"] = fired
        return agg

    @staticmethod
    def _merge(agg, cell):
        for k in ("records", "in_raw", "ledger_records", "ledger_decoded",
                  "ledger_agree", "ledger_disagree", "byte_ledger_records",
                  "byte_ledger_agree", "byte_ledger_disagree",
                  "sem_checks", "sem_true",
                  "sem_false", "baseline_oracle", "host_oracle",
                  "liveness_predictions", "prose_predictions"):
            agg[k] += cell.get(k, 0)
        for k in ("n_req_values", "n_actual_bytes", "n_actual_field_values", "V",
                  "n_oracle_digests"):
            agg[k] = max(agg[k], cell.get(k, 0))
        for k in ("sem_buckets", "outcomes", "hard", "contamination", "targets",
                  "keying"):
            agg[k].update(cell.get(k, {}) or {})
        agg["raw_runs"].update((cell.get("raw_runs") or {}).keys())
        for a, b in (("carriers", "carriers"), ("arms", "arms"),
                     ("probes", "probes")):
            agg[a].update((cell.get(b) or {}).keys())
        agg["ledger_examples"].extend(cell.get("ledger_examples") or [])


# ------------------------------------------------------------------- the rules


def rule_R1(row, ev, e):
    """evidence path or authored input is missing"""
    if not row.get("evidence"):
        if row.get("label") == "untested":
            return NA, "untested with no citation: nothing is being promoted"
        return INSUFFICIENT, "label %r carries no evidence citation" % row.get("label")
    bad = []
    if ev["unresolved"]:
        bad.append("citation(s) resolve to no directory: %s" % ", ".join(ev["unresolved"]))
    if ev["no_raw"]:
        bad.append("cited experiment(s) have no raw/: %s" % ", ".join(ev["no_raw"]))
    if ev["no_authored"]:
        bad.append("cited experiment(s) commit no authored probe: %s"
                   % ", ".join(ev["no_authored"]))
    if ev["quarantined"]:
        bad.append("cited experiment(s) are QUARANTINED: %s" % ", ".join(ev["quarantined"]))
    if bad:
        return REJECT, "; ".join(bad)
    return PASS, "%d citation(s) resolve, raw and authored input present" % len(ev["resolved"])


def rule_R2(row, ev, e):
    """target does not match the claimed target"""
    claimed = (row.get("target") or "").strip()
    if not claimed:
        return INSUFFICIENT, "no target claimed"
    want = set()
    for part in re.split(r"[+/,]", claimed):
        p = part.strip().upper()
        if p in ("A18", "G17P"):
            want.add("G17P")
        elif p in ("M4", "G16G"):
            want.add("G16G")
        elif p in ("M5", "G17G"):
            want.add("M5")
    if not want:
        return INSUFFICIENT, "target %r is not a recognised silicon name" % claimed
    seen = set(ev["targets"])
    if not seen:
        runs = ev["raw_runs"]
        if not runs:
            return INSUFFICIENT, ("no raw run directory names a target; claim %s is "
                                  "not directly evidenced" % claimed)
        return INSUFFICIENT, ("raw run dirs %s name no target; claim %s is not "
                              "directly evidenced" % (",".join(runs[:4]), claimed))
    missing = want - seen
    if missing:
        return REJECT, ("claims %s but the cited raw ran on %s -- %s has no direct "
                        "evidence here" % (claimed, ",".join(sorted(seen)),
                                           ",".join(sorted(missing))))
    return PASS, "claimed %s, raw ran on %s" % (claimed, ",".join(sorted(seen)))


def _field_width(row, e):
    """The field's real width: db.json first, the claim row only as a fallback."""
    sp = (getattr(e, "_spec", {}) or {}).get(row["mnemonic"]) or {}
    span = (sp.get("fields") or {}).get(row["field"])
    if span:
        return span[1]
    return row.get("width")


def rule_R3(row, ev, e):
    """actual-byte ledger is missing, or requested and decoded values disagree"""
    if row["field"] is None:
        return NA, "instruction-level row: no single field to decode"
    if ev["ledger_disagree"] or ev["byte_ledger_disagree"]:
        exs = ev["ledger_examples"][:2]
        which = []
        if ev["ledger_disagree"]:
            which.append("%d field-keyed" % ev["ledger_disagree"])
        if ev["byte_ledger_disagree"]:
            which.append("%d byte-keyed" % ev["byte_ledger_disagree"])
        width = _field_width(row, e)
        over = [x for x in exs if isinstance(width, int)
                and isinstance(x.get("requested"), int)
                and x["requested"] >= (1 << width)]
        if over:
            kind = ("the requested values run past this field's %d-bit encodable "
                    "range, so `value` is a byte- or program-level intent: the "
                    "ledger does NOT establish that the FIELD took it" % width)
        else:
            kind = ("either the assembler could not place the requested value (the "
                    "DEF-0166 signature) or `value` names a byte rather than this "
                    "field -- both leave Gate A unmet, and the raw does not "
                    "distinguish them")
        return REJECT, ("%s record(s) where the requested value != the value decoded "
                        "from the ACTUAL dispatched bytes; %s (e.g. %s)"
                        % (" + ".join(which), kind,
                           "; ".join("[%s] req=%s bytes=%s decoded=%s"
                                     % (x.get("keying"), x["requested"],
                                        x["actual_bytes"], x["decoded"])
                                     for x in exs)))
    if ev["ledger_decoded"] == 0:
        why = ("no records at all under any keying" if ev["records"] == 0
               else "%d record(s) but none carried actual instruction bytes"
                    % ev["records"])
        if ev["records"] == 0 and ev["derived_records"]:
            why += ("; %d record(s) exist but only OUTSIDE raw/ (%s) -- derived "
                    "artifacts are not dispatches"
                    % (ev["derived_records"], ",".join(ev["derived_only"][:3])))
        if ev["records"] == 0 and ev["nonrecord_files"]:
            why += ("; evidence is in %d non-record file(s) (.txt/.log/.hex) -- "
                    "format-unreadable, not absent" % ev["nonrecord_files"])
        return INSUFFICIENT, "no actual-byte ledger: " + why
    if ev["ledger_agree"] == 0 and ev["byte_ledger_agree"] == 0:
        return INSUFFICIENT, ("%d record(s) carried actual bytes and %d decoded, but "
                              "NONE stated a requested value to compare against -- "
                              "bytes without a caller intent are not a Gate A ledger"
                              % (ev["ledger_records"], ev["ledger_decoded"]))
    return PASS, ("%d/%d records decoded; field-keyed %d agree / 0 disagree; "
                  "byte-keyed %d agree / 0 disagree"
                  % (ev["ledger_decoded"], ev["ledger_records"], ev["ledger_agree"],
                     ev["byte_ledger_agree"]))


def rule_R4(row, ev, e):
    """distinct actual encodings do not cover the claimed range"""
    if row["field"] is None:
        return NA, "instruction-level row: no field range claimed"
    want, how = claimed_cardinality(row)
    got = ev["n_actual_field_values"]
    if want is None:
        return INSUFFICIENT, ("claimed range %r states no cardinality (%s); cannot "
                              "check coverage. Actual distinct encodings seen: %d"
                              % (row.get("range"), how, got))
    if got == 0:
        return INSUFFICIENT, ("claim covers %d value(s) (%s) but 0 distinct actual "
                              "encodings were recovered from raw" % (want, how))
    if got < want:
        return REJECT, ("claim covers %d value(s) (%s) but only %d distinct actual "
                        "encodings reached the hardware -- the DEF-0166-1 signature"
                        % (want, how, got))
    return PASS, "%d distinct actual encodings >= %d claimed (%s)" % (got, want, how)


def rule_R5(row, ev, e):
    """semantic checks are zero, or do not cover the claimed behaviour buckets"""
    label = row.get("label")
    if label not in EMIT_GRADE:
        return NA, "label %r makes no semantic claim" % label
    if ev["sem_checks"] == 0:
        extra = []
        if ev["liveness_predictions"]:
            extra.append("%d liveness ladder prediction(s)" % ev["liveness_predictions"])
        if ev["prose_predictions"]:
            extra.append("%d free-prose prediction(s)" % ev["prose_predictions"])
        if ev["baseline_oracle"]:
            extra.append("%d baseline-comparison oracle(s)" % ev["baseline_oracle"])
        return INSUFFICIENT, ("0 semantic checks in the cited raw%s. Section 2: "
                              "`sem_checked == 0` can never produce `hardware-run`"
                              % (" (found instead: " + ", ".join(extra) + ")"
                                 if extra else ""))
    nb = len(ev["sem_buckets"])
    if nb < 2:
        return REJECT, ("%d semantic check(s) but they cover only %d behaviour "
                        "bucket(s) (%s). Gate C requires the predictor to distinguish "
                        "correct / coherent-other / silent / fault / measurement-failure"
                        % (ev["sem_checks"], nb, ",".join(ev["sem_buckets"]) or "none"))
    if ev["n_oracle_digests"] <= 1 and ev["sem_checks"]:
        return REJECT, ("%d semantic check(s) over %d bucket(s), but the oracle took "
                        "ONE value across the sweep -- a constant oracle predicts the "
                        "instruction's effect, not the field's"
                        % (ev["sem_checks"], nb))
    return PASS, ("%d semantic checks (%d matched) over %d buckets: %s"
                  % (ev["sem_checks"], ev["sem_true"], nb,
                     ",".join("%s=%d" % kv for kv in sorted(ev["sem_buckets"].items()))))


def rule_R6(row, ev, e):
    """the carrier's detection-power control failed"""
    label = row.get("label")
    inert = re.search(r"\binert\b|never moved|0 observations moved|no movement",
                      row.get("note") or "", re.I)
    if label not in EMIT_GRADE and not inert:
        return NA, "no liveness or inertness claim to defend"
    if not ev["controls"]:
        return INSUFFICIENT, ("no detection-power control found in the cited raw. "
                              "Gate B: zero movement without a firing control is "
                              "`carrier-undecidable`, not inertness")
    if ev["control_fired"] is False:
        return REJECT, ("%d control arm(s) present and NONE moved (V<2 and <2 distinct "
                        "encodings) -- the carrier could not have shown the effect "
                        "either way" % len(ev["controls"]))
    return PASS, ("%d control arm(s), %d fired"
                  % (len(ev["controls"]), len(ev.get("controls_fired") or [])))


def rule_R7(row, ev, e):
    """required isolated repetitions or a second method are missing"""
    if row.get("label") not in EMIT_GRADE:
        return NA, "label %r is not an emitter-grade promotion" % row.get("label")
    runs = ev["raw_runs"]
    if len(runs) < 2:
        return INSUFFICIENT, ("%d raw run director%s (%s). Gate E requires two clean "
                              "runs in reversed or shuffled case order"
                              % (len(runs), "y" if len(runs) == 1 else "ies",
                                 ",".join(runs) or "none"))
    methods = len(set(ev["carriers"])) + (1 if len(ev["indexed"]) > 1 else 0)
    if len(set(ev["carriers"])) < 2 and len(ev["indexed"]) < 2:
        return REJECT, ("%d raw runs but ONE carrier (%s) and ONE cited experiment. "
                        "Phase 5: two carriers sharing the observation path count as "
                        "one method" % (len(runs), ",".join(ev["carriers"]) or "unnamed"))
    return PASS, ("%d raw runs (%s), %d carrier(s), %d cited experiment(s)"
                  % (len(runs), ",".join(runs[:4]), len(set(ev["carriers"])),
                     len(ev["indexed"])))


def rule_R8(row, ev, e):
    """copied donor fields remain in a claimed generated recipe"""
    reg = e.recipes()
    rec = reg.get(row["mnemonic"])
    claims_generated = row.get("label") in EMIT_GRADE
    if not claims_generated:
        return NA, "label %r claims no generated recipe" % row.get("label")
    if rec is None:
        return INSUFFICIENT, ("no generated-recipe record for %s in any committed "
                              "analysis/template_dependency.json or "
                              "analysis/generated_recipe.json" % row["mnemonic"])
    donors = rec.get("donor_fields") or {}
    if not rec.get("in_generated_corpus"):
        return INSUFFICIENT, ("%s: %s -- no generated program containing this "
                              "instruction has been executed (source %s)"
                              % (row["mnemonic"], rec.get("verdict"), rec.get("_source")))
    if row["field"] and row["field"] in donors:
        return REJECT, ("field %s is still supplied by a COPIED DONOR in the generated "
                        "program (%s)" % (row["field"], rec.get("_source")))
    if donors and row["field"] is None:
        return REJECT, ("%d field(s) of %s are still donor-supplied: %s (%s)"
                        % (len(donors), row["mnemonic"], ",".join(sorted(donors)),
                           rec.get("_source")))
    return PASS, "%s: %s, no donor field for this row (%s)" % (
        row["mnemonic"], rec.get("verdict"), rec.get("_source"))


def rule_R9(row, ev, e):
    """fault/hang/limit claims were not confirmed free of cascade contamination"""
    note = (row.get("note") or "") + " " + (row.get("range") or "")
    axes = row.get("axes") or {}
    hazard = str(axes.get("hazard") or "")
    claims_hard = bool(re.search(r"\bfault|hang|wedge|overflow|limit|reject", note, re.I)
                       or re.search(r"fault|hang|no_draw", hazard, re.I))
    observed_hard = sum(ev["hard"].values())
    if not claims_hard and not observed_hard:
        return NA, "no fault/hang/limit claim and no hard outcome in the raw"
    contam = ev["contamination"]
    bad = {k: v for k, v in contam.items() if v}
    if bad:
        return REJECT, ("hard outcomes present (%s) with cascade/contamination markers "
                        "in the SAME cited raw: %s. Gate E: a malformed runner response "
                        "is `measurement_failure`, never a hardware outcome"
                        % (",".join("%s=%d" % kv for kv in sorted(ev["hard"].items()))
                           or "none", ",".join("%s=%d" % kv for kv in sorted(bad.items()))))
    if claims_hard and len(ev["raw_runs"]) < 2:
        return INSUFFICIENT, ("a fault/hang/limit claim confirmed in %d run(s). Gate E "
                              "requires such claims to be repeated in isolation"
                              % len(ev["raw_runs"]))
    if observed_hard and not claims_hard:
        return INSUFFICIENT, ("%d hard outcome(s) in the raw (%s) that the claim does "
                              "not mention -- unclassified, so not confirmed free of "
                              "cascade contamination"
                              % (observed_hard,
                                 ",".join("%s=%d" % kv for kv in sorted(ev["hard"].items()))))
    return PASS, ("hard outcomes %s repeated across %d runs with no victim/sentinel/"
                  "restart markers"
                  % (",".join("%s=%d" % kv for kv in sorted(ev["hard"].items())) or "none",
                     len(ev["raw_runs"])))


RULES = [("R1", rule_R1), ("R2", rule_R2), ("R3", rule_R3), ("R4", rule_R4),
         ("R5", rule_R5), ("R6", rule_R6), ("R7", rule_R7), ("R8", rule_R8),
         ("R9", rule_R9)]


def check_row(row, e):
    ev = e.gather(row)
    out = {"key": row["key"], "label": row.get("label"), "target": row.get("target"),
           "range": row.get("range"), "evidence": row.get("evidence"),
           "facts": {k: ev[k] for k in
                     ("records", "in_raw", "n_req_values", "n_actual_bytes",
                      "n_actual_field_values", "ledger_records", "ledger_decoded",
                      "ledger_agree", "ledger_disagree", "byte_ledger_records",
                      "byte_ledger_agree", "byte_ledger_disagree",
                      "sem_checks", "sem_buckets",
                      "baseline_oracle", "host_oracle", "V", "n_oracle_digests",
                      "raw_runs", "targets", "carriers", "outcomes", "hard",
                      "contamination", "keying", "nonrecord_files", "record_files",
                      "unresolved", "no_raw", "no_authored", "quarantined",
                      "control_fired", "derived_only", "derived_records")},
           "rules": {}}
    for code, fn in RULES:
        v, why = fn(row, ev, e)
        out["rules"][code] = {"verdict": v, "why": why}
    out["blocking"] = sorted(c for c, r in out["rules"].items()
                             if r["verdict"] in BLOCKING)
    out["promotable"] = not out["blocking"]
    for name, codes in REPORTS.items():
        vs = [out["rules"][c]["verdict"] for c in codes]
        out.setdefault("axis", {})[name] = (
            REJECT if REJECT in vs else
            INSUFFICIENT if INSUFFICIENT in vs else
            PASS if PASS in vs else NA)
    return out


# ------------------------------------------------------------------- reporting


def write_reports(results, outdir, rows_source):
    os.makedirs(outdir, exist_ok=True)
    n = len(results)
    for name, codes in sorted(REPORTS.items()):
        lines = []
        lines.append("# Promotion checker — %s report\n" % name)
        lines.append("**Generated by `tools/agx-isa/promotion_check.py`; do not "
                     "hand-edit.**  \nSource of claims: `%s`  \nRules in this report: "
                     "%s\n" % (rows_source, ", ".join("`%s` (%s)" % (c, RULE_TITLE[c])
                                                      for c in codes)))
        lines.append("This report is one of six. Section 8 requires geometry, "
                     "liveness, semantics, recipe, target and audit to be reported "
                     "SEPARATELY, and forbids deriving a single `N of 166 emittable` "
                     "headline from field labels. No number below is computed from a "
                     "label; every one is re-derived from raw.\n")
        for c in codes:
            tally = collections.Counter(r["rules"][c]["verdict"] for r in results)
            lines.append("## `%s` — %s\n" % (c, RULE_TITLE[c]))
            lines.append("| verdict | rows | of | meaning |")
            lines.append("|---|---:|---:|---|")
            for v, meaning in ((PASS, "the raw meets the rule"),
                               (REJECT, "the raw CONTRADICTS the rule"),
                               (INSUFFICIENT, "the raw lacks what the rule needs"),
                               (NA, "the rule does not apply to this claim")):
                lines.append("| `%s` | %d | %d | %s |" % (v, tally.get(v, 0), n, meaning))
            lines.append("")
            for v in (REJECT, INSUFFICIENT):
                sel = [r for r in results if r["rules"][c]["verdict"] == v]
                if not sel:
                    continue
                reasons = collections.Counter(
                    re.sub(r"\d+", "N", r["rules"][c]["why"].split(".")[0].split(" -- ")[0])[:110]
                    for r in sel)
                lines.append("### `%s` — %d row(s), by reason\n" % (v, len(sel)))
                lines.append("| rows | reason (numbers elided) |")
                lines.append("|---:|---|")
                for why, k in reasons.most_common(20):
                    lines.append("| %d | %s |" % (k, why))
                lines.append("")
                lines.append("<details><summary>first 60 rows</summary>\n")
                lines.append("| row | label | target | why |")
                lines.append("|---|---|---|---|")
                for r in sel[:60]:
                    lines.append("| `%s` | %s | %s | %s |" % (
                        r["key"], r["label"], r["target"],
                        r["rules"][c]["why"].replace("|", "\\|")[:220]))
                lines.append("\n</details>\n")
        open(os.path.join(outdir, "%s.md" % name), "w").write("\n".join(lines) + "\n")

    # machine-readable, one row per claim
    json.dump({"_source": rows_source, "_rows": n,
               "_note": "No aggregate emittability count is derived here; see "
                        "RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 8.",
               "rows": results},
              open(os.path.join(outdir, "promotion_rows.json"), "w"),
              indent=1, default=str)

    # the cross-axis summary. Per AXIS, never one number.
    lines = ["# Promotion checker — axis summary\n",
             "**Generated by `tools/agx-isa/promotion_check.py`; do not hand-edit.**\n",
             "Section 8: *\"It must not derive a single `N of 166 emittable` headline "
             "from field labels.\"* This table is per AXIS and per VERDICT. Reading a "
             "single number off it is the failure mode it exists to prevent — and the "
             "numbers are not summable, because a row can be `PASS` on geometry and "
             "`INSUFFICIENT` on semantics at the same time.\n",
             "| axis | PASS | REJECT | INSUFFICIENT | N/A | rows |",
             "|---|---:|---:|---:|---:|---:|"]
    for name in sorted(REPORTS):
        t = collections.Counter(r["axis"][name] for r in results)
        lines.append("| %s | %d | %d | %d | %d | %d |"
                     % (name, t.get(PASS, 0), t.get(REJECT, 0),
                        t.get(INSUFFICIENT, 0), t.get(NA, 0), n))
    lines.append("")
    lines.append("## Rows that clear EVERY rule that applies to them\n")
    ok = [r for r in results if r["promotable"]]
    lines.append("%d of %d claim rows have no blocking rule. This is not an "
                 "emittability count: it is a count of CLAIM ROWS whose cited raw "
                 "survives all nine section-8 conditions, and a row can be here "
                 "because most rules returned `N/A` for it.\n" % (len(ok), n))
    lines.append("| row | label | target | rules that returned PASS |")
    lines.append("|---|---|---|---|")
    for r in ok[:200]:
        p = [c for c, x in sorted(r["rules"].items()) if x["verdict"] == PASS]
        lines.append("| `%s` | %s | %s | %s |" % (r["key"], r["label"], r["target"],
                                                  ", ".join(p) or "(none — all N/A)"))
    open(os.path.join(outdir, "promotion_summary.md"), "w").write("\n".join(lines) + "\n")
    return outdir


# ------------------------------------------------------------------- self-test


def _fixture(tmp):
    """A synthetic corpus in which each gate can be made to fire, one at a time.

    Every gate below is exercised in BOTH directions. This corpus produced thirteen
    checks that could not come out the other way; a gate proven only to refuse is as
    broken as one proven only to accept, so the last case is a well-formed claim that
    MUST be accepted.
    """
    exps = os.path.join(tmp, "experiments")
    idx = os.path.join(tmp, "index")
    os.makedirs(idx, exist_ok=True)
    spec = {"tst": {"length": 2, "match": [], "emitter_role": None,
                    "fields": {"f": (4, 4)}}}
    ix = EI.Indexer(spec)

    def mk(name, records, runs=("g17p_run01", "g17p_run02"), authored=True,
           has_raw=True, quarantined=False, controls="moving"):
        d = os.path.join(exps, name)
        os.makedirs(os.path.join(d, "kernels" if authored else "notes"), exist_ok=True)
        open(os.path.join(d, ("kernels" if authored else "notes"), "k.metal"), "w").write("//")
        if has_raw:
            os.makedirs(os.path.join(d, "raw"), exist_ok=True)
        if quarantined:
            open(os.path.join(d, "QUARANTINE.md"), "w").write("q")
        cells = collections.defaultdict(EI._new_cell)
        ctrl = collections.defaultdict(EI._new_cell)
        meta = {"instr_names_seen": collections.Counter(),
                "field_names_seen": collections.Counter(),
                "instr_records": collections.Counter(), "group_strings": set()}
        for run in runs:
            for rec in records:
                r = dict(rec)
                r["_in_raw"] = True
                ix.handle(r, cells, ctrl, meta, ("raw/%s/s.jsonl" % run, 1), run,
                          EI._target_of_run(run), in_raw=True)
            if controls:
                # "moving": the ladder produces two distinct payloads and two
                # distinct encodings -- the carrier demonstrably has detection power.
                # "dead": the ladder arm is PRESENT but never moves, which is the
                # EXP-0155 samp_extra failure mode: zero movement in the swept field
                # then says nothing either way.
                pairs = ((0, "0901"), (1, "1901")) if controls == "moving" \
                    else ((0, "0901"), (0, "0901"))
                for v, byt in pairs:
                    r = {"instr": "tst", "field": "__ladder_L_f", "value": v,
                         "bytes": byt, "outcome": "ok", "observed": {"z": 0},
                         "carrier": "C1", "_in_raw": True}
                    ix.handle(r, cells, ctrl, meta, ("raw/%s/s.jsonl" % run, 2), run,
                              EI._target_of_run(run), in_raw=True)
        doc = {"_meta": {"dir": name, "files": {}, "bytes": {}, "record_files": 1,
                         "nonrecord_files": 0, "runs": {r: 1 for r in runs},
                         "run_targets": {r: EI._target_of_run(r) for r in runs},
                         "targets": sorted({t for t in
                                            (EI._target_of_run(r) for r in runs) if t}),
                         "parse_failures": 0, "instr_names_seen": {},
                         "field_names_seen": {}, "instr_records": {},
                         "n_group_strings": 0, "has_raw": has_raw,
                         "has_prereg": True, "has_contract": True,
                         "has_results": True, "has_manifest": True,
                         "has_verdicts": True, "quarantined": quarantined},
               "cells": {"%s.%s" % (m, f): EI._finish(c) for (m, f), c in cells.items()},
               "controls": {"%s.%s" % (m, f): EI._finish(c)
                            for (m, f), c in ctrl.items()}}
        json.dump(doc, open(os.path.join(idx, name + ".json"), "w"), indent=1,
                  default=str)
        return name

    # A clean sweep: 16 values, ledger agrees, two semantic buckets, discriminating
    # oracle, two carriers, two runs, no contamination.
    good = []
    for v in range(16):
        good.append({"instr": "tst", "field": "f", "value": v,
                     "bytes": "%x901" % v if v else "0901",
                     "sem_match": (v % 3 != 0),
                     "outcome": "ok" if v % 3 else "wrong_value",
                     "observed": {"z": v}, "oracle": {"z": v, "source": "host"},
                     "carrier": "C1" if v < 8 else "C2"})
    mk("EXP-9001-good", good)

    # Same, but the assembler could not clear the requested bits: requested value
    # moves, actual bytes do not. (DEF-0166.)
    stuck = [dict(r, bytes="0901") for r in good]
    mk("EXP-9002-stuck-bytes", stuck)

    # Same, but no bytes recorded at all: no ledger.
    noledger = [{k: v for k, v in r.items() if k != "bytes"} for r in good]
    mk("EXP-9003-no-ledger", noledger)

    # Same, but zero semantic checks -- only a liveness ladder prediction.
    nosem = [{k: v for k, v in r.items() if k not in ("sem_match", "oracle")}
             for r in good]
    nosem = [dict(r, predict="move") for r in nosem]
    mk("EXP-9004-no-semantics", nosem)

    # Same, but the control arm is present and never moves.
    mk("EXP-9005-dead-control", good, controls="dead")
    # ...and one with no control arm at all, so "failed" and "absent" stay distinct.
    mk("EXP-9005b-no-control", good, controls=None)

    # Same, one run only.
    mk("EXP-9006-one-run", good, runs=("g17p_run01",))

    # Same, but it ran on the M4.
    mk("EXP-9007-wrong-target", good, runs=("m4_run01", "m4_run02"))

    # Same, but faults plus a victim marker in the same raw.
    cascade = [dict(r, outcome="fault", victim=True) for r in good]
    mk("EXP-9008-cascade", cascade)

    # Same, but no authored probe committed.
    mk("EXP-9009-no-authored", good, authored=False)

    # A recipe registry: `tst` is generated but field `f` is still donor-supplied;
    # `tst2` is generated clean.
    d = os.path.join(exps, "EXP-9010-recipes", "analysis")
    os.makedirs(d, exist_ok=True)
    json.dump({"instructions": [
        {"mnemonic": "tst", "verdict": "GENERATED-AND-EMITTABLE",
         "in_generated_corpus": True, "donor_fields": {}},
        {"mnemonic": "tstdonor", "verdict": "PARTLY-DONOR",
         "in_generated_corpus": True, "donor_fields": {"f": 3}},
        {"mnemonic": "tstungen", "verdict": "EMITTABLE-NOT-GENERATED",
         "in_generated_corpus": False, "donor_fields": {}},
    ]}, open(os.path.join(d, "template_dependency.json"), "w"))
    json.dump({"_meta": {}, "cells": {}, "controls": {},
               "_fingerprint": "x"},
              open(os.path.join(idx, "EXP-9010-recipes.json"), "w"))
    return exps, idx


def selftest(verbose=False):
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="promcheck-")
    try:
        exps, idx = _fixture(tmp)
        e = Evidence(index_dir=idx, root=tmp)
        base = {"key": "tst.f", "mnemonic": "tst", "field": "f",
                "label": "hardware-run", "range": "0..15 dense (all 16 values)",
                "target": "G17P", "evidence": [], "note": "", "axes": None,
                "values_dispatched": None, "distinct_bytes": None,
                "encodable_range": 16, "start": 4, "width": 4}

        def run(**kw):
            row = dict(base)
            row.update(kw)
            return check_row(row, e)

        ok = True
        results = []

        def expect(name, code, want, **kw):
            nonlocal ok
            r = run(**kw)
            got = r["rules"][code]["verdict"]
            good = (got == want)
            print("%-4s %-11s %-13s %s" % ("PASS" if good else "FAIL", code, got, name))
            if not good:
                ok = False
                print("       expected %s; why: %s" % (want, r["rules"][code]["why"]))
            results.append(r)
            return r

        print("--- each gate must be able to say NO ---")
        expect("R1 rejects a citation resolving to no directory", "R1", REJECT,
               evidence=["EXP-9999-nope"])
        expect("R1 rejects an experiment with no authored probe", "R1", REJECT,
               evidence=["EXP-9009-no-authored"])
        expect("R2 rejects a G17P claim whose raw ran on the M4", "R2", REJECT,
               evidence=["EXP-9007-wrong-target"])
        expect("R3 flags a sweep that recorded no actual bytes", "R3", INSUFFICIENT,
               evidence=["EXP-9003-no-ledger"])
        expect("R3 REJECTS requested != decoded (the DEF-0166 signature)", "R3",
               REJECT, evidence=["EXP-9002-stuck-bytes"])
        expect("R4 rejects 16 claimed values reaching 1 actual encoding", "R4",
               REJECT, evidence=["EXP-9002-stuck-bytes"])
        expect("R5 refuses hardware-run with zero semantic checks", "R5",
               INSUFFICIENT, evidence=["EXP-9004-no-semantics"])
        expect("R6 rejects a carrier whose control never fired", "R6", REJECT,
               evidence=["EXP-9005-dead-control"])
        expect("R6 separates 'control absent' from 'control failed'", "R6",
               INSUFFICIENT, evidence=["EXP-9005b-no-control"])
        expect("R7 refuses a single-run promotion", "R7", INSUFFICIENT,
               evidence=["EXP-9006-one-run"])
        expect("R8 rejects a donor-supplied field in a generated recipe", "R8",
               REJECT, key="tstdonor.f", mnemonic="tstdonor",
               evidence=["EXP-9001-good"])
        expect("R8 refuses a mnemonic no generated program ever contained", "R8",
               INSUFFICIENT, key="tstungen.f", mnemonic="tstungen",
               evidence=["EXP-9001-good"])
        expect("R9 rejects faults sharing raw with a victim marker", "R9", REJECT,
               evidence=["EXP-9008-cascade"])

        print("\n--- ...and each gate must be able to say YES ---")
        good = expect("R1 accepts a resolvable, authored, un-quarantined citation",
                      "R1", PASS, evidence=["EXP-9001-good"])
        expect("R2 accepts a G17P claim whose raw ran on G17P", "R2", PASS,
               evidence=["EXP-9001-good"])
        expect("R3 accepts a ledger where requested == decoded", "R3", PASS,
               evidence=["EXP-9001-good"])
        expect("R4 accepts 16 distinct actual encodings for 16 claimed values", "R4",
               PASS, evidence=["EXP-9001-good"])
        expect("R5 accepts semantic checks spanning two buckets", "R5", PASS,
               evidence=["EXP-9001-good"])
        expect("R6 accepts a control that moved", "R6", PASS,
               evidence=["EXP-9001-good"])
        expect("R7 accepts two runs across two carriers", "R7", PASS,
               evidence=["EXP-9001-good"])
        expect("R8 accepts a generated recipe with no donor field", "R8", PASS,
               evidence=["EXP-9001-good"])
        expect("R9 accepts clean raw with no hard outcome", "R9", NA,
               evidence=["EXP-9001-good"])

        print("\n--- the whole gate must be able to ACCEPT a row ---")
        allpass = run(evidence=["EXP-9001-good"])
        good_all = allpass["promotable"]
        print("%-4s a well-formed claim is PROMOTABLE (the gate is not refuse-all)"
              % ("PASS" if good_all else "FAIL"))
        if not good_all:
            ok = False
            for c in allpass["blocking"]:
                print("       %s: %s" % (c, allpass["rules"][c]["why"]))

        print("\n--- the label must not drive the verdict ---")
        r = run(evidence=["EXP-9004-no-semantics"], label="hardware-run")
        lab_ok = "R5" in r["blocking"]
        print("%-4s a row LABELLED hardware-run is still rejected when its raw has "
              "0 semantic checks" % ("PASS" if lab_ok else "FAIL"))
        ok = ok and lab_ok

        print("\n--- section 8: no single emittable headline ---")
        out = os.path.join(tmp, "reports")
        write_reports(results + [allpass], out, "selftest fixture")
        blob = ""
        for p in sorted(glob.glob(os.path.join(out, "*.md"))):
            blob += open(p).read()
        bad = re.findall(r"\b\d+\s*(?:of|/)\s*166\b|emittable_instructions|"
                         r"\bemittable\s*[:=]\s*\d+", blob)
        head_ok = not bad
        print("%-4s no report derives an `N of 166 emittable` headline%s"
              % ("PASS" if head_ok else "FAIL", "" if head_ok else ": %r" % bad[:3]))
        ok = ok and head_ok
        six = all(os.path.exists(os.path.join(out, "%s.md" % k)) for k in REPORTS)
        print("%-4s all six reports (geometry, liveness, semantics, recipe, target, "
              "audit) were written" % ("PASS" if six else "FAIL"))
        ok = ok and six

        print("\nPROMOTION-CHECK SELFTEST %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=os.path.join(HERE, "validation.json"))
    ap.add_argument("--verdicts", nargs="*", help="check proposed field_verdicts.json "
                                                  "instead of validation.json")
    ap.add_argument("--report-dir",
                    default=os.path.join(ROOT, "experiments", "EXP-0209-dashboards",
                                         "reports"))
    ap.add_argument("--index-dir", default=None)
    ap.add_argument("--row", help="check one <mnemonic>.<field> and print it")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest(a.verbose)

    e = Evidence(index_dir=a.index_dir)
    if a.verdicts:
        rows = claims_from_verdicts(a.verdicts)
        src = ", ".join(a.verdicts)
    else:
        rows = claims_from_validation(a.labels)
        src = os.path.relpath(a.labels, ROOT)
    if a.row:
        rows = [r for r in rows if r["key"] == a.row]
        if not rows:
            print("no such row: %s" % a.row, file=sys.stderr)
            return 2
        for r in rows:
            print(json.dumps(check_row(r, e), indent=1, default=str))
        return 0

    results = [check_row(r, e) for r in rows]
    write_reports(results, a.report_dir, src)
    print("checked %d claim rows from %s" % (len(results), src))
    print("reports written to %s" % os.path.relpath(a.report_dir, ROOT))
    print()
    print("  axis            PASS  REJECT  INSUFF     N/A")
    for name in sorted(REPORTS):
        t = collections.Counter(r["axis"][name] for r in results)
        print("  %-12s %6d  %6d  %6d  %6d"
              % (name, t.get(PASS, 0), t.get(REJECT, 0), t.get(INSUFFICIENT, 0),
                 t.get(NA, 0)))
    print()
    print("  rows with no blocking rule: %d of %d  (NOT an emittability count -- "
          "see section 8)" % (sum(1 for r in results if r["promotable"]), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
