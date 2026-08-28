"""EXP-0124 frozen case matrix. Pure data + generator, no device/filesystem access at
import time (mirrors EXP-0098's harness/casematrix.py convention). Every entry:
  {"id": <unique str>, "family": <Q or I family name>, "kind": <run.py dispatch key>,
   "params": {...}}

Two groups:
  Q* -- P1.6 / DRV-QUERY-01  (counter heap, occlusion queries, pipeline statistics)
  I* -- P1.7 / DRV-INDIRECT-01 (indirect CDM, writable ICB grammar, barriers, restart)

`i_icbmax` (the maxCommandCount crash-boundary bisection) is NOT in this fixed matrix --
it is an adaptive (but fully deterministic, given fixed hardware behavior) bisection
implemented separately in run.py's `run_icbmax_bisect()` / `harness/icbmax_bisect.py`,
because the CODEX boundary-mapping mandate for this specific already-bracketed cliff
(EXP-0098 h_icbmax) calls for narrowing an interval, not sampling a fixed pre-guessed list.
See PRE_REGISTRATION.md H-I6 and README.md.
"""

MATRIX = []


def _add(case_id, family, kind, params):
    for c in MATRIX:
        if c["id"] == case_id:
            raise ValueError(f"duplicate case id {case_id}")
    MATRIX.append({"id": case_id, "family": family, "kind": kind, "params": dict(params)})


# ---------------------------------------------------------------------------
# Group Q -- P1.6 counter heap / occlusion / pipeline-statistics
# ---------------------------------------------------------------------------

_add("q_caps_census", "q_caps", "q_caps", {})

# q_alloc: sampleCount sweep, storageMode=Shared unless noted. Chosen to bracket a
# plausible cliff without gratuitous crash risk (17.18e9-byte host RAM; 2^26 samples *
# 8 B/sample ~ 512 MiB is the largest "plausible working" point tested, 2^40 is a
# deliberately-absurd point expected to be rejected gracefully, not crash).
for i, sc in enumerate([0, 1, 2, 4, 16, 1024, 2048, 4096, 8192, 16384, 32768,
                        65536, 1 << 20, 1 << 24, 1 << 26]):
    _add(f"q_alloc_sweep_{i:02d}_{sc}", "q_alloc", "q_alloc_sweep",
         {"sampleCount": sc, "storageMode": "shared"})
_add("q_alloc_sweep_absurd", "q_alloc", "q_alloc_sweep",
     {"sampleCount": 1 << 40, "storageMode": "shared"})

_add("q_alloc_mode_shared_ctrl", "q_alloc", "q_alloc_mode", {"storageMode": "shared"})
# Build-time finding: resolveCounterRange: on a Private-storage-mode sample buffer
# SIGSEGVs uncatchably (matches the header's documented Shared-only precondition,
# but as an unrecoverable crash rather than a graceful rejection) -- expected here.
_add("q_alloc_mode_private", "q_alloc", "q_alloc_mode",
     {"storageMode": "private", "expect_crash": True})
_add("q_alloc_mode_managed", "q_alloc", "q_alloc_mode", {"storageMode": "managed"})

# q_avail: availability sentinel at three points in the command-buffer lifecycle.
_add("q_avail_pre_commit", "q_avail", "q_avail", {"point": "pre_commit"})
_add("q_avail_post_commit_unwaited", "q_avail", "q_avail", {"point": "post_commit_unwaited"})
_add("q_avail_post_completed", "q_avail", "q_avail", {"point": "post_completed"})

# q_reset: is resolve destructive/idempotent, is index-reuse an overwrite.
_add("q_reset_resolve_idempotent", "q_reset", "q_reset_idempotent", {})
_add("q_reset_index_reuse_overwrite", "q_reset", "q_reset_reuse", {})

# q_copy: GPU-side resolveCounters: (blit) vs CPU-side resolveCounterRange:
_add("q_copy_gpu_matches_cpu", "q_copy", "q_copy_match", {})
_add("q_copy_samecb_hazard", "q_copy", "q_copy_samecb_hazard", {})
_add("q_copy_oob_range", "q_copy", "q_copy_oob", {})

# q_simul: concurrent counter sample buffers.
_add("q_simul_two_buffers_one_encoder", "q_simul", "q_simul_two_in_encoder", {})
# n sweeps the per-encoder sampleBufferAttachments slot count to map the discovered
# 4-slot cliff (n=4 works, n=5 hits a hard CPU-side assertion abort -- build-time
# finding).
for n in (1, 2, 3, 4):
    _add(f"q_simul_many_buffers_one_encoder_n{n}", "q_simul", "q_simul_many_in_encoder", {"n": n})
_add("q_simul_many_buffers_one_encoder_n5_overlimit", "q_simul", "q_simul_many_in_encoder",
     {"n": 5, "expect_abort": True})
_add("q_simul_two_queues_concurrent", "q_simul", "q_simul_two_queues", {})

