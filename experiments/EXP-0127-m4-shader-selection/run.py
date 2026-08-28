#!/usr/bin/env python3
"""EXP-0127 run.py -- official capture driver.

Builds tools/iotrace + harness/vstoken + harness/fsredirect (all our own
authored source; iotrace.c is the repository's unmodified, read-only
DATA-TRACE interposer), then runs:

  1. vstoken --mode varied   (task 1, size-independence discrimination)
  2. vstoken --mode uniform  (task 1, linear rule + capacity boundary)
  3. vstoken --mode uniform --pad-mb 0/64, --extra-queues 4
                              (task 3, code-window relocation category)
  4. fsredirect case matrix  (task 2, FS selector redirect + boundary sweep)

Raw per-draw DATA-TRACE dumps (BODUMP .hex snapshots) are written under
work/dumps_<run-id>_<subtest>/ -- scratch, per SUBAGENT_BRIEF.md ("use
work/ inside your experiment dir"), never committed. This program reads
them immediately to compute the small, non-address derived facts that ARE
committed evidence (raw/<run-id>/*_gated.json / *_addrs.json, plus the
harnesses' own raw stdout, which is the append-only, human-auditable
evidence trail: every RESULT/DUMP line for every draw, including any
mid-run failure).

Usage:
  python3 run.py --run-id m4_<date>_run01
  python3 run.py --smoke     # single tiny non-recorded case into work/, never raw/
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BUILD = ROOT / "build"
RAW = ROOT / "raw"
WORK = ROOT / "work"

sys.path.insert(0, str(ROOT))
import schema  # noqa: E402

VSTOKEN_DUMP_SLEEP_MS_SMALL = 2000
VSTOKEN_DUMP_SLEEP_MS_SPARSE = 500

FSREDIRECT_CASES = [
    "baseline_red_solo", "baseline_green_solo", "baseline_blue_solo",
    "redirect_red_to_green", "redirect_red_to_blue",
    "redirect_green_to_red", "redirect_blue_to_red",
    "misalign_plus1", "misalign_plus2", "misalign_plus4", "misalign_plus8",
    "misalign_minus1", "misalign_minus2", "misalign_minus4", "misalign_minus8",
    "boundary_zero", "boundary_far_oor", "boundary_top_bit", "boundary_max",
    "boundary_near_but_invalid",
]


def run(cmd, *, timeout, env=None, cwd=None, stdout=None, stderr=None, check=True):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd or ROOT, env=env, stdout=stdout,
                          stderr=stderr, timeout=timeout, check=check)


def build():
    BUILD.mkdir(exist_ok=True)
    run(["xcrun", "clang", "-arch", "arm64", "-dynamiclib", "-o",
         str(BUILD / "iotrace.dylib"), str(REPO / "tools/iotrace/iotrace.c"),
         "-framework", "IOKit", "-framework", "CoreFoundation"], timeout=60)
    run(["xcrun", "clang", "-fobjc-arc", "-o", str(BUILD / "vstoken"),
         str(ROOT / "harness/vstoken.m"),
         "-framework", "Metal", "-framework", "Foundation"], timeout=60)
    run(["xcrun", "clang", "-fobjc-arc", "-o", str(BUILD / "fsredirect"),
         str(ROOT / "harness/fsredirect.m"),
         "-framework", "Metal", "-framework", "Foundation"], timeout=60)


# ---------------------------------------------------------------------------
# BODUMP (.hex) reading -- same public format tools/iotrace/iotrace.c writes
# (unmodified, read-only tool); our own independent reader, matching the
# format this experiment's other harnesses/pilots already parse.
HEADER_RE = re.compile(r"gpu_va=0x([0-9a-f]+).*size=0x([0-9a-f]+)")
LINE_RE = re.compile(r"^([0-9a-f]{8}):\s+(.*)$")


def load_hex(path: Path):
    text = path.read_text(errors="strict").splitlines()
    m = HEADER_RE.search(text[0])
    va = int(m.group(1), 16)
    size = int(m.group(2), 16)
    chunks = []
    for line in text[1:]:
        mm = LINE_RE.match(line)
        if mm:
            chunks.append(bytes.fromhex(mm.group(2).replace(" ", "")))
    return va, size, b"".join(chunks)


def u32(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 4], "little")


def find_bo_exact(dumpdir: Path, want_va: int):
    """Return (va, size, data) for the BO registered at exactly `want_va` in
    `dumpdir`, matching the `_va<hex>_` filename segment exactly (never a
    prefix/substring match, so 0x18000 is never confused with
    0x10000018000)."""
    for f in dumpdir.glob("bo_*.hex"):
        m = re.search(r"_va([0-9a-f]+)_", f.name)
        if m and int(m.group(1), 16) == want_va:
            return load_hex(f)
    return None


def all_bo_vas(dumpdir: Path) -> set:
    out = set()
    for f in dumpdir.glob("bo_*.hex"):
        m = re.search(r"_va([0-9a-f]+)_", f.name)
        if m:
            out.add(int(m.group(1), 16))
    return out


# ---------------------------------------------------------------------------
def vstoken_env(dump_dir: Path, persig: bool, max_map=4194304):
    env = os.environ.copy()
    env.update({
        "DYLD_INSERT_LIBRARIES": str(BUILD / "iotrace.dylib"),
        "IOTRACE_LOG": str(dump_dir / "iotrace.log"),
        "IOTRACE_DUMP_DIR": str(dump_dir),
        "IOTRACE_DUMP_ON_USR1": "1",
        "IOTRACE_DUMP_PERSIG": "1" if persig else "0",
        "IOTRACE_MAX_MAP": str(max_map),
    })
    return env


def compute_dump_schedule(count, dump_first, dump_stride, window):
    lo, hi = window
    sched = []
    for i in range(count):
        if i < dump_first or (dump_stride > 0 and i % dump_stride == 0) or \
           i == count - 1 or (lo <= i <= hi):
            sched.append(i)
    return sched


def run_vstoken_varied(run_id: str) -> dict:
    dump_dir = WORK / f"dumps_{run_id}_varied"
    dump_dir.mkdir(parents=True, exist_ok=True)
    env = vstoken_env(dump_dir, persig=True)
    stdout_path = RAW / run_id / "vstoken_varied_stdout.txt"
    with stdout_path.open("wb") as out:
        run([str(BUILD / "vstoken"), "--mode", "varied", "--order",
             "0,1,2,3,4,5,6,7", "--dump", "--dump-first", "8",
             "--watchdog-sec", "10", "--alarm", "60",
             "--dump-sleep-ms", str(VSTOKEN_DUMP_SLEEP_MS_SPARSE)],
            timeout=90, env=env, stdout=out, stderr=subprocess.STDOUT)
    text = stdout_path.read_text()
    statuses = re.findall(r"RESULT i=\d+ name=\S+ stage=draw status=(\S+)", text)
    tokens = []
    for i in range(8):
        d = dump_dir / f"dump{i:02d}"
        got = find_bo_exact(d, 0x18000)
        if got is None:
            raise RuntimeError(f"varied: no VDM bo at dump{i:02d}")
        _, _, data = got
        tokens.append(u32(data, 0x20))
    deltas = [tokens[i] - tokens[i - 1] for i in range(1, len(tokens))]
    result = {
        "mode": "varied", "order": "0,1,2,3,4,5,6,7", "n": 8,
        "tokens": tokens, "deltas": deltas,
        "readback_status_all_completed": all(s == "completed" for s in statuses) and len(statuses) == 8,
    }
    shutil.rmtree(dump_dir, ignore_errors=True)
    return result


def run_vstoken_uniform(run_id: str, count: int) -> dict:
    dump_dir = WORK / f"dumps_{run_id}_uniform"
    dump_dir.mkdir(parents=True, exist_ok=True)
    env = vstoken_env(dump_dir, persig=True)
    stdout_path = RAW / run_id / "vstoken_uniform_stdout.txt"
    window = (max(0, 495), min(count - 1, 515))
    with stdout_path.open("wb") as out:
        run([str(BUILD / "vstoken"), "--mode", "uniform", "--count", str(count),
             "--dump", "--dump-first", "4", "--dump-stride", "50",
             "--dump-window", f"{window[0]},{window[1]}",
             "--watchdog-sec", "10", "--alarm", "300",
             "--dump-sleep-ms", str(VSTOKEN_DUMP_SLEEP_MS_SPARSE)],
            timeout=340, env=env, stdout=out, stderr=subprocess.STDOUT)
    text = stdout_path.read_text()
    statuses = re.findall(r"RESULT i=\d+ name=\S+ stage=draw status=(\S+)", text)
    schedule = compute_dump_schedule(count, 4, 50, window)
    tokens = []
    new_region_va = None
    new_region_size = None
    prev_vas = None
    boundary_index = None
    for event_idx, i in enumerate(schedule):
        d = dump_dir / f"dump{event_idx:02d}"
        got = find_bo_exact(d, 0x18000)
        if got is None:
            raise RuntimeError(f"uniform: no VDM bo at dump{event_idx:02d} (i={i})")
        _, _, data = got
        tok = u32(data, 0x20)
        tokens.append(tok)
        cur_vas = all_bo_vas(d)
        if prev_vas is not None and boundary_index is None:
            new_vas = cur_vas - prev_vas
            close = [va for va in new_vas if va < (1 << 32) and abs(tok - va) < 0x1000]
            if close:
                new_region_va = close[0]
                got2 = find_bo_exact(d, new_region_va)
                if got2:
                    new_region_size = got2[1]
                boundary_index = i
        prev_vas = cur_vas

    # Linear fit from the first two checkpoints at i>=1 (skip i=0's own
    # anomaly, see RESULTS.md).
    idx_ge1 = [k for k, i in enumerate(schedule) if i >= 1]
    linear_base = linear_step = None
    if len(idx_ge1) >= 2:
        k0, k1 = idx_ge1[0], idx_ge1[1]
        i0, i1 = schedule[k0], schedule[k1]
        t0, t1 = tokens[k0], tokens[k1]
        if i1 != i0:
            linear_step = (t1 - t0) // (i1 - i0)
            linear_base = t0 - linear_step * i0

    boundary_delta = None
    post_boundary_step_ok = None
    if boundary_index is not None and linear_step is not None:
        bk = schedule.index(boundary_index)
        predicted = linear_base + linear_step * boundary_index
        boundary_delta = tokens[bk] - predicted
        # Check post-boundary checkpoints continue linearly (same step) from
        # the boundary's own token.
        ok = True
        for k in range(bk + 1, len(schedule)):
            steps = schedule[k] - schedule[bk]
            predicted2 = tokens[bk] + linear_step * steps
            if tokens[k] != predicted2:
                ok = False
                break
        post_boundary_step_ok = ok

    deltas = [tokens[k] - tokens[k - 1] for k in range(1, len(tokens))]
    result = {
        "mode": "uniform", "count": count, "schedule": schedule,
        "tokens": tokens, "deltas": deltas,
        "linear_base": linear_base, "linear_step": linear_step,
        "first_step_anomaly_token": tokens[0],
        "boundary_index": boundary_index, "boundary_delta": boundary_delta,
        "post_boundary_step_ok": post_boundary_step_ok,
        "readback_status_all_completed": all(s == "completed" for s in statuses) and len(statuses) == count,
        "new_region_appeared": new_region_va is not None,
        "new_region_size": new_region_size,
        "new_region_va": new_region_va,  # addr field, split out by schema
    }
    shutil.rmtree(dump_dir, ignore_errors=True)
    return result


def run_vstoken_perturb(run_id: str, label: str, pad_mb: int, extra_queues: int,
                        baseline: dict | None) -> dict:
    dump_dir = WORK / f"dumps_{run_id}_{label}"
    dump_dir.mkdir(parents=True, exist_ok=True)
    env = vstoken_env(dump_dir, persig=False)
    stdout_path = RAW / run_id / f"vstoken_{label}_stdout.txt"
    cmd = [str(BUILD / "vstoken"), "--mode", "uniform", "--count", "3",
           "--dump", "--dump-first", "3", "--watchdog-sec", "10", "--alarm", "60",
           "--dump-sleep-ms", str(VSTOKEN_DUMP_SLEEP_MS_SMALL)]
    if pad_mb:
        cmd += ["--pad-mb", str(pad_mb)]
    if extra_queues:
        cmd += ["--extra-queues", str(extra_queues)]
    with stdout_path.open("wb") as out:
        run(cmd, timeout=90, env=env, stdout=out, stderr=subprocess.STDOUT)
    text = stdout_path.read_text()
    statuses = re.findall(r"RESULT i=\d+ name=\S+ stage=draw status=(\S+)", text)
    code = find_bo_exact(dump_dir, 0x10000000000)
    pool = find_bo_exact(dump_dir, 0x58000)
    vdm = find_bo_exact(dump_dir, 0x18000)
    code_va = code[0] if code else None
    pool_va = pool[0] if pool else None
    vdm_va = vdm[0] if vdm else None
    result = {
        "mode": f"perturb_{label}", "pad_mb": pad_mb, "extra_queues": extra_queues, "n": 3,
        "readback_status_all_completed": all(s == "completed" for s in statuses) and len(statuses) == 3,
        "code_bo_va": code_va, "pool_va": pool_va, "vdm_va": vdm_va,
    }
    if baseline is None:
        result["code_bo_base_unchanged_vs_pad0_baseline"] = True
        result["pool_base_unchanged_vs_pad0_baseline"] = True
        result["vdm_base_unchanged_vs_pad0_baseline"] = True
    else:
        result["code_bo_base_unchanged_vs_pad0_baseline"] = (code_va == baseline["code_bo_va"])
        result["pool_base_unchanged_vs_pad0_baseline"] = (pool_va == baseline["pool_va"])
        result["vdm_base_unchanged_vs_pad0_baseline"] = (vdm_va == baseline["vdm_va"])
    shutil.rmtree(dump_dir, ignore_errors=True)
    return result


def run_fsredirect_case(run_id: str, case: str) -> dict:
    dump_dir = WORK / f"dumps_{run_id}_fsredirect_{case}"
    dump_dir.mkdir(parents=True, exist_ok=True)
    (dump_dir / "iotrace_maps").mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update({
        "DYLD_INSERT_LIBRARIES": str(BUILD / "iotrace.dylib"),
        "IOTRACE_LOG": str(dump_dir / "iotrace.log"),
        "IOTRACE_DUMP_DIR": "iotrace_maps",
        "IOTRACE_DUMP_ON_USR1": "1",
        "IOTRACE_DUMP_PERSIG": "0",
        "IOTRACE_MAX_MAP": "4194304",
    })
    proc = run([str(BUILD / "fsredirect"), "--case", case, "--source",
                str(ROOT / "kernels/fsredirect.metal"), "--dump-dir", "work_dummy",
                "--watchdog-sec", "10", "--alarm", "45"],
               timeout=60, env=env, cwd=dump_dir,
               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    stdout_text = proc.stdout.decode(errors="replace")
    stderr_text = proc.stderr.decode(errors="replace")
    (RAW / run_id / f"fsredirect_{case}_stdout.txt").write_text(stdout_text)
    if stderr_text.strip():
        (RAW / run_id / f"fsredirect_{case}_stderr.txt").write_text(stderr_text)
    line = None
    for ln in stdout_text.splitlines():
        ln = ln.strip()
        if ln.startswith("{"):
            line = ln
    if line is None:
        shutil.rmtree(dump_dir, ignore_errors=True)
        return {"case": case, "process_error": True, "returncode": proc.returncode,
                "stdout_tail": stdout_text[-2000:]}
    result = json.loads(line)
    result["process_returncode"] = proc.returncode
    shutil.rmtree(dump_dir, ignore_errors=True)
    return result


# ---------------------------------------------------------------------------
def append_jsonl(path: Path, obj: dict):
    with path.open("a") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def official_run(run_id: str):
    run_dir = RAW / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(f"refusing to reuse a non-empty run id: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    build()

    gated_path = run_dir / "gated.jsonl"
    addrs_path = run_dir / "addrs.jsonl"

    # --- vstoken varied ---
    varied = run_vstoken_varied(run_id)
    g = schema.build_gated_vstoken(varied, "varied")
    schema.assert_no_address_leak(g)
    append_jsonl(gated_path, {"kind": "vstoken_varied", **g})
    append_jsonl(addrs_path, {"kind": "vstoken_varied", **schema.build_addrs_vstoken(varied)})
    progress(run_id, "vstoken varied done", varied)

    # --- vstoken uniform (to and past the capacity boundary) ---
    uniform = run_vstoken_uniform(run_id, count=650)
    g = schema.build_gated_vstoken(uniform, "uniform")
    schema.assert_no_address_leak(g)
    append_jsonl(gated_path, {"kind": "vstoken_uniform", **g})
    append_jsonl(addrs_path, {"kind": "vstoken_uniform", **schema.build_addrs_vstoken(uniform)})
    progress(run_id, "vstoken uniform (count=650) done", {
        "boundary_index": uniform["boundary_index"],
        "linear_base": uniform["linear_base"], "linear_step": uniform["linear_step"],
        "post_boundary_step_ok": uniform["post_boundary_step_ok"],
    })

    # --- vstoken perturbation (task 3) ---
    pad0 = run_vstoken_perturb(run_id, "pad0", pad_mb=0, extra_queues=0, baseline=None)
    g = schema.build_gated_vstoken(pad0, "perturb")
    schema.assert_no_address_leak(g)
    append_jsonl(gated_path, {"kind": "vstoken_perturb_pad0", **g})
    append_jsonl(addrs_path, {"kind": "vstoken_perturb_pad0", **schema.build_addrs_vstoken(pad0)})

    pad64 = run_vstoken_perturb(run_id, "pad64", pad_mb=64, extra_queues=0, baseline=pad0)
    g = schema.build_gated_vstoken(pad64, "perturb")
    schema.assert_no_address_leak(g)
    append_jsonl(gated_path, {"kind": "vstoken_perturb_pad64", **g})
    append_jsonl(addrs_path, {"kind": "vstoken_perturb_pad64", **schema.build_addrs_vstoken(pad64)})

    extraq = run_vstoken_perturb(run_id, "extraq", pad_mb=0, extra_queues=4, baseline=pad0)
    g = schema.build_gated_vstoken(extraq, "perturb")
    schema.assert_no_address_leak(g)
    append_jsonl(gated_path, {"kind": "vstoken_perturb_extraq", **g})
    append_jsonl(addrs_path, {"kind": "vstoken_perturb_extraq", **schema.build_addrs_vstoken(extraq)})
    progress(run_id, "vstoken perturbation (pad0/pad64/extraq) done", {
        "pad64_code_unchanged": pad64["code_bo_base_unchanged_vs_pad0_baseline"],
        "pad64_pool_unchanged": pad64["pool_base_unchanged_vs_pad0_baseline"],
        "extraq_code_unchanged": extraq["code_bo_base_unchanged_vs_pad0_baseline"],
    })

    # --- fsredirect case matrix ---
    for case in FSREDIRECT_CASES:
        result = run_fsredirect_case(run_id, case)
        if result.get("process_error"):
            append_jsonl(gated_path, {"kind": "fsredirect", "case": case, "process_error": True})
            progress(run_id, f"fsredirect case {case} PROCESS ERROR", result)
            continue
        g = schema.build_gated_fsredirect(result)
        schema.assert_no_address_leak(g)
        append_jsonl(gated_path, {"kind": "fsredirect", **g})
        append_jsonl(addrs_path, {"kind": "fsredirect", "case": case,
                                   **schema.build_addrs_fsredirect(result)})
        progress(run_id, f"fsredirect case {case} done", {
            "bind": result.get("bind"), "wrote": result.get("wrote"),
            "result_colour": result.get("result_colour"),
            "final_status": result.get("final_status"), "hang": result.get("hang"),
        })

    print(f"DONE run_id={run_id}")


def progress(run_id: str, what: str, data):
    p = ROOT / "PROGRESS.md"
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    line = f"\n- `{ts}` [{run_id}] {what}: `{json.dumps(data, sort_keys=True)}`\n"
    with p.open("a") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def smoke():
    build()
    dump_dir = WORK / "smoke_dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    env = vstoken_env(dump_dir, persig=False)
    proc = run([str(BUILD / "vstoken"), "--mode", "varied", "--order", "0,1",
                "--dump", "--dump-first", "2", "--watchdog-sec", "8", "--alarm", "30"],
               timeout=40, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
               check=False)
    print(proc.stdout.decode(errors="replace"))
    print("SMOKE_OK" if proc.returncode == 0 else f"SMOKE_FAIL rc={proc.returncode}")
    shutil.rmtree(dump_dir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--build-only", action="store_true")
    args = ap.parse_args()
    RAW.mkdir(exist_ok=True)
    WORK.mkdir(exist_ok=True)
    if args.build_only:
        build()
        return
    if args.smoke:
        smoke()
        return
    if not args.run_id:
        ap.error("--run-id required unless --smoke/--build-only")
    official_run(args.run_id)


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired as e:
        print(f"TIMEOUT after {e.timeout}s: {e.cmd}", file=sys.stderr)
        raise SystemExit(124)
