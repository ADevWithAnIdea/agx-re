"""EXP-0136 gated/nongated record schema (mirrors sibling EXPs, e.g. EXP-0123)."""

GATED_KEYS = {"case_id", "family", "kind", "params", "status", "verdict", "observed"}
NONGATED_KEYS = {"case_id", "gputime_ns", "wall_ms", "pid", "raw_tail"}

FAMILIES = {"aniso", "addrmode", "border", "swizzle", "restart", "norender", "opcode"}

# Fields inside `observed` that are confirmed, genuine run-to-run
# nondeterminism -- NOT stripped from the record (still fully visible/
# auditable in 02_gated.jsonl for every run) but excluded from the strict
# cross-run byte-equality gate. Established empirically by the two official
# runs of THIS experiment (mirrors the precedent in EXP-0123/EXP-0098's own
# single nondeterministic field, gputime_ns, which lives inside `observed`
# too and is excluded from cross_run_gate the same way):
#   - n_bos_loaded: the tools/iotrace BO-registration count observed at
#     descpatch.m's dump instant genuinely varies run to run (process/
#     allocator/compiler-cache timing outside this experiment's control),
#     confirmed differing between m4_20260828_run01 and _run02 for several
#     cases while every hardware-fact field (patched bytes, pixel, status)
#     matched exactly.
#   - error / error_patched: the OS/Metal fault-classification STRING for a
#     genuine GPU hang can read as either "Caused GPU Hang Error
#     (...ErrorHang)" or "Discarded (victim of GPU error/recovery)
#     (...ErrorInnocentVictim)" depending on scheduling relative to other
#     in-flight work -- confirmed differing between the two official runs for
#     swizzle_comp0_code6/code7 (both faulted -- status=CMDBUF_ERROR matched
#     exactly both runs -- only the sub-classification text differed). The
#     invariant gated on is `status`; the raw text stays in `observed` as an
#     un-gated diagnostic.
NONDET_OBSERVED_KEYS = {"n_bos_loaded", "error", "error_patched"}


def validate_gated(rec):
    if set(rec.keys()) != GATED_KEYS:
        return False, f"gated record keys {set(rec.keys())} != {GATED_KEYS}"
    if rec["family"] not in FAMILIES:
        return False, f"unknown family {rec['family']}"
    if rec["verdict"] not in ("PASS", "FAIL", "TIMEOUT"):
        return False, f"bad verdict {rec['verdict']}"
    return True, "ok"
