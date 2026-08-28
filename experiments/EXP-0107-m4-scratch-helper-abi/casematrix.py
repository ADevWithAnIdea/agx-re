#!/usr/bin/env python3
"""EXP-0107 case matrix -- the single source of truth for run.py, verify.py,
and analysis/*.py. Import, never restate.

Five families, each a single-variable ladder from a documented reference
point (CODEX.md Sec.3/5 "one variable per case"):

  K  -- CS pressure ladder (array-loop kernels, n=1). K = elements of the
        `thread float a[K]` array. Reference/no-spill control: K=8, K=32.
        Escalates by roughly-doubling steps from clearly-no-spill (K=8/32)
        through clearly-spilling (K=96..49152) to the exact HW-located
        compile-time boundary (K=65430 last known-good, K=65440 first
        known-fail from this experiment's own pre-flight reconnaissance,
        recorded in PRE_REGISTRATION.md -- both re-captured fresh here as
        gated evidence, not asserted from that reconnaissance).
  S  -- stage variation (VS, FS) at three of the K family's own levels
        (96/1536/6144), otherwise identical kernel design.
  O  -- occupancy/topology ladder: K fixed at 1536 (a clearly-spilling K
        family level, reused as O's own zero point), CS only, n=1;
        (grid, tg) varies by orders of magnitude and by threadgroup shape.
  X  -- compound stress: high K together with the largest tested grid, to
        ask whether aggregate (K_bytes x total_threads) demand adds a
        SEPARATE failure boundary beyond the per-thread K-family ceiling.
  H  -- hot execution: n>1 (genuine repeated spill/fill traffic across many
        passes), not just the degenerate n=1 init+reduce check.

Escalation policy (enforced by run.py, not here): within families K/O/X
(ordered ascending risk), a family's ladder STOPS -- later entries are
recorded SKIPPED, never executed -- after the first entry whose probe
status is not "OK" (K's own boundary pair is an intentional, expected
exception: the ladder is allowed exactly one more entry past a clean
PIPELINE_FAIL/COMPILE_FAIL, to capture the immediate post-boundary case,
but stops unconditionally on a TIMEOUT or unexpected exception anywhere).
A TIMEOUT or exception in ANY case, in ANY family, aborts the entire
remaining run (all later families too) -- see run.py.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
KDIR = HERE / "kernels"

# ---------------------------------------------------------------------------
# K family: CS pressure ladder, n=1, reference occupancy (grid=64, tg=32).
# ---------------------------------------------------------------------------
K_LEVELS = (8, 32, 96, 192, 384, 768, 1536, 3072, 6144, 12288, 24576, 49152,
           65430, 65440)
K_CASES = [
    {"name": f"K_cs_k{k}", "family": "K", "stage": "cs", "k": k,
     "source": f"cs_k{k}.metal", "grid": 64, "tg": 32, "n": 1}
    for k in K_LEVELS
]

# ---------------------------------------------------------------------------
# S family: stage variation at three shared K levels.
# ---------------------------------------------------------------------------
S_K_LEVELS = (96, 1536, 6144)
S_CASES = []
for k in S_K_LEVELS:
    for stage in ("vs", "fs"):
        S_CASES.append({"name": f"S_{stage}_k{k}", "family": "S", "stage": stage, "k": k,
                        "source": f"{stage}_k{k}.metal", "grid": None, "tg": None, "n": 1})

# ---------------------------------------------------------------------------
# O family: occupancy/topology ladder at fixed K=1536 (reuses K family's own
# cs_k1536.metal source -- no new kernel). Ascending risk order.
# ---------------------------------------------------------------------------
O_K = 1536
O_SHAPES = (
    (1024, 32), (32768, 32), (1048576, 32), (32768, 256), (32768, 1024),
    (4194304, 256),
)
O_CASES = [
    {"name": f"O_cs_k{O_K}_g{g}_t{t}", "family": "O", "stage": "cs", "k": O_K,
     "source": f"cs_k{O_K}.metal", "grid": g, "tg": t, "n": 1}
    for g, t in O_SHAPES
]

# ---------------------------------------------------------------------------
# X family: compound stress (high per-thread K x large total thread count).
# Ascending risk order.
# ---------------------------------------------------------------------------
X_CASES = [
    {"name": "X_cs_k49152_g1048576", "family": "X", "stage": "cs", "k": 49152,
     "source": "cs_k49152.metal", "grid": 1048576, "tg": 256, "n": 1},
    {"name": "X_cs_k65430_g4194304", "family": "X", "stage": "cs", "k": 65430,
     "source": "cs_k65430.metal", "grid": 4194304, "tg": 256, "n": 1},
]

# ---------------------------------------------------------------------------
# H family: hot execution, n>1, genuine repeated spill/fill traffic.
# ---------------------------------------------------------------------------
H_CASES = [
    {"name": "H_cs_k1536_n1000", "family": "H", "stage": "cs", "k": 1536,
     "source": "cs_k1536.metal", "grid": 1024, "tg": 32, "n": 1000},
    {"name": "H_cs_k6144_n200", "family": "H", "stage": "cs", "k": 6144,
     "source": "cs_k6144.metal", "grid": 256, "tg": 32, "n": 200},
]

ALL_CASES = K_CASES + S_CASES + O_CASES + X_CASES + H_CASES
for _i, _c in enumerate(ALL_CASES):
    _c["i"] = _i
NAMES = [c["name"] for c in ALL_CASES]
assert len(NAMES) == len(set(NAMES)), "duplicate case name"

FAMILIES_ESCALATING = ("K", "O", "X")  # stop-on-first-non-OK ladders
K_BOUNDARY_GRACE = 1  # K family may run exactly one case past first non-OK

# Every .metal source any case references must exist once kernels/generate.py
# has run; used by verify.py's static checks and run.py's preflight.
REQUIRED_SOURCES = sorted({c["source"] for c in ALL_CASES})

# Timeouts (seconds), escalating with the case's own risk profile. Chosen
# from this experiment's own pre-registration-stage reconnaissance timings
# (compile <1s regardless of K; the largest X-family dispatch measured
# ~38s), with a wide safety margin.
TIMEOUTS = {
    "metadata": 150,     # shdump compile + own-archive metadata parse
    "probe_default": 60,  # K/S families, small O entries
    "probe_high_occupancy": 150,  # O/X entries with grid >= 32768
    "smoke": 60,
    "env_command": 30,
}


def probe_timeout(case):
    if case["family"] in ("O", "X") and (case["grid"] or 0) >= 32768:
        return TIMEOUTS["probe_high_occupancy"]
    return TIMEOUTS["probe_default"]


# ---------------------------------------------------------------------------
# Gated (cross-run byte-compared) schema. NOTHING here may be a raw GPU
# address, wall-clock time, or other quantity this project has observed (or
# been warned) to vary run-to-run; those live only in TIMING_KEYS / raw logs.
# ---------------------------------------------------------------------------
CASE_KEYS = {
    "i", "name", "family", "stage", "k", "grid", "tg", "n", "source",
    "executed",                       # False if skipped by escalation policy
    "meta_exit", "meta_timed_out", "meta_status",
    "gpr_field_0", "scratch_field_41_or_14", "all_u32_fields",
    "main_bytes", "main_sha256",
    "probe_exit", "probe_timed_out", "probe_status", "probe_detail",
    "checksum",
    "resource_map_shape",   # sorted [{class,size,count}], NO va
    "bo_count", "bo_total_bytes",
    "bo_content_seq_sha256",  # sha256 of first-seen-order (class,size,prefix) tuples
}
TIMING_KEYS = {
    "i", "name", "meta_duration_ms", "probe_duration_ms",
    "meta_stdout", "meta_stderr", "probe_stdout", "probe_stderr",
    "maptrace_log_lines",
}

# `bo_content_seq_sha256` is a field of CASE_KEYS (so schema-exactness and
# selftest's injected-defect checks still cover it) but is EXCLUDED from the
# cross-run byte-gate. This is not a design assumption: EXP-0107's own two
# real captures (run01/run02, both fully reproducible in every OTHER
# CASE_KEYS field for all 30/30 cases) found this field itself differs on
# 9/30 cases -- clustered in some render-stage (S) cases and every case with
# either grid >= 1,048,576 or n > 1 (O/X/H) -- while `resource_map_shape`,
# `bo_count`, `bo_total_bytes`, `scratch_field_41_or_14`, `gpr_field_0`, and
# `checksum` reproduced exactly in all 30/30. This is a genuine, newly-
# discovered nondeterministic field (almost certainly execution-timing- or
# scheduling-dependent incidental bytes inside one or two specific BOs, not
# a GPU address), and is handled exactly as the standing gate requires:
# excluded from the gated payload, with the exclusion itself proven by a
# dedicated verify.py --selftest case (see RESULTS.md Sec. "Cross-run
# reproducibility").
NONDETERMINISTIC_CASE_KEYS = {"bo_content_seq_sha256"}
GATED_CASE_KEYS = CASE_KEYS - NONDETERMINISTIC_CASE_KEYS
