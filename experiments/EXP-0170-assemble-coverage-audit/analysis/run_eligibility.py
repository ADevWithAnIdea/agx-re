#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0170 Arm D, step 1 -- build the run-eligibility table frozen in
PRE_REGISTRATION.md AMENDMENT D.3.

E1  a marker file in the run's own raw directory
E2  an explicit prose disownment in a committed .md of the source experiment
    (hand-curated; every entry carries the quote and its file:line, as D.3 requires)
E3  EXP-0164's own NONGATED regex, unchanged

READ-ONLY.  Writes only analysis/run_eligibility.json.
Usage: python3 analysis/run_eligibility.py
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))

E1_MARK = re.compile(r"^(PARTIAL\.md|NOT_RUN\.md|SCOPE\.md|QUARANTINE.*\.md|BURNED.*|INVALID.*)$", re.I)
E3_NONGATED = re.compile(r"(prefreeze|smoke|pilot|quarantine|burned)", re.I)

# ---------------------------------------------------------------------------
# E2: prose disownment.  Hand-curated by reading each committed .md.  Every row
# is (experiment dir, run id) -> {quote, cite}.  D.3 forbids calling a run
# disowned without a quote, so this table IS the evidence.
# ---------------------------------------------------------------------------
E2 = {
 ("EXP-0138-m4-emit-falu", "m4_20260828_run02"): {
   "cite": "experiments/EXP-0138-m4-emit-falu/README.md:52-58",
   "quote": "run02 and run03 were killed by a machine-wide MTLCompilerService collapse, "
            "run04 by a host reboot, and run07 by a GPU hang while two sibling experiments "
            "held live agxrun_persist children; all are retained as partials. The gated "
            "pair analysed is run01 + run06, with run05 as a third annotating run."},
 ("EXP-0138-m4-emit-falu", "m4_20260828_run03"): {
   "cite": "experiments/EXP-0138-m4-emit-falu/README.md:52-58", "quote": "(same passage)"},
 ("EXP-0138-m4-emit-falu", "m4_20260828_run04"): {
   "cite": "experiments/EXP-0138-m4-emit-falu/README.md:52-58", "quote": "(same passage)"},
 ("EXP-0138-m4-emit-falu", "m4_20260828_run07"): {
   "cite": "experiments/EXP-0138-m4-emit-falu/PROGRESS.md:114-117",
   "quote": "Its records are contaminated and it is NOT used as a gated run."},
 ("EXP-0140-m4-emit-mov-cf", "m4_20260828_run01"): {
   "cite": "experiments/EXP-0140-m4-emit-mov-cf/QUARANTINE-NOTE-run01.md:1",
   "quote": "raw/m4_20260828_run01 - retained, NOT used for any field verdict"},
 ("EXP-0141-m4-emit-mem", "m4-20260828-run01"): {
   "cite": "experiments/EXP-0141-m4-emit-mem/README.md:65",
   "quote": "RETAINED partial capture, superseded, see its PARTIAL.md"},
 ("EXP-0144-m4-emit-pack", "m4_20260828_run01"): {
   "cite": "experiments/EXP-0144-m4-emit-pack/RESULTS.md:29-33",
   "quote": "Everything promoted here comes from the revalidation captures m4_20260828_rv01__* "
            "only. The earlier captures run01-run05 are retained as append-only history and "
            "back no label."},
 ("EXP-0155-g17p-emit-tex-frag", "g17p_20260829_run01"): {
   "cite": "experiments/EXP-0155-g17p-emit-tex-frag/raw/g17p_20260829_run01/PARTIAL.md:1",
   "quote": "PARTIAL, RETAINED, NOT REUSED, NOT USED FOR PROMOTION"},
 ("EXP-0155-g17p-emit-tex-frag", "g17p_20260829_run02"): {
   "cite": "experiments/EXP-0155-g17p-emit-tex-frag/raw/g17p_20260829_run02/PARTIAL.md:1",
   "quote": "PARTIAL, RETAINED, NOT REUSED, NOT USED FOR PROMOTION"},
 ("EXP-0153-g17p-revalidation", "g17p-20260830-run02"): {
   "cite": "experiments/EXP-0153-g17p-revalidation/raw/g17p-20260830-run02/PARTIAL.md:1",
   "quote": "PARTIAL CAPTURE -- RETAINED, NOT REUSED"},
 ("EXP-0156-g17p-emit-cf-mem", "g17p-20260830-cf01a"): {
   "cite": "experiments/EXP-0156-g17p-emit-cf-mem/raw/BURNED_RUN_IDS.md:37-39",
   "quote": "raw/g17p-20260830-cf01a/ - 887 records, killed by a transport failure. "
            "See its PARTIAL.md. Cited by no verdict."},
}
for _r in ("m4_20260828_run02", "m4_20260828_run03", "m4_20260828_run04", "m4_20260828_run05"):
    E2[("EXP-0144-m4-emit-pack", _r)] = E2[("EXP-0144-m4-emit-pack", "m4_20260828_run01")]

