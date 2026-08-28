#!/usr/bin/env python3
"""EXP-0110 frozen case matrix -- single source of truth, imported by
run.py and verify.py. Every case is ONE variable changed vs the group's
baseline (CODEX one-variable-per-case discipline); each case is its own
process.
"""

# --- CDM (compute) relocation + link/chain-grammar cases -------------------
# grid/tg are fixed at (64,1,1)/(32,1,1) by harness/cmdprobe.m; not a param.
CDM_CASES = [
    {"name": "cdm_baseline", "count": 1500, "prior_queues": 0, "pad_count": 0, "pad_bytes": 0},
    {"name": "cdm_pq4", "count": 2, "prior_queues": 4, "pad_count": 0, "pad_bytes": 0},
    {"name": "cdm_pad_small", "count": 1500, "prior_queues": 0, "pad_count": 8, "pad_bytes": 4096},
    {"name": "cdm_pad_big", "count": 1500, "prior_queues": 0, "pad_count": 16, "pad_bytes": 4194304},
]
CDM_BASELINE_NAME = "cdm_baseline"

# --- VDM (render/draw) relocation + link/chain-grammar cases ---------------
VDM_CASES = [
    {"name": "vdm_baseline", "count": 700, "prior_queues": 0, "prior_draws": 0, "pad_count": 0, "pad_bytes": 0},
    {"name": "vdm_pqdraw4", "count": 10, "prior_queues": 4, "prior_draws": 1, "pad_count": 0, "pad_bytes": 0},
    {"name": "vdm_pad_big", "count": 700, "prior_queues": 0, "prior_draws": 0, "pad_count": 16, "pad_bytes": 4194304},
]
VDM_BASELINE_NAME = "vdm_baseline"

# --- State-packet-schema cases (one Metal state parameter changed at a
# time vs state_baseline; small, fixed draw count) --------------------------
STATE_CASES = [
    {"name": "state_baseline", "count": 4, "depth_test": 0, "stencil_test": 0, "blend": 0, "cull": "none"},
    {"name": "state_depth", "count": 4, "depth_test": 1, "stencil_test": 0, "blend": 0, "cull": "none"},
    {"name": "state_stencil", "count": 4, "depth_test": 0, "stencil_test": 1, "blend": 0, "cull": "none"},
    {"name": "state_blend", "count": 4, "depth_test": 0, "stencil_test": 0, "blend": 1, "cull": "none"},
    {"name": "state_cull_back", "count": 4, "depth_test": 0, "stencil_test": 0, "blend": 0, "cull": "back"},
    {"name": "state_all", "count": 4, "depth_test": 1, "stencil_test": 1, "blend": 1, "cull": "back"},
]
STATE_BASELINE_NAME = "state_baseline"

# --- P0.7 container / metadata field survey (archive-only, no dispatch) ----
CONTAINER_CASES = [
    {"name": "container_kbuf0", "file": "kbuf0.metal", "function": "kbuf0"},
    {"name": "container_kbuf1", "file": "kbuf1.metal", "function": "kbuf1"},
    {"name": "container_kbuf2", "file": "kbuf2.metal", "function": "kbuf2"},
    {"name": "container_kbuf4", "file": "kbuf4.metal", "function": "kbuf4"},
    {"name": "container_kbuf8", "file": "kbuf8.metal", "function": "kbuf8"},
    {"name": "container_ktex0_samp0", "file": "ktex0_samp0.metal", "function": "ktex0_samp0"},
    {"name": "container_ktex1_samp0", "file": "ktex1_samp0.metal", "function": "ktex1_samp0"},
    {"name": "container_ktex1_samp1", "file": "ktex1_samp1.metal", "function": "ktex1_samp1"},
    {"name": "container_ktex2_samp1", "file": "ktex2_samp1.metal", "function": "ktex2_samp1"},
    {"name": "container_ktex4_samp2", "file": "ktex4_samp2.metal", "function": "ktex4_samp2"},
    {"name": "container_kpress4", "file": "kpress4.metal", "function": "kpress4"},
    {"name": "container_kpress32", "file": "kpress32.metal", "function": "kpress32"},
    {"name": "container_kpress96", "file": "kpress96.metal", "function": "kpress96"},
]

# --- P0.7 live cross-check: dispatch a subset of the buffer-count kernels
# and compare the LIVE CDM record + argument table against the archive
# metadata survey (firmware-consumed vs archive-bookkeeping split). ---------
CONTAINER_LIVE_CASES = [
    {"name": "live_kbuf0", "file": "kbuf0.metal", "function": "kbuf0", "nbuf": 0},
    {"name": "live_kbuf1", "file": "kbuf1.metal", "function": "kbuf1", "nbuf": 1},
    {"name": "live_kbuf2", "file": "kbuf2.metal", "function": "kbuf2", "nbuf": 2},
    {"name": "live_kbuf4", "file": "kbuf4.metal", "function": "kbuf4", "nbuf": 4},
    {"name": "live_kbuf8", "file": "kbuf8.metal", "function": "kbuf8", "nbuf": 8},
]

ALL_CASE_NAMES = ([c["name"] for c in CDM_CASES] + [c["name"] for c in VDM_CASES]
                  + [c["name"] for c in STATE_CASES] + [c["name"] for c in CONTAINER_CASES]
                  + [c["name"] for c in CONTAINER_LIVE_CASES])

assert len(ALL_CASE_NAMES) == len(set(ALL_CASE_NAMES)), "duplicate case name in matrix"
