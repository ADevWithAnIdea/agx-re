#!/usr/bin/env python3
"""EXP-0135 capture driver.

One case = one OS process (mesh_probe, or a dedicated Group R static/iotrace
step), never batched, matching CLAUDE.md's recovery model. Every record is
appended to raw/<run_id>/records.jsonl and fflush'd immediately after each
case so a kill/wedge loses at most the in-flight case. Hard per-case timeout
via subprocess.run(timeout=...) (no external `timeout` binary on this host).

Usage:
  python3 run.py --run-id m4_YYYYMMDD_runNN [--smoke] [--limit N]

--smoke writes into work/smoke/<run_id>/ instead of raw/ and is NOT a valid
--run01/--run02 argument for verify.py (the NON-RECORDED smoke gate CODEX
requires before any raw/ capture).
"""
import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_matrix  # noqa: E402

BIN = os.path.join(EXP_ROOT, "work", "bin")
PER_CASE_TIMEOUT_S = 30
POST_ANOMALY_TIMEOUT_S = 30


def sh(cmd, cwd=EXP_ROOT, timeout=60):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def build_tools():
    os.makedirs(BIN, exist_ok=True)
    steps = [
        (["clang", "-fobjc-arc", "-O1", "-framework", "Metal", "-framework", "Foundation",
          "-o", os.path.join(BIN, "mesh_probe"), "harness/mesh_probe.m"]),
        (["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
          "-o", os.path.join(BIN, "shdump_mesh"), "harness/shdump_mesh.m"]),
        (["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
          "-o", os.path.join(BIN, "shdump_compute"), "../../tools/shdump/shdump.m"]),
        (["clang", "-dynamiclib", "-o", os.path.join(BIN, "iotrace.dylib"),
          "../../tools/iotrace/iotrace.c", "-framework", "IOKit", "-framework", "CoreFoundation"]),
        (["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
          "-o", os.path.join(BIN, "iohello_compute"), "../../tools/iotrace/iohello_compute.m"]),
        (["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
          "-o", os.path.join(BIN, "iohello_draw"), "../../tools/iotrace/iohello_draw.m"]),
        (["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
          "-o", os.path.join(BIN, "iohello_mesh"), "harness/iohello_mesh.m"]),
    ]
    for cmd in steps:
        r = sh(cmd)
        if r.returncode != 0:
            print("BUILD FAIL:", " ".join(cmd), file=sys.stderr)
            print(r.stderr, file=sys.stderr)
            sys.exit(1)
    print("build: OK (7 tools)", file=sys.stderr)


def classify(returncode, timed_out, stdout):
    if timed_out:
        return "TIMEOUT"
    if returncode is not None and returncode < 0:
        return f"CRASH_SIG{-returncode}"
    lines = stdout.splitlines()
    status_lines = [l for l in lines if l.startswith("STATUS ")]
    if status_lines:
        return status_lines[-1].split(" ", 1)[1].strip()
    if returncode == 0:
        return "OK_NO_STATUS_LINE"
    return f"UNKNOWN_RC{returncode}"


def run_case_probe(case, run_dir):
    argv = [os.path.join(BIN, "mesh_probe")] + case["argv_extra"]
    t0 = time.time()
    timed_out = False
    try:
        r = subprocess.run(argv, cwd=EXP_ROOT, capture_output=True, text=True,
                            timeout=PER_CASE_TIMEOUT_S)
        rc, out, err = r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as e:
        timed_out = True
        rc, out, err = None, (e.stdout or ""), (e.stderr or "")
    elapsed = time.time() - t0
    status = classify(rc, timed_out, out if isinstance(out, str) else (out or b"").decode("utf-8", "replace"))
    rec = {
        "case_id": case["case_id"], "group": case["group"], "role": case["role"],
        "params": case["params"], "argv": argv, "role_note": case.get("role_note", ""),
        "returncode": rc, "timed_out": timed_out, "elapsed_s": round(elapsed, 4),
        "status": status,
        "stdout": out if isinstance(out, str) else (out or b"").decode("utf-8", "replace"),
        "stderr": (err if isinstance(err, str) else (err or b"").decode("utf-8", "replace"))[-2000:],
    }
    return rec, status


