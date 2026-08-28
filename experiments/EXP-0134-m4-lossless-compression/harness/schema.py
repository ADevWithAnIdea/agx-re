"""EXP-0134 record schema, imported by run.py (producer) and verify.py (consumer).
Pure data, no device/filesystem access at import time (standing gate (a)).

Gate (d) -- nondeterminism exclusion -- is realized structurally: GATED_KEYS never
includes a raw timestamp/tick/pid value. Every field expected to be byte-identical
across two independent runs on the same pinned revision (creation success, the
compression descriptor's flag bits, secondary VA presence, measured aux byte
counts, aux content hex, replicate base_va deltas, CPU-op success/detail) lives
in GATED_KEYS's `observed`. Wall-clock time, pid, and raw stdout tails live only
in NONGATED_KEYS.
"""

GATED_KEYS = {"case_id", "family", "kind", "params", "status", "verdict", "observed"}
NONGATED_KEYS = {"case_id", "wall_ms", "pid", "raw_tail", "raw_ticks"}

STATUS_VALUES = {
    "OK", "ALLOC_REJECTED", "HARNESS_CRASH", "HANG", "CMDBUF_ERROR",
    "PIPELINE_FAIL", "FUNCTION_MISSING", "COMPILE_FAIL", "DECODE_FAIL",
}
VERDICT_VALUES = {"PASS", "FAIL", "N/A"}

FAMILIES = {"elig", "aux", "state", "cpu"}


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
    for k in rec["observed"].keys():
        if k.endswith("_ns") or k in ("cpu_ts", "gpu_ts", "raw_tick", "wall_ms", "pid"):
            return False, f"observed contains a raw-tick/time-shaped key {k!r}; not permitted (gate d)"
    return True, "ok"


def validate_nongated(rec):
    if set(rec.keys()) != NONGATED_KEYS:
        return False, f"nongated record key set mismatch: {sorted(rec.keys())} != {sorted(NONGATED_KEYS)}"
    if not isinstance(rec["raw_ticks"], dict):
        return False, "raw_ticks must be an object"
    return True, "ok"
