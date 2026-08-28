#!/usr/bin/env python3
"""EXP-0110 capture runner. One fresh process per case; hard timeouts;
append+fflush each record as it completes; a NON-RECORDED smoke case runs
into work/ before the append-only raw/ tree is created; GATED records
(schema.py) never carry a raw GPU address -- those live only in the sibling
`_addrs.jsonl` file for this run, which is NOT part of the cross-run gate.

Usage:
  python3 run.py --run-id m4_<date>_run01 --execute
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0110-m4-command-container-packing"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "analysis"))
import casematrix as CM  # noqa: E402
import schema  # noqa: E402
import scan  # noqa: E402

TIMEOUTS = {"build": 120, "cdm_case": 60, "vdm_case": 60, "state_case": 30,
            "container_case": 30, "container_live_case": 30, "smoke": 30}
DUMP_WAIT_US = 800000

AUTH_CODE = ("harness/cmdprobe.m", "harness/containerdispatch.m",
            "kernels/gen_container_kernels.py", "analysis/scan.py", "analysis/metadata.py",
            "analysis/report.py", "schema.py", "casematrix.py", "run.py", "verify.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md", "CAPTURE_CONTRACT.json")
AUTH_TOOLS = ("tools/iotrace/iotrace.c", "tools/iotrace/README.md",
             "tools/shdump/shdump.m", "tools/shdump/agxparse.py")

SMOKE_CASE = {"name": "smoke_ctrl", "count": 2, "prior_queues": 0, "pad_count": 0, "pad_bytes": 0}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*a):
    return subprocess.run(["git", *a], cwd=REPO, text=True, capture_output=True, check=True).stdout


def provenance():
    exp_status = git("status", "--porcelain", "--", EXP_REL)
    return {
        "git_revision": git("rev-parse", "HEAD").strip(),
        "git_dirty": git("status", "--porcelain").strip() != "",
        "experiment_tree_dirty_entries": len([l for l in exp_status.splitlines() if l.strip()]),
        "authored_code_sha256": {p: sha(HERE / p) for p in AUTH_CODE},
        "authored_doc_sha256": {p: sha(HERE / p) for p in AUTH_DOC if (HERE / p).exists()},
        "authored_tools_sha256": {p: sha(REPO / p) for p in AUTH_TOOLS},
        "machine": subprocess.run(["uname", "-a"], text=True, capture_output=True).stdout.strip(),
        "sw_vers": subprocess.run(["sw_vers"], text=True, capture_output=True).stdout.strip(),
    }


def build(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    iotrace_c = REPO / "tools" / "iotrace" / "iotrace.c"
    steps = [
        (["xcrun", "clang", "-dynamiclib", "-O2", "-o", str(out_dir / "iotrace.dylib"),
          str(iotrace_c), "-framework", "IOKit", "-framework", "CoreFoundation"]),
        (["xcrun", "clang", "-fobjc-arc", "-Wno-deprecated-declarations", "-o",
          str(out_dir / "cmdprobe"), str(HERE / "harness" / "cmdprobe.m"),
          "-framework", "Metal", "-framework", "Foundation"]),
        (["xcrun", "clang", "-fobjc-arc", "-Wno-deprecated-declarations", "-o",
          str(out_dir / "containerdispatch"), str(HERE / "harness" / "containerdispatch.m"),
          "-framework", "Metal", "-framework", "Foundation"]),
        (["xcrun", "clang", "-fobjc-arc", "-Wno-deprecated-declarations", "-o",
          str(out_dir / "shdump"), str(REPO / "tools" / "shdump" / "shdump.m"),
          "-framework", "Metal", "-framework", "Foundation"]),
    ]
    log = []
    for cmd in steps:
        r = subprocess.run(cmd, text=True, capture_output=True, timeout=TIMEOUTS["build"])
        log.append({"cmd": cmd, "returncode": r.returncode, "stderr": r.stderr[-4000:]})
        if r.returncode != 0:
            raise SystemExit("BUILD FAILED: %r\n%s" % (cmd, r.stderr))
    return log


def run_proc(argv, env, timeout, cwd=None):
    t0 = time.time()
    try:
        r = subprocess.run(argv, text=True, capture_output=True, timeout=timeout, env=env, cwd=cwd)
        return {"exit": r.returncode, "timed_out": False, "stdout": r.stdout, "stderr": r.stderr[-4000:],
                "duration_s": round(time.time() - t0, 3)}
    except subprocess.TimeoutExpired as e:
        return {"exit": None, "timed_out": True, "stdout": (e.stdout or ""), "stderr": (e.stderr or "")[-4000:],
                "duration_s": round(time.time() - t0, 3)}


def dump_dir_for(work_root, name):
    d = work_root / "maps" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def collect_matched(dump_dir, scan_fn, size_cap=8 * 1024 * 1024, **scan_kwargs):
    matched = {}
    catalog = []
    for p in sorted(glob.glob(str(dump_dir / "bo_sigusr1_h*_va*.hex"))):
        meta = scan.parse_dump_filename(os.path.basename(p))
        if meta is None:
            continue
        catalog.append({"gpu_va": meta["gpu_va"], "size": meta["size"], "handle": meta["handle"]})
        if meta["size"] > size_cap or meta["size"] < 0x2c:
            continue
        d = scan.load_hex_dump(p)
        r = scan_fn(d["data"], **scan_kwargs)
        if r["record_count"] > 0:
            r["gpu_va"] = d["gpu_va"]
            matched[d["gpu_va"]] = r
    return matched, catalog


def cdm_case(bin_dir, work_root, case, baseline_segments, iotrace):
    argv = [str(bin_dir / "cmdprobe"), "--mode", "cdm", "--count", str(case["count"]),
            "--prior-queues", str(case["prior_queues"]), "--pad-count", str(case["pad_count"]),
            "--pad-bytes", str(case["pad_bytes"]), "--dump-wait-us", str(DUMP_WAIT_US)]
    dd = dump_dir_for(work_root, case["name"])
    logp = work_root / "logs" / (case["name"] + ".log.txt")
    logp.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, DYLD_INSERT_LIBRARIES=str(iotrace), IOTRACE_LOG=str(logp), IOTRACE_DUMP_DIR=str(dd))
    z = run_proc(argv, env, TIMEOUTS["cdm_case"])
    if z["timed_out"] or z["exit"] != 0:
        return ({"case": case["name"], "kind": "cdm", "params": case, "status": "proc_fail" if not z["timed_out"] else "proc_timeout",
                 "cb_status": None, "segment_count": 0, "total_records": 0, "segments": []},
                {"case": case["name"], "receipt": z, "matched": {}, "catalog": []})
    matched, catalog = collect_matched(dd, scan.scan_cdm_segment)
    chain, anomalies = scan.find_chain(matched)
    seg_in_order = []
    for i, va in enumerate(chain):
        r = dict(matched[va])
        if r["tail_kind"] == "link":
            tag, tgt = scan.decode_link(r["tail_hi"], r["tail_lo"])
            nxt = chain[i + 1] if i + 1 < len(chain) else None
            r["decoded_target_va"] = tgt
            r["decoded_ok"] = (nxt is not None and tgt == nxt)
        else:
            r["decoded_ok"] = None
        seg_in_order.append(r)
    base_segs = baseline_segments if baseline_segments is not None else seg_in_order
    segs_gated = schema.build_segment_records(seg_in_order, base_segs)
    total_records = sum(s["record_count"] for s in seg_in_order)
    gated = {"case": case["name"], "kind": "cdm", "params": case, "status": "ok", "cb_status": 4,
             "segment_count": len(seg_in_order), "total_records": total_records, "segments": segs_gated}
    assert set(gated.keys()) == schema.CDM_CASE_KEYS
    raw = {"case": case["name"], "readback": [l for l in z["stdout"].splitlines() if l.startswith("READBACK")],
           "chain_va": [hex(v) for v in chain], "anomalies": anomalies,
           "segment_va": {hex(va): {k: v for k, v in r.items() if k != "gpu_va"} for va, r in matched.items()},
           "catalog": catalog}
    return gated, raw, seg_in_order


def vdm_case(bin_dir, work_root, case, baseline_segments, iotrace):
    argv = [str(bin_dir / "cmdprobe"), "--mode", "vdm", "--count", str(case["count"]),
            "--prior-queues", str(case["prior_queues"]), "--pad-count", str(case["pad_count"]),
            "--pad-bytes", str(case["pad_bytes"]), "--dump-wait-us", str(DUMP_WAIT_US)]
    if case.get("prior_draws"):
        argv.append("--prior-draws")
    dd = dump_dir_for(work_root, case["name"])
    logp = work_root / "logs" / (case["name"] + ".log.txt")
    logp.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, DYLD_INSERT_LIBRARIES=str(iotrace), IOTRACE_LOG=str(logp), IOTRACE_DUMP_DIR=str(dd))
    z = run_proc(argv, env, TIMEOUTS["vdm_case"])
    if z["timed_out"] or z["exit"] != 0:
        return ({"case": case["name"], "kind": "vdm", "params": case, "status": "proc_fail" if not z["timed_out"] else "proc_timeout",
                 "cb_status": None, "segment_count": 0, "total_records": 0, "segments": []},
                {"case": case["name"], "receipt": z, "matched": {}, "catalog": []})
    matched, catalog = collect_matched(dd, scan.scan_vdm_segment)
    chain, anomalies = scan.find_chain(matched)
    seg_in_order = []
    for i, va in enumerate(chain):
        r = dict(matched[va])
        if r["tail_kind"] == "link":
            tag, tgt = scan.decode_link(r["tail_hi"], r["tail_lo"])
            nxt = chain[i + 1] if i + 1 < len(chain) else None
            r["decoded_target_va"] = tgt
            r["decoded_ok"] = (nxt is not None and tgt == nxt)
        else:
            r["decoded_ok"] = None
        seg_in_order.append(r)
    base_segs = baseline_segments if baseline_segments is not None else seg_in_order
    segs_gated = schema.build_segment_records(seg_in_order, base_segs)
    total_records = sum(s["record_count"] for s in seg_in_order)
    gated = {"case": case["name"], "kind": "vdm", "params": case, "status": "ok", "cb_status": 4,
             "segment_count": len(seg_in_order), "total_records": total_records, "segments": segs_gated}
    assert set(gated.keys()) == schema.VDM_CASE_KEYS
    # secondary evidence for the multi-queue address-aliasing observation:
    # count DISTINCT (gpu_va) among ALL registered BOs (not just matched
    # command segments) whose filename gpu_va equals any chain member's va
    # but with a different cpu-mapping -- a queue/context aliasing signal.
    alias_notes = []
    by_va = {}
    for c in catalog:
        by_va.setdefault(c["gpu_va"], []).append(c)
    for va in chain:
        dups = [x for x in by_va.get(va, [])]
        if len(dups) > 1:
            alias_notes.append({"va": hex(va), "distinct_registrations": len(dups)})
    raw = {"case": case["name"], "readback": [l for l in z["stdout"].splitlines() if l.startswith("READBACK")],
           "chain_va": [hex(v) for v in chain], "anomalies": anomalies, "alias_notes": alias_notes,
           "segment_va": {hex(va): {k: v for k, v in r.items() if k != "gpu_va"} for va, r in matched.items()},
           "catalog": catalog}
    return gated, raw, seg_in_order


def state_case(bin_dir, work_root, case, iotrace):
    argv = [str(bin_dir / "cmdprobe"), "--mode", "vdm", "--count", str(case["count"]),
            "--dump-wait-us", str(DUMP_WAIT_US), "--cull", case["cull"]]
    if case["depth_test"]:
        argv.append("--depth-test")
    if case["stencil_test"]:
        argv.append("--stencil-test")
    if case["blend"]:
        argv.append("--blend")
    dd = dump_dir_for(work_root, case["name"])
    logp = work_root / "logs" / (case["name"] + ".log.txt")
    logp.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, DYLD_INSERT_LIBRARIES=str(iotrace), IOTRACE_LOG=str(logp), IOTRACE_DUMP_DIR=str(dd))
    z = run_proc(argv, env, TIMEOUTS["state_case"])
    if z["timed_out"] or z["exit"] != 0:
        return ({"case": case["name"], "kind": "state", "params": case,
                 "status": "proc_fail" if not z["timed_out"] else "proc_timeout",
                 "cb_status": None, "pool_fields": {}, "pairs": []},
                {"case": case["name"], "receipt": z})
    matched, catalog = collect_matched(dd, scan.scan_vdm_segment, min_run=2)
    chain, anomalies = scan.find_chain(matched)
    if not chain:
        return ({"case": case["name"], "kind": "state", "params": case, "status": "no_vdm_segment",
                 "cb_status": 4, "pool_fields": {}, "pairs": []},
                {"case": case["name"], "receipt": z, "anomalies": anomalies})
    vdm_va = chain[0]
    vdm_path = glob.glob(str(dd / ("bo_sigusr1_h*_va%x_*.hex" % vdm_va)))[0]
    d = scan.load_hex_dump(vdm_path)
    r = matched[vdm_va]
    pairs = scan.scan_vdm_bindpairs(d["data"], r["first_offset"])
    pool_base, cluster = scan.find_pool_base(pairs)
    pool_fields = {}
    pool_path = None
    if pool_base is not None:
        cands = glob.glob(str(dd / ("bo_sigusr1_h*_va%x_*.hex" % pool_base)))
        if cands:
            pool_path = cands[0]
            pd = scan.load_hex_dump(pool_path)
            import struct as _s
            for off in (0x34, 0x38, 0x3c, 0x40, 0x44, 0x50, 0x70):
                if off + 4 <= len(pd["data"]):
                    pool_fields[hex(off)] = hex(_s.unpack_from("<I", pd["data"], off)[0])
    pairs_gated = []
    for p in pairs:
        delta = (p["address"] - pool_base) if pool_base is not None else None
        pairs_gated.append({"control": p["control"], "delta_from_pool": delta})
        assert set(pairs_gated[-1].keys()) == schema.STATE_PAIR_KEYS
    gated = {"case": case["name"], "kind": "state", "params": case, "status": "ok", "cb_status": 4,
             "pool_fields": pool_fields, "pairs": pairs_gated}
    assert set(gated.keys()) == schema.STATE_CASE_KEYS
    raw = {"case": case["name"], "vdm_va": hex(vdm_va), "pool_base": hex(pool_base) if pool_base else None,
           "cluster": [hex(x) for x in cluster], "pairs_raw": pairs,
           "readback": [l for l in z["stdout"].splitlines() if l.startswith("READBACK")]}
    return gated, raw


def container_case(bin_dir, case):
    kernels_dir = HERE / "kernels" / "generated"
    src = kernels_dir / case["file"]
    arc = HERE / "work" / ("container_%s.bin" % case["name"])
    argv = [str(bin_dir / "shdump"), "-o", str(arc), "-f", case["function"], str(src)]
    z = run_proc(argv, dict(os.environ), TIMEOUTS["container_case"])
    if z["timed_out"] or z["exit"] != 0 or not arc.exists():
        return ({"case": case["name"], "kind": "container", "function": case["function"],
                 "meta_len": 0, "fields": {}, "sections_present": []},
                {"case": case["name"], "receipt": z})
    sys.path.insert(0, str(HERE / "analysis"))
    import metadata as MD
    surv = MD.survey(str(arc))
    gated = {"case": case["name"], "kind": "container", "function": case["function"],
             "meta_len": surv["meta_len"], "fields": {str(k): v for k, v in surv["fields"].items()},
             "sections_present": surv["sections_present"]}
    assert set(gated.keys()) == schema.CONTAINER_CASE_KEYS
    raw = {"case": case["name"], "archive_sha256": sha(arc), "agxparse_path": surv["agxparse_sha256_path"]}
    arc.unlink()
    return gated, raw


def container_live_case(bin_dir, work_root, case, iotrace):
    kernels_dir = HERE / "kernels" / "generated"
    src = kernels_dir / case["file"]
    argv = [str(bin_dir / "containerdispatch"), "--source", str(src), "--function", case["function"],
            "--nbuf", str(case["nbuf"]), "--dump-wait-us", str(DUMP_WAIT_US)]
    dd = dump_dir_for(work_root, case["name"])
    logp = work_root / "logs" / (case["name"] + ".log.txt")
    logp.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, DYLD_INSERT_LIBRARIES=str(iotrace), IOTRACE_LOG=str(logp), IOTRACE_DUMP_DIR=str(dd))
    z = run_proc(argv, env, TIMEOUTS["container_live_case"])
    if z["timed_out"] or z["exit"] != 0:
        return ({"case": case["name"], "kind": "container_live", "function": case["function"],
                 "nbuf": case["nbuf"], "status": "proc_fail" if not z["timed_out"] else "proc_timeout",
                 "cb_status": None, "cdm_record_hex_normalized": None,
                 "arg_table_entry_count": None, "preamble_nonzero_len": None},
                {"case": case["name"], "receipt": z})
    matched, catalog = collect_matched(dd, scan.scan_cdm_segment)
    cdm_va = min(matched) if matched else None
    cdm_hex_norm = None
    if cdm_va is not None:
        p = glob.glob(str(dd / ("bo_sigusr1_h*_va%x_*.hex" % cdm_va)))[0]
        d = scan.load_hex_dump(p)
        rec = d["data"][0:schema.CDM_RECORD_LEN]
        cdm_hex_norm = schema.normalize_cdm_record(rec).hex()
    # argument-buffer table: the BO family member matching known EXP-0011
    # shape (largest 0x9480-ish compute-args BO); locate by size heuristic
    # bounded to registered BOs only, entries counted, VAs never gated.
    argtab_count = None
    argtab_path = None
    for c in catalog:
        if c["size"] in (0x9480,):
            argtab_path = glob.glob(str(dd / ("bo_sigusr1_h*_va%x_*.hex" % c["gpu_va"])))
            if argtab_path:
                argtab_path = argtab_path[0]
                break
    if argtab_path:
        d = scan.load_hex_dump(argtab_path)
        import struct as _s
        n = 0
        off = 0x14a0
        while off + 8 <= len(d["data"]):
            lo, hi = _s.unpack_from("<II", d["data"], off)
            if lo == 0 and hi == 0:
                break
            n += 1
            off += 8
        argtab_count = n
    preamble_len = None
    for c in catalog:
        if c["gpu_va"] in (0x10000090000,) or (0x10000080000 <= c["gpu_va"] <= 0x100000a0000 and c["size"] == 0x8000):
            pp = glob.glob(str(dd / ("bo_sigusr1_h*_va%x_*.hex" % c["gpu_va"])))
            if pp:
                d = scan.load_hex_dump(pp[0])
                nz = len(d["data"].rstrip(b"\x00"))
                preamble_len = max(preamble_len or 0, nz)
    gated = {"case": case["name"], "kind": "container_live", "function": case["function"],
             "nbuf": case["nbuf"], "status": "ok", "cb_status": 4,
             "cdm_record_hex_normalized": cdm_hex_norm, "arg_table_entry_count": argtab_count,
             "preamble_nonzero_len": preamble_len}
    assert set(gated.keys()) == schema.CONTAINER_LIVE_CASE_KEYS
    raw = {"case": case["name"], "cdm_va": hex(cdm_va) if cdm_va else None,
           "argtab_va": None, "catalog": catalog,
           "readback": [l for l in z["stdout"].splitlines() if l.startswith("READBACK")]}
    return gated, raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    if not args.execute:
        print("dry run only; pass --execute to run on the real M4 GPU")
        return 0

    raw_root = HERE / "raw" / args.run_id
    if raw_root.exists():
        raise SystemExit("run id already exists (never reuse): %s" % raw_root)
    work_root = HERE / "work" / args.run_id
    work_root.mkdir(parents=True, exist_ok=True)
    bin_dir = work_root / "bin"

    build_log = build(bin_dir)
    inputs = provenance()
    inputs["run_id"] = args.run_id
    inputs["started_at"] = datetime.datetime.utcnow().isoformat() + "Z"

    iotrace = bin_dir / "iotrace.dylib"

    # --- NON-RECORDED smoke gate: must succeed BEFORE raw/ is created -----
    smoke_dd = dump_dir_for(work_root, "SMOKE")
    smoke_log = work_root / "logs" / "SMOKE.log.txt"
    smoke_log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, DYLD_INSERT_LIBRARIES=str(iotrace), IOTRACE_LOG=str(smoke_log), IOTRACE_DUMP_DIR=str(smoke_dd))
    z = run_proc([str(bin_dir / "cmdprobe"), "--mode", "cdm", "--count", str(SMOKE_CASE["count"]),
                  "--dump-wait-us", str(DUMP_WAIT_US)], env, TIMEOUTS["smoke"])
    if z["timed_out"] or z["exit"] != 0 or "VERDICT completed=1" not in z["stdout"]:
        raise SystemExit("SMOKE GATE FAILED (pre-capture stop, no raw/ created): %r" % z)
    matched, _ = collect_matched(smoke_dd, scan.scan_cdm_segment)
    if not any(r["record_count"] == SMOKE_CASE["count"] for r in matched.values()):
        raise SystemExit("SMOKE GATE FAILED: authored CDM signature not found intact: %r" % matched)
    print("SMOKE GATE PASSED")

    raw_root.mkdir(parents=True)
    (raw_root / "00_inputs.json").write_text(json.dumps(inputs, indent=2, sort_keys=True) + "\n")
    (raw_root / "01_build.json").write_text(json.dumps(build_log, indent=2, sort_keys=True) + "\n")

    gated_path = raw_root / "02_results.jsonl"
    addrs_path = raw_root / "02_results_addrs.jsonl"  # sibling, NOT part of the cross-run gate
    gf = open(gated_path, "a")
    af = open(addrs_path, "a")

    def emit(gated, raw):
        gf.write(json.dumps(gated, sort_keys=True) + "\n")
        gf.flush(); os.fsync(gf.fileno())
        af.write(json.dumps(raw, sort_keys=True, default=str) + "\n")
        af.flush(); os.fsync(af.fileno())

    cdm_baseline_segs = None
    for case in CM.CDM_CASES:
        base = cdm_baseline_segs if case["name"] != CM.CDM_BASELINE_NAME else None
        result = cdm_case(bin_dir, work_root, case, base, iotrace)
        gated, raw = result[0], result[1]
        emit(gated, raw)
        if case["name"] == CM.CDM_BASELINE_NAME and len(result) > 2:
            cdm_baseline_segs = result[2]
        print("CDM", case["name"], gated["status"], gated["segment_count"], gated["total_records"])

    vdm_baseline_segs = None
    for case in CM.VDM_CASES:
        base = vdm_baseline_segs if case["name"] != CM.VDM_BASELINE_NAME else None
        result = vdm_case(bin_dir, work_root, case, base, iotrace)
        gated, raw = result[0], result[1]
        emit(gated, raw)
        if case["name"] == CM.VDM_BASELINE_NAME and len(result) > 2:
            vdm_baseline_segs = result[2]
        print("VDM", case["name"], gated["status"], gated["segment_count"], gated["total_records"])

    for case in CM.STATE_CASES:
        gated, raw = state_case(bin_dir, work_root, case, iotrace)
        emit(gated, raw)
        print("STATE", case["name"], gated["status"])

    for case in CM.CONTAINER_CASES:
        gated, raw = container_case(bin_dir, case)
        emit(gated, raw)
        print("CONTAINER", case["name"], gated["meta_len"])

    for case in CM.CONTAINER_LIVE_CASES:
        gated, raw = container_live_case(bin_dir, work_root, case, iotrace)
        emit(gated, raw)
        print("CONTAINER_LIVE", case["name"], gated["status"])

    gf.close(); af.close()
    manifest = {"run_id": args.run_id, "results_sha256": sha(gated_path),
               "completed_at": datetime.datetime.utcnow().isoformat() + "Z"}
    (raw_root / "03_run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("DONE", args.run_id, manifest["results_sha256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