def group_r_static(run_dir):
    """Group R byte-extraction: build the two mesh archives + the compute
    control, extract each stage's _agc.main hex, and record structural facts
    (lengths, 0x43 frame_marker occurrence count, 0xe7 device_store count)."""
    work = os.path.join(run_dir, "work_r")
    os.makedirs(work, exist_ok=True)
    recs = []

    def build(dst, defines, extra_args):
        args = [os.path.join(BIN, "shdump_mesh"), "-o", dst] + extra_args
        for k, v in defines.items():
            args += ["--define", f"{k}={v}"]
        args.append("kernels/mesh_sweep.metal")
        r = sh(args, timeout=60)
        return r

    base_bin = os.path.join(work, "mesh_baseline.bin")
    emit0_bin = os.path.join(work, "mesh_emit0.bin")
    compute_bin = os.path.join(work, "compute_emul.bin")
    build(base_bin, dict(NV=3, NP=1, PAYLOAD_BYTES=16, AMP_COUNT=1), [])
    build(emit0_bin, dict(NV=3, NP=0, PAYLOAD_BYTES=16, AMP_COUNT=1), [])
    r = sh([os.path.join(BIN, "shdump_compute"), "-o", compute_bin, "-f", "emul_main",
            "kernels/compute_emul.metal"], timeout=60)

    sys.path.insert(0, os.path.join(EXP_ROOT, "harness"))
    import mesh_extract  # noqa: E402  (monkeypatches agxparse.STAGE_SECTIONS for __object/__mesh)
    agxparse = mesh_extract.agxparse

    def extract(path, stage):
        buf = open(path, "rb").read()
        _, stages = agxparse.extract_all_stages(buf)
        return stages[stage]["_agc.main"].hex()

    def e7count(h):
        return sum(1 for i in range(0, len(h), 2) if h[i:i + 2] == "e7")

    def marker_count(h):
        return h.count("43000001")

    facts = {}
    for tag, path in [("base", base_bin), ("emit0", emit0_bin)]:
        for stage in ("object", "mesh", "fragment"):
            h = extract(path, stage)
            facts[f"{tag}_{stage}_hex_sha256"] = hashlib.sha256(h.encode()).hexdigest()
            facts[f"{tag}_{stage}_len_bytes"] = len(h) // 2
            facts[f"{tag}_{stage}_e7_count"] = e7count(h)
            facts[f"{tag}_{stage}_frame_marker_43000001_count"] = marker_count(h)
    comp_h = extract(compute_bin, "compute")
    facts["compute_control_hex_sha256"] = hashlib.sha256(comp_h.encode()).hexdigest()
    facts["compute_control_len_bytes"] = len(comp_h) // 2
    facts["compute_control_e7_count"] = e7count(comp_h)
    facts["obj_stage_identical_base_vs_emit0"] = (
        extract(base_bin, "object") == extract(emit0_bin, "object"))

    for cid in ["R-bytes-mesh-baseline", "R-bytes-mesh-emit0", "R-bytes-compute-control"]:
        recs.append({"case_id": cid, "group": "R", "role": "extract", "params": {},
                     "status": "OK", "facts": facts if cid == "R-bytes-mesh-baseline" else "see R-bytes-mesh-baseline"})
    return recs


def group_r_trace(run_dir):
    """Group R DATA-TRACE: iotrace-wrapped mesh / draw / compute dispatch,
    compare IOKit selector-CALL counts (EXP-0030's headline metric: mesh
    IOKit call count approx= draw call count, both > compute)."""
    import iotrace_parse
    work = os.path.join(run_dir, "work_r_trace")
    os.makedirs(work, exist_ok=True)
    recs = []
    targets = [
        ("R-trace-mesh", "iohello_mesh", ["--w", "16", "--h", "16"]),
        ("R-trace-draw", "iohello_draw", []),
        ("R-trace-compute", "iohello_compute", []),
    ]
    for cid, binname, extra in targets:
        log = os.path.join(work, f"{cid}.log")
        env = dict(os.environ)
        env["IOTRACE_LOG"] = log
        env["DYLD_INSERT_LIBRARIES"] = os.path.join(BIN, "iotrace.dylib")
        try:
            r = subprocess.run([os.path.join(BIN, binname)] + extra, cwd=EXP_ROOT, env=env,
                                capture_output=True, text=True, timeout=PER_CASE_TIMEOUT_S)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            r = None
        if timed_out:
            recs.append({"case_id": cid, "group": "R", "role": "iotrace", "params": {},
                         "status": "TIMEOUT"})
            continue
        parsed = iotrace_parse.parse_iotrace_log(log) if os.path.exists(log) else {}
        recs.append({
            "case_id": cid, "group": "R", "role": "iotrace", "params": {},
            "status": "OK" if r.returncode == 0 else f"RC{r.returncode}",
            "total_calls": parsed.get("total_calls"), "sel9_calls": parsed.get("sel9_calls"),
            "selector_histogram": parsed.get("selector_histogram"),
            "stdout_tail": r.stdout.strip().splitlines()[-3:],
        })
    return recs