# A run the source experiment DOES use, but only in a weaker role.  Flagged, not
# disqualified -- D.3 lists no such ground.
E2_FLAG = {
 ("EXP-0138-m4-emit-falu", "m4_20260828_run05"): {
   "flag": "annotating-only",
   "cite": "experiments/EXP-0138-m4-emit-falu/PROGRESS.md:119-120",
   "quote": "Gated pair analysed: run01 + run06 (run06 replaces the contract's dead run02), "
            "with run05 carried as a third annotating run."},
}

# Where the source experiment CONTRADICTS ITSELF about a run.  Recorded so the
# orchestrator can see it; the frozen rules still make the run ineligible.
E2_CONFLICT = {
 ("EXP-0144-m4-emit-pack", "m4_20260828_run05"): {
   "disowned_by": "experiments/EXP-0144-m4-emit-pack/RESULTS.md:29-33 "
                  "('run01-run05 ... back no label')",
   "but_retained_by": "experiments/EXP-0144-m4-emit-pack/raw/m4_20260828_run05/SCOPE.md:1-12",
   "quote": "m4_20260828_run05 - PARTIAL BUT USED, within the scope stated here. ... "
            "Everything it recorded before that point is a valid measurement and IS used, "
            "within this scope: pack_convert - complete (arms C, S, F, W, X). Gated against "
            "m4_20260828_run03: 6,251/6,255 gated records byte-identical (99.936 %). "
            "unpack_convert - arms C, S and the full per-byte F sweep complete.",
   "scoped_to": ["pack_convert", "unpack_convert"]},
 ("EXP-0144-m4-emit-pack", "m4_20260828_rv01__cvt_f2h_dst"): {
   "disowned_by": "(none -- E1 fires only because a SCOPE.md is present)",
   "but_retained_by": "experiments/EXP-0144-m4-emit-pack/raw/m4_20260828_rv01__cvt_f2h_dst/SCOPE.md:1-10",
   "quote": "rv01__cvt_f2h_dst - PARTIAL (294 of 1311), retained. ... The 294 records "
            "present are complete majority-of-N measurements and are used.",
   "scoped_to": None},
}


def main():
    out = {}
    for exp in sorted(os.listdir(EXPDIR)):
        raw = os.path.join(EXPDIR, exp, "raw")
        if not os.path.isdir(raw):
            continue
        for run in sorted(os.listdir(raw)):
            rd = os.path.join(raw, run)
            if not os.path.isdir(rd):
                continue
            marks = sorted(f for f in os.listdir(rd) if E1_MARK.match(f))
            reasons = []
            if marks:
                reasons.append("E1:" + ",".join(marks))
            e2 = E2.get((exp, run))
            if e2:
                reasons.append("E2")
            if E3_NONGATED.search(run):
                reasons.append("E3")
            rec = {"experiment": exp, "run": run, "eligible": not reasons,
                   "ineligible_reasons": reasons, "e1_markers": marks}
            if e2:
                rec["e2"] = e2
            if (exp, run) in E2_FLAG:
                rec["flag"] = E2_FLAG[(exp, run)]
            if (exp, run) in E2_CONFLICT:
                rec["source_conflict"] = E2_CONFLICT[(exp, run)]
            out["%s/%s" % (exp, run)] = rec

    n_inel = sum(1 for r in out.values() if not r["eligible"])
    doc = {"_meta": {"generated_by": "EXP-0170/analysis/run_eligibility.py",
                     "rules": "PRE_REGISTRATION.md AMENDMENT D.3 (E1/E2/E3), frozen",
                     "e1_marker_regex": E1_MARK.pattern,
                     "e3_nongated_regex": E3_NONGATED.pattern,
                     "note": "EXP-0164 honoured only PARTIAL.md, and only via a raw-dir scan."},
           "totals": {"runs": len(out), "ineligible": n_inel,
                      "eligible": len(out) - n_inel,
                      "e2_prose_disownments_curated": len(E2),
                      "source_self_conflicts": len(E2_CONFLICT)},
           "runs": out}
    json.dump(doc, open(os.path.join(HERE, "run_eligibility.json"), "w"),
              indent=1, sort_keys=True)
    print("runs %d  ineligible %d  (E2 curated %d, self-conflicts %d)"
          % (len(out), n_inel, len(E2), len(E2_CONFLICT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
