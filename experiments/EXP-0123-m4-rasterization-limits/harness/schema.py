"""EXP-0123 record schema -- frozen key sets for gated/nongated JSONL rows."""

GATED_KEYS = {"case_id", "family", "kind", "params", "status", "verdict", "observed"}
NONGATED_KEYS = {"case_id", "gputime_ns", "wall_ms", "pid", "raw_tail"}

FAMILIES = {
    "line_rule", "point_rounding", "polygon_fillmode", "wide_line_negative",
    "depth_clip_clamp", "conservative_raster", "coverage_earlylate",
    "limit_attachments", "limit_viewports", "limit_tex", "limit_bufferindex",
    "limit_textureindex", "limit_bytesconst", "limit_bufferalign",
    "limit_threadgroup", "limit_tgmem_dynamic", "simd_width", "simd_shuffle_oob",
}


def validate_gated(rec):
    if set(rec.keys()) != GATED_KEYS:
        return False, f"gated keys mismatch: {sorted(rec.keys())}"
    if rec["family"] not in FAMILIES:
        return False, f"unknown family {rec['family']}"
    if rec["verdict"] not in ("PASS", "FAIL", "TIMEOUT", "N/A"):
        return False, f"bad verdict {rec['verdict']}"
    if not isinstance(rec["observed"], dict):
        return False, "observed must be an object"
    return True, "ok"
