#!/usr/bin/env python3
"""EXP-0085 frozen case matrix -- the single authoritative source for run.py,
analysis.py, and verify.py. Never restate this list anywhere else.

Each case is one process invocation of one harness binary. Families:
  atomic          -> harness/atomics_probe   (kernels/atomics.metal)
  ordering_probe  -> harness/atomics_probe   (kernels/atomics_ordering.metal)
  interlock       -> harness/interlock_probe (kernels/interlock.metal)
  interlock_tex   -> harness/interlock_tex_probe (kernels/interlock_tex.metal)
"""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Per-op init value (device/threadgroup atomic target initial content) and
# ATOM-item tag, frozen so the expected invariant is fully determined by
# (kernel, dtype, addr, n, init) with no hidden state.
# ---------------------------------------------------------------------------
RMW_INIT = {
    "da_add": "00000000", "da_sub": "00000000",
    "da_and": "ffffffff", "da_or": "00000000", "da_xor": "00000000",
    "da_umin": "ffffffff", "da_umax": "00000000",
    "da_smin": "ffffff7f", "da_smax": "00000080",  # little-endian INT32_MAX / INT32_MIN
    "da_fadd": "00000000",
    "da_add_static0": "00000000", "da_xor_static0": "00000000", "da_umin_static0": "ffffffff",
    # threadgroup-scope RMW: init is hardcoded inside kernels/atomics.metal's
    # threadgroup array fill (lane 0's loop before the barrier) -- mirrored
    # here verbatim so analysis.py can recompute the expected combine without
    # re-parsing the kernel source. u32 little-endian hex.
    "ta_add": "00000000", "ta_sub": "40420f00",  # 1,000,000 little-endian
    "ta_min": "ffffffff", "ta_max": "00000000",
    "da_umin64": "ffffffffffffffff", "da_umax64": "0000000000000000",
}
EXCH_INIT = "efbeadde"  # 0xdeadbeef little-endian
CMPXCHG_INIT = "00000000"

ATOM_ITEM = {
    "da_add": "ATOM-01", "da_sub": "ATOM-01", "da_and": "ATOM-01", "da_or": "ATOM-01",
    "da_xor": "ATOM-01", "da_umin": "ATOM-01", "da_umax": "ATOM-01",
    "da_smin": "ATOM-01", "da_smax": "ATOM-01", "da_fadd": "ATOM-01",
    "ta_add": "ATOM-02", "ta_sub": "ATOM-02", "ta_min": "ATOM-02", "ta_max": "ATOM-02",
    "da_exch": "ATOM-03", "da_exch_noret": "ATOM-03", "da_store": "ATOM-03",
    "ta_exch": "ATOM-03",
    "da_cmpxchg": "ATOM-04", "ta_cmpxchg": "ATOM-04",
    "da_add_static0": "ATOM-05/06", "da_xor_static0": "ATOM-05/06",
    "da_umin_static0": "ATOM-05/06", "da_exch_static0": "ATOM-05/06",
    "da_cmpxchg_static0": "ATOM-05/06",
    "da_umin64": "ATOM-01(width)", "da_umax64": "ATOM-01(width)",
    "da_add_seqcst": "ATOM-07(deferred;exposure-only)",
}


def _atomic_case(i, name, kernel, shape, dtype, n, addr, init=None, tcount=None):
    if init is None:
        if shape == "dev_exch" or shape == "tg_exch":
            init = EXCH_INIT
        elif shape == "dev_cmpxchg" or shape == "tg_cmpxchg":
            init = CMPXCHG_INIT
        else:
            init = RMW_INIT.get(kernel, "00000000")
    return {
        "i": i, "family": "atomic", "name": name, "kernel": kernel, "shape": shape,
        "dtype": dtype, "n": n, "addr": addr, "init": init, "tcount": tcount,
        "atom_item": ATOM_ITEM.get(kernel, "?"),
    }


def _interlock_case(i, name, kernel, n, afactor=1):
    return {"i": i, "family": "interlock", "name": name, "kernel": kernel, "n": n,
            "afactor": afactor, "atom_item": "MEM-13/14"}


def _tex_case(i, name, kernel, w, h):
    return {"i": i, "family": "interlock_tex", "name": name, "kernel": kernel,
            "w": w, "h": h, "atom_item": "MEM-13"}


def _ordering_case(i, name, kernel, n):
    return {"i": i, "family": "ordering_probe", "name": name, "kernel": kernel, "n": n,
            "atom_item": "ATOM-07(deferred;exposure-only)"}


