"""EXP-0124 maxCommandCount crash-boundary bisection (P1.7 / H-I6).

EXP-0098's h_icbmax census bracketed newIndirectCommandBufferWithDescriptor:
maxCommandCount:'s crash boundary between 4,194,304 (confirmed working) and
8,388,608 (confirmed SIGSEGV), explicitly not narrowed further ("not required by
the addendum"). This experiment's dispatch explicitly asks for the exact cliff, so
this module performs a deterministic integer bisection between those two known
bracket points, one probe per process (SAFETY: this family crashes the calling
process at high counts -- one case per process, hard per-probe timeout), appending
every probe (not just the converged endpoint) to an append-only JSONL file with
fflush after each record.

This is intentionally NOT part of the fixed casematrix.py matrix: the exact probe
SEQUENCE is only knowable by running it (each step's direction depends on the
previous probe's real outcome), unlike every other case in this experiment. It is
still fully deterministic and reproducible given fixed hardware behavior -- both
official runs execute this same algorithm independently and are compared for an
identical converged boundary in verify.py's --captured gate, which is the
reproducibility check for this component.
"""
import json, os, subprocess, time

# Bracket bounds established by EXP-0098 h_icbmax (both directions reproduced 2x+
# there); re-confirmed at the bracket ends here as probe #0/#1 before bisecting.
LO_KNOWN_WORKS = 4_194_304
HI_KNOWN_CRASHES = 8_388_608
PROBE_TIMEOUT_S = 30
MAX_ITERS = 30  # log2(8388608-4194304) ~= 22; generous cap


def _probe(ibench_path, max_count, timeout=PROBE_TIMEOUT_S):
    t0 = time.time()
    cmd = [str(ibench_path), "i_icbmax_probe", json.dumps({"maxCommandCount": max_count})]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        wall = time.time() - t0
        if p.returncode not in (0, 1):
            return {"status": "HARNESS_CRASH", "outcome": "CRASH", "wall_ms": round(wall*1000, 3),
                    "pid": p.pid if hasattr(p, "pid") else -1, "rc": p.returncode,
                    "stderr_tail": p.stderr[-300:]}
        status = None
        for line in p.stdout.splitlines():
            if line.startswith("STATUS "):
                status = line[len("STATUS "):].strip()
        outcome = "WORKS" if status == "OK" else ("OTHER_FAIL" if status else "OTHER_FAIL")
        return {"status": status or "UNKNOWN", "outcome": outcome, "wall_ms": round(wall*1000, 3),
                "pid": -1, "rc": p.returncode, "stderr_tail": p.stderr[-300:]}
    except subprocess.TimeoutExpired:
        wall = time.time() - t0
        return {"status": "HANG", "outcome": "TIMEOUT", "wall_ms": round(wall*1000, 3),
                "pid": -1, "rc": None, "stderr_tail": ""}


def run_bisection(out_path, ibench_path):
    out_path = str(out_path)
    if os.path.exists(out_path):
        raise RuntimeError(f"refuse to reuse an existing icbmax bisection file: {out_path}")
    f = open(out_path, "a")
    probes = []

    def record(probe_id, max_count, result):
        rec = {"probe_id": probe_id, "maxCommandCount": max_count, "status": result["status"],
               "outcome": result["outcome"], "wall_ms": result["wall_ms"], "pid": os.getpid()}
        f.write(json.dumps(rec, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        probes.append(rec)
        return rec

    # Re-confirm both bracket ends first (probe_id 0, 1) before bisecting between them.
    r_lo = _probe(ibench_path, LO_KNOWN_WORKS)
    record(0, LO_KNOWN_WORKS, r_lo)
    r_hi = _probe(ibench_path, HI_KNOWN_CRASHES)
    record(1, HI_KNOWN_CRASHES, r_hi)

    if r_lo["outcome"] != "WORKS" or r_hi["outcome"] not in ("CRASH", "TIMEOUT"):
        f.close()
        return {"converged": False, "reason": "bracket re-confirmation did not match "
                "EXP-0098's recorded behavior -- see raw probes 0/1", "probes_total": len(probes)}

    lo, hi = LO_KNOWN_WORKS, HI_KNOWN_CRASHES
    pid = 2
    monotonic_violation = False
    while hi - lo > 1 and pid < MAX_ITERS:
        mid = lo + (hi - lo) // 2
        r = _probe(ibench_path, mid)
        record(pid, mid, r)
        pid += 1
        if r["outcome"] == "WORKS":
            if mid < lo:
                monotonic_violation = True
            lo = mid
        else:
            if mid > hi:
                monotonic_violation = True
            hi = mid

    f.close()
    return {
        "converged": (hi - lo == 1),
        "last_working": lo,
        "first_crashing": hi,
        "probes_total": len(probes),
        "monotonic_violation_detected": monotonic_violation,
    }
