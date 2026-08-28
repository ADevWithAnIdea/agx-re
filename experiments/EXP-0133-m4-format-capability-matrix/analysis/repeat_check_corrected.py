#!/usr/bin/env python3
"""Post-hoc, NOT-part-of-frozen-AUTH corrected repeat-exactness check.

analysis.py (frozen at capture time, part of AUTH, hash-bound in both runs'
00_inputs.json -- see verify.py check_inputs_bindings) has a disclosed bug:
its repeat-check compares the full "argv" list across run07 vs run08
byte-for-byte, but argv[0] is each run's own compiled probe binary path
(work/m4-20260828-run07/probe vs work/m4-20260828-run08/probe) -- a
deterministic, BY-DESIGN per-run difference (each run compiles a fresh
probe binary into its own run-id-scoped work/ directory), not evidence of
non-determinism. This makes analysis.py report repeat_exact=False with
exactly 1548/1548 "mismatches" (every case, all on the argv field alone),
which is misleading without this note.

Because analysis.py is part of AUTH and its hash is bound into both already-
captured runs' 00_inputs.json, it cannot be edited post-capture without
invalidating verify.py's post-capture source-binding check (which exists to
prevent exactly this class of post-hoc tampering with evidence-PRODUCING
code) -- so the bug is fixed here instead, in a script that is NOT part of
AUTH and does not touch, re-run, or reinterpret any raw/ file, only reads it
read-only and recomputes the comparison analysis.py should have made.

This script changes no evidence and produces no new evidence: it is
provenance for how RESULTS.md's stated repeat-exactness number was derived
by hand from the existing raw/ data, in place of analysis.py's own
(disclosed-buggy) automated field.
"""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
RUNS = ("m4-20260828-run07", "m4-20260828-run08")

def load_case(rid, cid):
    return json.loads((HERE / "raw" / rid / "cases" / (cid + ".json")).read_text())

def main():
    rm = json.loads((HERE / "raw" / RUNS[0] / "run_manifest.json").read_text())
    case_ids = rm["cases"]
    mismatches = []
    for cid in case_ids:
        z0, z1 = load_case(RUNS[0], cid), load_case(RUNS[1], cid)
        for k in ("cwd", "timeout_seconds", "timed_out", "exit", "stdout", "stderr", "exception"):
            if z0[k] != z1[k]:
                mismatches.append({"case": cid, "field": k})
        argv0 = [x for x in z0["argv"] if not str(x).endswith("/probe")]
        argv1 = [x for x in z1["argv"] if not str(x).endswith("/probe")]
        if argv0 != argv1:
            mismatches.append({"case": cid, "field": "argv (excluding the run-id-scoped probe path)"})
    out = {"schema": 1, "runs": list(RUNS), "case_count": len(case_ids),
           "repeat_exact_corrected": len(mismatches) == 0, "mismatch_count": len(mismatches),
           "mismatches_sample": mismatches[:20],
           "note": "corrects analysis.py's argv-comparison bug (see this file's docstring); "
                   "raw/ is untouched; analysis.py itself is left at its frozen, captured, "
                   "hash-bound state (mismatch_count=1548, all on the run-id-scoped probe path)"}
    dst = HERE / "analysis" / "repeat_check_corrected.json"
    dst.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
