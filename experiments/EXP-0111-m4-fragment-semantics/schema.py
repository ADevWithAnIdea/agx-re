#!/usr/bin/env python3
"""EXP-0111 shared record schema -- the ONE authoritative key-set for both the
runner (run.py) and the verifier (verify.py). Import this module from both; never
restate the key list in either file (the EXP-0073-class defect this repo's standing
gate set exists to prevent; pattern follows EXP-0091's schema.py).

A case produces exactly two sibling files per run directory:
  raw/<run>/<case_id>.gated.json     -- byte/value-deterministic fields only.
  raw/<run>/<case_id>.nongated.json  -- timing/pid/wall-clock fields only.
Nothing in .gated.json may vary between two honest repeated executions of the
same case on the same hardware/toolchain. Nothing timing-shaped may appear in
.gated.json.
"""

GATED_KEYS = frozenset({
    "case_id",       # str, matches filename stem
    "group",         # str, one of GROUPS
    "kind",          # "gpu_render" | "compile_scan" | "compile_attempt"
    "params",        # dict: exact frozen CLI args / compile inputs for this case
    "status",        # str: STATUS token from fsrun, or "SCANNED"/"REJECTED"/"ACCEPTED"
    "result",        # dict: the case-kind-specific deterministic payload (see below)
})

NONGATED_KEYS = frozenset({
    "case_id",
    "gputime_ns",
    "wall_ms",
    "pid",
    "started_at",
})

# result payload shape for kind == "gpu_render":
GPU_RESULT_KEYS = frozenset({
    "device",            # str, MTLDevice name (deterministic: fixed test host)
    "pipeline_source",   # "compiled" | "archive"
    "size",              # [w,h,samples]
    "pixels",            # dict: {rt_index_str: [{x,y,bgra}, ...] sorted by (y,x)}
    "depth",             # list of {x,y,value} or null
    "occlusion",         # int or null
    "buffers",           # dict: {str(idx): hex string}
    "error",             # str or null (ERROR line text, for FAIL statuses)
})

# result payload shape for kind == "compile_scan" (own-shader byte-level structural scan):
SCAN_RESULT_KEYS = frozenset({
    "frag_main_hex",     # str: the extracted fragment _agc.main hex
    "frag_main_len",     # int
    "tokenize_clean",    # bool: did tools/agx-isa tokenize with 0 leftover
    "tokenize_leftover", # int: leftover byte count (0 if clean)
    "counts",            # dict: case-specific op-family counts (e.g. {"get_sr_a0":1})
})

# result payload shape for kind == "compile_attempt" (does source X compile at all?):
ATTEMPT_RESULT_KEYS = frozenset({
    "compiled",           # bool
    "error_text",         # str or null (truncated NSError text on failure)
})

GROUPS = frozenset({
    "poscoord",         # FS-01/02/03
    "deriv_quad",        # FS-04
    "deriv_scalar",       # FS-07 (+ FS-04/05 axis-byte cross-check)
    "deriv_helper",       # FS-02 (helper)/FS-06/GLFS-A03 remainder
    "interp_mode",        # FS-08 remainder (centroid/offset)
    "interp_convergent",  # FS-09
    "dynidx_in",           # FS-10
    "dynidx_out",          # FS-11
    "fs12_samplemask",     # FS-12 remainder
    "anomaly_helper_pre",  # EXP-0091 anomaly (a) second method
    "anomaly_persample",   # EXP-0091 anomaly (b) second method
})

RUN_IDS = ("run01", "run02")