def build_matrix():
    m = []
    i = 0
    N_DEV = 65536   # device-scope contention: many threadgroups, real cross-TG contention
    N_TG = 256      # threadgroup-scope: exactly one threadgroup (hardware max tested here)
    N_STATIC = 8192  # static-address reduce-path probe: functional + structural
    N_U64 = 8192

    dev_ops = ["da_add", "da_sub", "da_and", "da_or", "da_xor", "da_umin", "da_umax"]
    for op in dev_ops:
        for addr in ("uniform", "indexed"):
            m.append(_atomic_case(i, f"{op}_{addr}", op, "dev_rmw", "u32", N_DEV, addr)); i += 1
    for op in ("da_smin", "da_smax"):
        for addr in ("uniform", "indexed"):
            m.append(_atomic_case(i, f"{op}_{addr}", op, "dev_rmw", "i32", N_DEV, addr)); i += 1
    for addr in ("uniform", "indexed"):
        m.append(_atomic_case(i, f"da_fadd_{addr}", "da_fadd", "dev_rmw", "f32", N_DEV, addr)); i += 1

    for addr in ("uniform", "indexed"):
        m.append(_atomic_case(i, f"da_exch_{addr}", "da_exch", "dev_exch", "u32", N_DEV, addr)); i += 1
    m.append(_atomic_case(i, "da_exch_noret_uniform", "da_exch_noret", "dev_exch", "u32", N_DEV, "uniform")); i += 1
    m.append(_atomic_case(i, "da_store_uniform", "da_store", "dev_exch", "u32", N_DEV, "uniform")); i += 1

    for addr in ("uniform", "indexed"):
        m.append(_atomic_case(i, f"da_cmpxchg_{addr}", "da_cmpxchg", "dev_cmpxchg", "u32", N_DEV, addr)); i += 1

    for op in ("da_add_static0", "da_xor_static0", "da_umin_static0"):
        m.append(_atomic_case(i, op, op, "dev_rmw", "u32", N_STATIC, "uniform", tcount=1)); i += 1
    m.append(_atomic_case(i, "da_exch_static0", "da_exch_static0", "dev_exch", "u32", N_STATIC, "uniform", tcount=1)); i += 1
    m.append(_atomic_case(i, "da_cmpxchg_static0", "da_cmpxchg_static0", "dev_cmpxchg", "u32", N_STATIC, "uniform", tcount=1)); i += 1

    for op in ("ta_add", "ta_sub", "ta_min", "ta_max"):
        for addr in ("uniform", "indexed"):
            m.append(_atomic_case(i, f"{op}_{addr}", op, "tg_rmw", "u32", N_TG, addr)); i += 1
    for addr in ("uniform", "indexed"):
        m.append(_atomic_case(i, f"ta_exch_{addr}", "ta_exch", "tg_exch", "u32", N_TG, addr)); i += 1
    for addr in ("uniform", "indexed"):
        m.append(_atomic_case(i, f"ta_cmpxchg_{addr}", "ta_cmpxchg", "tg_cmpxchg", "u32", N_TG, addr)); i += 1

    for op in ("da_umin64", "da_umax64"):
        for addr in ("uniform", "indexed"):
            m.append(_atomic_case(i, f"{op}_{addr}", op, "dev_rmw", "u64", N_U64, addr)); i += 1

    m.append(_ordering_case(i, "da_add_seqcst_compile_probe", "da_add_seqcst", 8)); i += 1

    m.append(_interlock_case(i, "il_load_alu", "il_load_alu", 8192)); i += 1
    m.append(_interlock_case(i, "il_gather", "il_gather", 8192)); i += 1
    m.append(_interlock_case(i, "il_atomic_alu", "il_atomic_alu", 8192)); i += 1
    m.append(_interlock_case(i, "il_store_src", "il_store_src", 8192)); i += 1
    m.append(_interlock_case(i, "il_atomic_src", "il_atomic_src", 8192)); i += 1
    m.append(_interlock_case(i, "il_chain48_n4096", "il_chain48", 4096, afactor=48)); i += 1
    m.append(_interlock_case(i, "il_chain48_n65536", "il_chain48", 65536, afactor=48)); i += 1

    m.append(_tex_case(i, "il_tex_alu_64x64", "il_tex_alu", 64, 64)); i += 1

    return m


MATRIX = build_matrix()
TOTAL = len(MATRIX)

