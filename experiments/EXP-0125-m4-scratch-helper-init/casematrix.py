#!/usr/bin/env python3
"""EXP-0125 case matrix -- single source of truth for run.py, verify.py, and
analysis/*.py. Import, never restate.

Three families, one per hypothesis pair from the dispatch brief:

  I -- INIT-TIME CHECKPOINT (H1 + H2). Two process variants ("nospill",
       "spill"), each walking the SAME six lifecycle checkpoints
       (DEVICE_CREATED, QUEUE_CREATED, PIPELINE1_CREATED, PIPELINE2_CREATED,
       PRE_DISPATCH, POST_DISPATCH -- harness/initprobe.m). Only the SECOND
       pipeline and the final dispatch differ (trivial vs a real K=24576
       array-loop spill kernel); everything else is identical, so any BO
       that appears/changes ONLY in the spill variant, at ANY checkpoint --
       especially before dispatch -- is the H1 signal. harness/inittrace.c
       captures a full (class,gpu_va,size) resource-map + bounded content
       prefix of every BO the process has registered at each checkpoint,
       plus a best-effort read of the two selector-5 "shared pages" CPU
       pointers (H2's second search target: the code window / any
       executable-shaped region).

  B -- COMPILE-TIME CEILING BISECTION (H3). Deterministic binary search
       over K (array-loop element count, == mesa's compiler-accounting
       "scratch dwords" unit almost 1:1: our declared bytes = 4K+16) for
       each of CS/VS/FS independently, using harness/ceiling.m (compile +
       pipeline-creation only, no dispatch -- EXP-0107 Sec.4 already showed
       the ceiling is a pure compile-time property). Bracket
       [K_LOW, K_HIGH] is anchored explicitly at K_HIGH = mesa's own
       AGX_MAX_SCRATCH_DWORDS (131072) -- not because we assume the mesa
       constant applies to Apple9, but because it is the most principled
       available "does the compile ceiling reach as high as mesa's Linux-
       driver constant, or not" search target the dispatch calls for.
       Deterministic: given fixed bracket + a reproducible hardware oracle,
       the exact SEQUENCE of trial K values is reproducible run-to-run, so
       cross-run gating compares the full trial list, not just an endpoint.

  C -- CONCURRENT EXHAUSTION (H4). Escalating count of MTLCommandQueues
       (harness/concurrent.m), ALL committed before ANY is awaited, each
       running the SAME heavy-but-EXP-0107-validated-safe K=24576 kernel at
       a moderate grid. REVISED DURING THIS EXPERIMENT'S OWN PRE-CAPTURE
       RECONNAISSANCE (see PRE_REGISTRATION.md addendum #2): an initial
       single-trial-per-level design found the failure mode is NOT a clean
       monotonic "N and above always fails" wall -- repeated trials at the
       SAME n_queues (e.g. n_queues=4) sometimes ran 8/8 clean and sometimes
       showed a real EXEC_FAIL/checksum-mismatch cascade in the same short
       session. This is itself the H4 finding (an intermittent, low-
       frequency degradation, not a hard capacity boundary), so the design
       now runs C_REPEATS independent trials per level (no escalation-stop:
       a single flake at a low level must not truncate the higher-level
       data) and reports the PER-LEVEL FAILURE RATE, not a single pass/fail.
       Per-trial outcome fields (status/ok_queues/execfail_queues/
       nonfinite_queues/checksum_mismatch) are therefore NONDETERMINISTIC by
       this experiment's own direct observation and excluded from the
       cross-run byte-exact gate (GATED_C_TRIAL_KEYS), exactly as EXP-0107
       excluded `bo_content_seq_sha256` -- present in the schema (so an
       extra/missing key is still caught), but not required to match run01
       vs run02 exactly. Only a hard fault (timeout, process crash/non-0/1
       exit) aborts the run early -- that remains a genuine safety stop.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
KDIR = HERE / "kernels"

# ---------------------------------------------------------------------------
# I family
# ---------------------------------------------------------------------------
I_VARIANTS = ("nospill", "spill")
CHECKPOINT_LABELS = ("DEVICE_CREATED", "QUEUE_CREATED", "PIPELINE1_CREATED",
                     "PIPELINE2_CREATED", "PRE_DISPATCH", "POST_DISPATCH")
I_K = 24576  # matches kernels/kernelgen.py FIXED_K; must stay in sync (checked by verify.static())
I_GRID = 65536
I_TG = 256

I_CASES = [{"name": f"I_{v}", "family": "I", "variant": v} for v in I_VARIANTS]

# ---------------------------------------------------------------------------
# B family: deterministic bisection.
# ---------------------------------------------------------------------------
B_STAGES = ("cs", "vs", "fs")
K_LOW = 1024        # established OK for CS by EXP-0107 (K up to 49152 OK); re-verified fresh here for all 3 stages
K_HIGH = 131072      # == mesa's AGX_MAX_SCRATCH_DWORDS (agx_scratch.c) -- explicit H3 search target
K_BRACKET_HARDCAP = 400000   # safety ceiling for bracket-escalation if K_HIGH itself still succeeds
BISECT_STOP_WIDTH = 1        # stop when hi-lo <= this (adjacent-K resolution)


def run_bisection(oracle, k_low=K_LOW, k_high=K_HIGH, hardcap=K_BRACKET_HARDCAP):
    """Deterministic K-bisection. `oracle(k) -> bool` (True = pipeline
    creation succeeded). Returns (trials, result) where `trials` is the
    ordered list of {step, phase, k, ok} dicts (phase "bracket" or
    "bisect") and `result` is {"bracket_ok": bool, "k_low": int,
    "k_high": int, "last_ok": int|None, "first_fail": int|None}.

    Purely a function of `oracle`'s outputs and the fixed constants above --
    given the same oracle behavior, this always emits the same trial
    sequence, which is what makes B-family cross-run byte-comparison
    meaningful (see casematrix.py module docstring).
    """
    trials = []
    step = [0]

    def trial(phase, k):
        ok = oracle(k)
        trials.append({"step": step[0], "phase": phase, "k": k, "ok": ok})
        step[0] += 1
        return ok

    lo, hi = k_low, k_high
    ok_lo = trial("bracket", lo)
    if not ok_lo:
        # k_low itself fails -- no valid bracket at all; report and stop.
        return trials, {"bracket_ok": False, "k_low": lo, "k_high": hi,
                        "last_ok": None, "first_fail": lo}
    ok_hi = trial("bracket", hi)
    while ok_hi and hi < hardcap:
        lo = hi
        hi = min(hardcap, hi * 2)
        if hi == lo:
            break
        ok_hi = trial("bracket", hi)
    if ok_hi:
        # Even the hardcap succeeds: no ceiling found in the tested range.
        return trials, {"bracket_ok": True, "k_low": lo, "k_high": hi,
                        "last_ok": hi, "first_fail": None}

    while hi - lo > BISECT_STOP_WIDTH:
        mid = lo + (hi - lo) // 2
        if trial("bisect", mid):
            lo = mid
        else:
            hi = mid

    return trials, {"bracket_ok": True, "k_low": k_low, "k_high": k_high,
                    "last_ok": lo, "first_fail": hi}


# ---------------------------------------------------------------------------
# C family: concurrent-queue escalation ladder.
# ---------------------------------------------------------------------------
C_LEVELS = (1, 2, 4, 8, 16, 32)
C_REPEATS = 6         # independent trials per level -- see module docstring
C_K = 24576          # == I_K, EXP-0107-validated safe/correct, reuses cs_k24576.metal
C_GRID = 65536
C_TG = 256

# ---------------------------------------------------------------------------
# Timeouts (seconds).
# ---------------------------------------------------------------------------
TIMEOUTS = {
    "i_probe": 90,
    "b_trial": 30,
    "c_probe_base": 30,       # + per-queue margin, see c_timeout()
    "c_probe_per_queue": 6,
    "smoke": 60,
    "env_command": 30,
}


def c_timeout(n_queues):
    return TIMEOUTS["c_probe_base"] + TIMEOUTS["c_probe_per_queue"] * n_queues


# ---------------------------------------------------------------------------
# Gated (cross-run byte-compared) schemas. NOTHING here may be a raw GPU
# address, a wall-clock timestamp, or mach_absolute_time (mach_time is
# monotonic and process-relative but not reproducible run-to-run in exact
# value -- it lives only in the ungated ..._raw records / checkpoints logs).
# ---------------------------------------------------------------------------
I_CHECKPOINT_KEYS = {
    "case", "variant", "cp_idx", "cp_label",
    "nbo", "bo_total_bytes", "resource_map_shape",   # address-free
    "nshared", "shared_addr0_present", "shared_addr1_present",
    "code_window_present", "code_window_size",         # VA 0x10000000000, EXP-0042/0108 convention
}
I_SUMMARY_KEYS = {
    "case", "variant", "probe_exit", "probe_timed_out", "probe_status", "checksum",
}
B_TRIAL_KEYS = {"stage", "step", "phase", "k", "ok"}
B_RESULT_KEYS = {"stage", "bracket_ok", "k_low", "k_high", "last_ok", "first_fail", "n_trials"}

# Full per-trial schema (used for schema-exactness: an extra/missing key is
# always caught). Only C_GATED_TRIAL_KEYS is required to match byte-for-byte
# run01 vs run02 -- status/ok_queues/execfail_queues/nonfinite_queues/
# checksum_mismatch are this experiment's own directly-observed
# nondeterministic fields (module docstring), the C-family analogue of
# EXP-0107's `bo_content_seq_sha256` exclusion.
C_TRIAL_KEYS = {
    "name", "n_queues", "trial", "executed", "exit", "timed_out",
    "status", "ok_queues", "execfail_queues", "nonfinite_queues", "checksum_mismatch",
}
C_NONDETERMINISTIC_TRIAL_KEYS = {
    "status", "ok_queues", "execfail_queues", "nonfinite_queues", "checksum_mismatch",
}
C_GATED_TRIAL_KEYS = C_TRIAL_KEYS - C_NONDETERMINISTIC_TRIAL_KEYS

TIMING_KEYS = {
    "record", "duration_ms", "stdout", "stderr",
}
