#!/usr/bin/env python3
"""EXP-0091 shared record schema -- the ONE authoritative key-set for both the
runner (run.py) and the verifier (verify.py). Import this module from both; never
restate the key list in either file (the EXP-0073 quarantine-class defect this
repo's standing gate set exists to prevent).

A case produces exactly two sibling files per run directory:
  raw/<run>/<case_id>.gated.json     -- byte/value-deterministic fields only.
  raw/<run>/<case_id>.nongated.json  -- timing/pid/wall-clock fields only.
Nothing in .gated.json may vary between two honest repeated executions of the
same case on the same hardware/toolchain. Nothing timing-shaped may appear in
.gated.json.
"""

# Top-level keys REQUIRED (exactly, no more no less) in every *.gated.json record.
GATED_KEYS = frozenset({
    "case_id",       # str, matches filename stem
    "group",         # str, one of GROUPS
    "kind",          # "gpu_render" | "compile_scan"  (two case shapes this exp uses)
    "params",        # dict: exact frozen CLI args / compile inputs for this case
    "status",        # str: STATUS token from fsrun, or "DECODED"/"SCAN" for compile_scan
    "result",        # dict: the case-kind-specific deterministic payload (see below)
})

# Non-gated (timing-only) sibling record keys.
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
    "pixels",            # list of {x,y,bgra} sorted by (y,x)
    "depth",             # list of {x,y,value} or null
    "occlusion",         # int or null
    "buffers",           # dict: {str(idx): hex string}
    "error",             # str or null (ERROR line text, for FAIL statuses)
})

# result payload shape for kind == "compile_scan":
SCAN_RESULT_KEYS = frozenset({
    "frag_main_hex",     # str: the extracted fragment _agc.main hex
    "frag_main_len",     # int
    "hits_0x57",         # list of {offset, exact6}
    "hits_0x07",         # list of {offset, exact6}
    "tokenize_clean",    # bool: did tools/agx-isa tokenize with 0 leftover
    "tokenize_leftover", # int: leftover byte count (0 if clean)
})

GROUPS = frozenset({
    "loc",       # GLFS-A01 differential-compile localization (compile_scan)
    "splice",    # GLFS-A01 HW splice validation (gpu_render, archive mode)
    "msaa",      # GLFS-A01/A07 mask width/hole sweep (gpu_render, plain mode)
    "demote",    # GLFS-A02/OPT-09/A03 demote-vs-terminate + helper status
    "depth",     # GLFS-A05 early/late depth-stencil ordering
    "suppress",  # GLFS-A06 suppression matrix
    "sampleshading",  # GLFS-A07 invocation/liveness model
})

RUN_IDS = ("run01", "run02")