# Per-case raw result payload keys, by family. gputime_ns is deliberately
# EXCLUDED here (fenced class (d)): it is captured in a separate, non-gated
# per-run timing file so 04_results.jsonl can never contain a nondeterministic
# field, structurally, not just by comparison-time filtering.
ATOMIC_RESULT_KEYS = {"i", "name", "kernel", "shape", "dtype", "n", "tcount", "addr", "init",
                      "status", "cb_status", "err", "target_final_hex", "old_out_hex",
                      "deltas_hex", "tag_hex", "idx", "success_out", "tg_result_hex",
                      "compile_err"}
INTERLOCK_RESULT_KEYS = {"i", "name", "kernel", "n", "afactor", "status", "cb_status", "err",
                         "out_hex", "atom_final", "compile_err"}
TEX_RESULT_KEYS = {"i", "name", "kernel", "w", "h", "status", "cb_status", "err", "out_hex",
                    "compile_err"}
ORDERING_RESULT_KEYS = {"i", "name", "kernel", "n", "status", "cb_status", "err", "compile_err"}

RESULT_KEYS_BY_FAMILY = {
    "atomic": ATOMIC_RESULT_KEYS,
    "interlock": INTERLOCK_RESULT_KEYS,
    "interlock_tex": TEX_RESULT_KEYS,
    "ordering_probe": ORDERING_RESULT_KEYS,
}

# Per-case process receipt (timing + process bookkeeping; NOT byte-compared
# across runs -- this is where gputime_ns / duration_ms / timestamps live).
RECEIPT_KEYS = {"i", "name", "argv", "cwd", "started_utc", "duration_ms", "exit",
                "timed_out", "gputime_ns"}

STATUS_ALLOWED = {"ok", "compile_fail", "function_missing", "pipeline_fail", "no_device",
                  "read_fail", "cb_error", "proc_fail", "proc_timeout"}


def case_order_sensitive_keys(case):
    """Result-record keys allowed to differ between the two capture runs for
    this case WITHOUT failing the cross-run gate, because they record which
    concurrently-executing lane observed/produced a given value -- a
    legitimate scheduling-order artifact, not evidence of a semantic
    difference (fenced class (d): "per-lane RETURN ORDER may legitimately
    vary run to run; gate on the run-invariant ... record the raw per-lane
    order in a separate non-gated record"). Every other key in the record
    (including target_final_hex/atom_final for the commutative/associative
    RMW ops, and every field of every non-contended case) is fully
    order-INDEPENDENT and therefore stays in the strict byte-identity gate.
    Cases with per-lane exclusive addressing (addr == "indexed", or the tg_rmw
    indexed form) have no real cross-lane contention at any single slot, so
    nothing is excluded even though the kernel is nominally "contention"
    shaped.
    """
    fam = case["family"]
    if fam == "atomic":
        addr = case.get("addr")
        shape = case["shape"]
        if addr != "uniform":
            return set()
        if shape == "dev_rmw":
            return {"old_out_hex"}
        if shape == "dev_exch":
            return {"target_final_hex", "old_out_hex"}
        if shape == "dev_cmpxchg":
            return {"target_final_hex", "old_out_hex", "success_out"}
        if shape == "tg_rmw":
            # tg_result_hex slot 0 IS the commutative/associative combine
            # (order-independent) for every op tested here, so it stays
            # gated; only the per-lane old_out is scheduling-order-dependent.
            return {"old_out_hex"}
        if shape == "tg_exch":
            # the threadgroup array's final content (tg_result_hex) depends
            # on which lane wrote last -- order-sensitive, unlike dev_rmw's
            # tg_result_hex.
            return {"tg_result_hex", "old_out_hex"}
        if shape == "tg_cmpxchg":
            return {"tg_result_hex", "old_out_hex", "success_out"}
        return set()
    if fam == "interlock":
        if case["kernel"] in ("il_atomic_alu", "il_atomic_src"):
            return {"out_hex"}
        return set()
    return set()


def authored_files():
    return ["casematrix.py", "run.py", "analysis.py", "verify.py",
            "kernels/atomics.metal", "kernels/atomics_ordering.metal",
            "kernels/interlock.metal", "kernels/interlock_tex.metal",
            "harness/atomics_probe.m", "harness/interlock_probe.m",
            "harness/interlock_tex_probe.m",
            "PRE_REGISTRATION.md", "README.md"]


def sha(relpath):
    return hashlib.sha256((HERE / relpath).read_bytes()).hexdigest()


def authored_sha256():
    return {p: sha(p) for p in authored_files()}


if __name__ == "__main__":
    print(f"TOTAL cases: {TOTAL}")
    from collections import Counter
    print(Counter(c["family"] for c in MATRIX))