# q_occmode: counting vs boolean, overlap precision, zero coverage.
_add("q_occ_counting_single", "q_occmode", "q_occmode", {"mode": "counting", "overlap": 1})
_add("q_occ_counting_overlap2x", "q_occmode", "q_occmode", {"mode": "counting", "overlap": 2})
_add("q_occ_boolean_single", "q_occmode", "q_occmode", {"mode": "boolean", "overlap": 1})
_add("q_occ_boolean_overlap2x", "q_occmode", "q_occmode", {"mode": "boolean", "overlap": 2})
_add("q_occ_zero_coverage", "q_occmode", "q_occmode_zero", {"mode": "counting"})

# q_occoverwrite: same-offset reuse within one encoder.
_add("q_occ_overwrite_same_offset", "q_occoverwrite", "q_occoverwrite", {"variant": "same_offset"})
_add("q_occ_overwrite_disabled_between", "q_occoverwrite", "q_occoverwrite", {"variant": "disabled_between"})
_add("q_occ_overwrite_distinct_offsets_ctrl", "q_occoverwrite", "q_occoverwrite", {"variant": "distinct_offsets"})

# q_tick: counter-heap timestamp vs public sampleTimestamps cross-check.
_add("q_tick_crosscheck", "q_tick", "q_tick", {})


# ---------------------------------------------------------------------------
# Group I -- P1.7 indirect CDM / writable ICB grammar / barriers / restart
# ---------------------------------------------------------------------------

_add("i_cdm_axis_order_proof", "i_cdmfmt", "i_cdm_axisproof", {})
for axis in ("x", "y", "z"):
    _add(f"i_cdm_zero_{axis}", "i_cdmfmt", "i_cdm_zeroaxis", {"zero_axis": axis})
_add("i_cdm_tiny_1_1_1", "i_cdmfmt", "i_cdm_sweep", {"x": 1, "y": 1, "z": 1})
_add("i_cdm_typical_8_8_1", "i_cdmfmt", "i_cdm_sweep", {"x": 8, "y": 8, "z": 1})
_add("i_cdm_boundary_65535", "i_cdmfmt", "i_cdm_sweep", {"x": 65535, "y": 1, "z": 1})
_add("i_cdm_boundary_65536", "i_cdmfmt", "i_cdm_sweep", {"x": 65536, "y": 1, "z": 1})
_add("i_cdm_large_1m", "i_cdmfmt", "i_cdm_sweep", {"x": 1 << 20, "y": 1, "z": 1})
_add("i_cdm_large_16m", "i_cdmfmt", "i_cdm_sweep", {"x": 1 << 24, "y": 1, "z": 1})
_add("i_cdm_misaligned_offset", "i_cdmfmt", "i_cdm_offset", {"indirectBufferOffset": 2})

_add("i_icbw_basic_render_n8", "i_icbwrite", "i_icbw_basic", {"n": 8})
_add("i_icbw_reset_after_encode", "i_icbwrite", "i_icbw_reset", {"n": 4, "reset_idx": 1})
for i, (vc, ic, vs, bi) in enumerate([
        (0, 1, 0, 0), (1, 1, 0, 0), (8, 0, 0, 0), (8, 1000, 0, 0),
        (8, 1, 10, 0), (8, 1, 0, 500)]):
    _add(f"i_icbw_fields_{i:02d}", "i_icbwrite", "i_icbw_fields",
         {"vertexCount": vc, "instanceCount": ic, "vertexStart": vs, "baseInstance": bi})
_add("i_icbw_inherit_buffers_yes", "i_icbwrite", "i_icbw_inherit_yes", {})
_add("i_icbw_indexed", "i_icbwrite", "i_icbw_indexed", {"n": 4})
_add("i_icbw_oob_command_index", "i_icbwrite", "i_icbw_oob_index",
     {"maxCommandCount": 4, "dispatched_threads": 8})

for t in range(8):
    _add(f"i_icbb_barrier_t{t}", "i_icbbarrier", "i_icbb_trial",
         {"barrier": True, "trial": t})
for t in range(8):
    _add(f"i_icbb_nobarrier_t{t}", "i_icbbarrier", "i_icbb_trial",
         {"barrier": False, "trial": t})

_add("i_restart_strip_sentinel32", "i_restart", "i_restart",
     {"topology": "strip", "idxbits": 32})
_add("i_restart_strip_sentinel16", "i_restart", "i_restart",
     {"topology": "strip", "idxbits": 16})
_add("i_restart_point_sentinel_ctrl", "i_restart", "i_restart",
     {"topology": "point", "idxbits": 32})


TOTAL = len(MATRIX)


def nondeterministic_observed_keys(case):
    """Gate (d): which keys inside a case's gated `observed` dict are legitimately
    allowed to differ between two otherwise-identical runs, because they record a
    genuinely racy GPU-scheduling outcome rather than a deterministic hardware fact.
    Only i_icbb_trial's unbarriered (barrier=False) rows qualify -- every other case
    in this matrix is expected to be byte-identical across runs on the same pinned
    revision. Matches EXP-0098's h_sync exclusion-list convention.
    """
    if case["kind"] == "i_icbb_trial" and not case["params"].get("barrier", True):
        return {"result", "correct"}
    return set()


def by_family():
    out = {}
    for c in MATRIX:
        out.setdefault(c["family"], []).append(c)
    return out


if __name__ == "__main__":
    fams = by_family()
    for fam, cs in fams.items():
        print(f"{fam}: {len(cs)}")
    print(f"TOTAL {TOTAL}")
