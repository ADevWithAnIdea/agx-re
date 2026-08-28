"""EXP-0097 authoritative record schema, imported by BOTH run.py (producer)
and verify.py (consumer) -- standing gate (a): one shared key set, no
duplicated/divergent copy. Runnable in every tree state (pure data, no
device or filesystem access at import time).
"""

GATED_KEYS = {"case_id", "family", "kind", "params", "status", "verdict", "observed"}

NONGATED_KEYS = {"case_id", "gputime_ns", "wall_ms", "pid", "raw_tail"}

STATUS_VALUES = {"OK", "COMPILE_FAIL", "FUNCTION_MISSING", "PIPELINE_FAIL",
                  "CMDBUF_ERROR", "HANG", "HARNESS_CRASH", "READ_FAIL"}

VERDICT_VALUES = {"PASS", "FAIL", "TIMEOUT", "N/A"}

FAMILIES = {"vary_scalar", "vary_dce", "clip_sweep", "cull_negative",
            "vary_clip_combo", "vary_render_confirm", "position_special",
            "point_size", "layer_oob", "viewport_oob", "provoking"}


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
