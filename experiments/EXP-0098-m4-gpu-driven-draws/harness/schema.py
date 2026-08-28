"""EXP-0098 authoritative record schema, imported by BOTH run.py (the producer)
and verify.py (the consumer) -- standing gate (a): one shared key set, no
duplicated/divergent copy. Runnable in every tree state (pure data, no device
or filesystem access at import time).
"""

# Every gated record (raw/<run_id>/02_gated.jsonl line) has exactly these keys.
GATED_KEYS = {"case_id", "family", "kind", "params", "status", "verdict", "observed"}

# Every non-gated sibling record (raw/<run_id>/03_nongated.jsonl line) has
# exactly these keys. This is where legitimately nondeterministic
# scheduling-order detail lives (gate class (d)): exact race magnitudes,
# per-run timing, pid, and the process's raw stdout/stderr tail.
NONGATED_KEYS = {"case_id", "wall_ms", "pid", "raw_tail"}

STATUS_VALUES = {"OK", "HANG", "CMDBUF_ERROR", "PIPELINE_FAIL", "FUNCTION_MISSING",
                  "COMPILE_FAIL", "ALLOC_FAIL", "HARNESS_CRASH"}

VERDICT_VALUES = {"PASS", "FAIL", "TIMEOUT", "N/A"}

# case families (the "family" key).
FAMILIES = {"h_sync", "h_fields", "h_icbrange", "h_icbmax",
            "xfb_capacity", "xfb_multistream", "xfb_discard", "xfb_sync"}


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
    return True, "ok"


def validate_nongated(rec):
    if set(rec.keys()) != NONGATED_KEYS:
        return False, f"nongated record key set mismatch: {sorted(rec.keys())} != {sorted(NONGATED_KEYS)}"
    return True, "ok"