def group_d_trace(matrix, run_dir):
    """Group D iotrace BO-scaling check: does the sel-9-registered BO size
    multiset change across payload/NV/NP/AMP_COUNT checkpoints (EXP-0120
    methodology, reusing its iotrace_parse.py BODUMP parser verbatim,
    applied here to the mesh output/payload buffers)?"""
    import iotrace_parse
    work = os.path.join(run_dir, "work_d_trace")
    os.makedirs(work, exist_ok=True)
    recs = []
    d_trace_cases = [c for c in matrix if c["group"] == "D" and c["role"] == "iotrace_bo_scaling"]
    for c in d_trace_cases:
        p = c["params"]
        log = os.path.join(work, f"{c['case_id']}.log")
        mapdir = os.path.join(work, f"{c['case_id']}_maps")
        env = dict(os.environ)
        env["IOTRACE_LOG"] = log
        env["IOTRACE_DUMP_DIR"] = mapdir
        env["DYLD_INSERT_LIBRARIES"] = os.path.join(BIN, "iotrace.dylib")
        argv = [os.path.join(BIN, "mesh_probe"), "--src", "kernels/mesh_sweep.metal",
                "--define", f"NV={p['NV']}", "--define", f"NP={p['NP']}",
                "--define", f"PAYLOAD_BYTES={p['PAYLOAD_BYTES']}",
                "--define", f"AMP_COUNT={p['AMP_COUNT']}",
                "--mode", "direct", "--width", "32", "--height", "32", "--dump"]
        try:
            r = subprocess.run(argv, cwd=EXP_ROOT, env=env, capture_output=True, text=True,
                                timeout=PER_CASE_TIMEOUT_S)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            r = None
        if timed_out:
            recs.append({"case_id": c["case_id"], "group": "D", "role": "iotrace_bo_scaling",
                         "params": p, "status": "TIMEOUT"})
            continue
        parsed = iotrace_parse.parse_iotrace_log(log) if os.path.exists(log) else {}
        recs.append({
            "case_id": c["case_id"], "group": "D", "role": "iotrace_bo_scaling", "params": p,
            "status": "OK" if r.returncode == 0 else f"RC{r.returncode}",
            "n_bo": parsed.get("n_bo"), "sel9_calls": parsed.get("sel9_calls"),
            "total_calls": parsed.get("total_calls"),
            "size_multiset": parsed.get("size_multiset"),
            "selector_histogram": parsed.get("selector_histogram"),
        })
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    build_tools()

    base = os.path.join(EXP_ROOT, "work", "smoke") if args.smoke else os.path.join(EXP_ROOT, "raw")
    run_dir = os.path.join(base, args.run_id)
    if os.path.exists(run_dir):
        print(f"REFUSE: {run_dir} already exists (run-id reuse is forbidden)", file=sys.stderr)
        sys.exit(1)
    os.makedirs(run_dir)

    records_path = os.path.join(run_dir, "records.jsonl")
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    live_head = sh(["git", "rev-parse", "HEAD"]).stdout.strip()

    matrix = gen_matrix.build_matrix()
    if args.limit:
        matrix = matrix[:args.limit]

    n_anomaly = 0
    with open(records_path, "a") as f:
        # Group R static + trace first (order fixed, deterministic).
        for rec in group_r_static(run_dir):
            f.write(json.dumps(rec) + "\n")
            f.flush()
        for rec in group_r_trace(run_dir):
            f.write(json.dumps(rec) + "\n")
            f.flush()
        for rec in group_d_trace(matrix, run_dir):
            f.write(json.dumps(rec) + "\n")
            f.flush()

        probe_cases = [c for c in matrix if c["argv_extra"]]
        for i, c in enumerate(probe_cases):
            rec, status = run_case_probe(c, run_dir)
            f.write(json.dumps(rec) + "\n")
            f.flush()
            anomaly = status not in ("OK", "COMPILE_FAIL", "PIPELINE_FAIL", "CMDBUF_ERROR")
            if anomaly:
                n_anomaly += 1
                print(f"ANOMALY case={c['case_id']} status={status} -- running post-fault sanity check",
                      file=sys.stderr)
                sanity_argv = [os.path.join(BIN, "mesh_probe"), "--src", "kernels/mesh_sweep.metal",
                               "--define", "NV=3", "--define", "NP=1", "--define", "PAYLOAD_BYTES=16",
                               "--define", "AMP_COUNT=1", "--mode", "direct",
                               "--width", "32", "--height", "32"]
                try:
                    sr = subprocess.run(sanity_argv, cwd=EXP_ROOT, capture_output=True, text=True,
                                         timeout=POST_ANOMALY_TIMEOUT_S)
                    s_status = classify(sr.returncode, False, sr.stdout)
                except subprocess.TimeoutExpired:
                    s_status = "TIMEOUT"
                sanity_rec = {"case_id": f"post_fault_sanity_after_{c['case_id']}", "group": "SAFETY",
                              "role": "post_fault_sanity", "params": {}, "status": s_status,
                              "after_case": c["case_id"]}
                f.write(json.dumps(sanity_rec) + "\n")
                f.flush()
                if s_status != "OK":
                    print("HOST MAY BE UNSTABLE -- sanity check did not return OK. STOPPING.",
                          file=sys.stderr)
                    break
            if (i + 1) % 10 == 0:
                print(f"progress: {i+1}/{len(probe_cases)} probe cases done", file=sys.stderr)

    manifest = {
        "run_id": args.run_id, "smoke": args.smoke, "started_utc": started,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "live_repo_head_at_run_time": live_head,
        "n_cases_in_matrix": len(matrix), "n_anomalies": n_anomaly,
    }
    with open(os.path.join(run_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    if not args.smoke:
        open(os.path.join(run_dir, "COMPLETE"), "w").close()
    print(f"done: {run_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
