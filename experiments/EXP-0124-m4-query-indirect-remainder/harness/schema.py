"""EXP-0124 authoritative record schema, imported by run.py (producer), verify.py
(consumer), and icbmax_bisect.py. Pure data, no device/filesystem access at import time
(standing gate (a): one shared key set).

Gate (d) -- nondeterminism exclusion -- is realized structurally here: GATED_KEYS never
includes a raw timestamp/tick value or any other field whose *exact numeric value* is
expected to differ run-to-run for reasons other than a bug (wall-clock time, PIDs, raw
resolved-counter tick magnitudes, GPU-scheduling-dependent race counts). Those live only
in NONGATED_KEYS's `raw_ticks` (a dict, case-family-defined shape) and `raw_tail`/`wall_ms`/
`pid`. Every field that must be byte-identical across two independent runs on the same
pinned revision (ordering booleans, equality relations, counts, status, verdict, byte-exact
structural payloads) lives in GATED_KEYS's `observed`.
"""

GATED_KEYS = {"case_id", "family", "kind", "params", "status", "verdict", "observed"}
NONGATED_KEYS = {"case_id", "wall_ms", "pid", "raw_tail", "raw_ticks"}

STATUS_VALUES = {
    "OK", "HANG", "CMDBUF_ERROR", "PIPELINE_FAIL", "FUNCTION_MISSING", "COMPILE_FAIL",
    "ALLOC_FAIL", "ALLOC_REJECTED", "HARNESS_CRASH", "RESOLVE_NIL", "EXCEPTION",
}
VERDICT_VALUES = {"PASS", "FAIL", "TIMEOUT", "N/A"}

FAMILIES = {
    "q_caps", "q_alloc", "q_avail", "q_reset", "q_copy", "q_simul", "q_occmode",
    "q_occoverwrite", "q_tick",
    "i_cdmfmt", "i_icbwrite", "i_icbbarrier", "i_restart",
}

# icbmax_bisect uses its own small record shape (not the general gated/nongated pair,
# since it is a probe-sequence, not a fixed-matrix case) -- documented and validated
# separately, see ICBMAX_PROBE_KEYS below.
ICBMAX_PROBE_KEYS = {"probe_id", "maxCommandCount", "status", "outcome", "wall_ms", "pid"}
ICBMAX_OUTCOME_VALUES = {"WORKS", "CRASH", "TIMEOUT", "OTHER_FAIL"}


def validate_gated(rec):
    if set(rec.keys()) != GATED_KEYS:
        return False, f"gated record key set mismatch: {sorted(rec.keys())} != {sorted(GATED_KEYS)}"
    if rec["status"] not in STATUS_VALUES:
        return False, f"unknown status {rec['status']!r}"
    if rec["verdict"] not in VERDICT_VALUES:
        return False, f"unknown verdict {rec['verdict']!r}"
    if rec["family"] not in FAMILIES:
        return False, f"unknown family {rec['family']!r}"
    if not isinstance(rec["params"], dict) or not isinstance(rec["observed"], dict):
        return False, "params/observed must be objects"
    # gate (d), enforced structurally: no key inside `observed` may look like a raw
    # nanosecond tick value (heuristic name check backed by the explicit per-family
    # producer code in run.py, which never writes such a field into `observed`).
    for k in rec["observed"].keys():
        if k.endswith("_ns") or k in ("cpu_ts", "gpu_ts", "raw_tick"):
            return False, f"observed contains a raw-tick-shaped key {k!r}; belongs in raw_ticks"
    return True, "ok"


def validate_nongated(rec):
    if set(rec.keys()) != NONGATED_KEYS:
        return False, f"nongated record key set mismatch: {sorted(rec.keys())} != {sorted(NONGATED_KEYS)}"
    if not isinstance(rec["raw_ticks"], dict):
        return False, "raw_ticks must be an object"
    return True, "ok"


def validate_icbmax_probe(rec):
    if set(rec.keys()) != ICBMAX_PROBE_KEYS:
        return False, f"icbmax probe key set mismatch: {sorted(rec.keys())} != {sorted(ICBMAX_PROBE_KEYS)}"
    if rec["outcome"] not in ICBMAX_OUTCOME_VALUES:
        return False, f"unknown icbmax outcome {rec['outcome']!r}"
    return True, "ok"
