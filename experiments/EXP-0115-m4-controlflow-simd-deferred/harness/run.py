#!/usr/bin/env python3
"""run.py -- EXP-0115 capture driver.

Executes every case in matrix.py, each against a FRESH GPU-facing subprocess,
with a hard wall-clock timeout per case. Appends two JSONL files per run,
immediately (open/write/flush/fsync/close) after each case:

  raw/<run_id>.jsonl          -- GATED fields only: case id/item, status,
                                  verdict, per-lane/pixel RESULT values,
                                  splice notes, compile_limit status. Byte-for-
                                  byte reproducible given the frozen source
                                  blobs and revision.
  raw/<run_id>.nongated.jsonl -- NON-gated companion: GPUTIME_NS, full raw
                                  stdout/stderr tails, wall-clock timestamps,
                                  compile logs.

Usage: python3 run.py --run-id m4_<date>_run01 [--limit N] [--only PREFIX]
"""
import argparse
import datetime
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
import matrix

EXP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(EXP_ROOT, "raw")
WORK_DIR = os.path.join(EXP_ROOT, "work")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def blob_hashes():
    files = [
        os.path.join(EXP_ROOT, "kernels", "reach.metal"),
        os.path.join(EXP_ROOT, "kernels", "cf_pred.metal"),
        os.path.join(EXP_ROOT, "kernels", "shuf_static.metal"),
        os.path.join(EXP_ROOT, "kernels", "vote_frag.metal"),
        os.path.join(EXP_ROOT, "kernels", "width_frag.metal"),
        os.path.join(EXP_ROOT, "kernels", "sgbar_adv.metal"),
        os.path.join(EXP_ROOT, "harness", "matrix.py"),
        os.path.join(EXP_ROOT, "harness", "lib.py"),
        os.path.join(EXP_ROOT, "harness", "gen_deep_kernels.py"),
    ]
    h = {os.path.basename(p): sha256_file(p) for p in files}
    deep_dir = os.path.join(EXP_ROOT, "kernels", "deep")
    for fn in sorted(os.listdir(deep_dir)):
        h[f"deep/{fn}"] = sha256_file(os.path.join(deep_dir, fn))
    return h


def do_compute(case, workdir):
    out = lib.run_compute(case["source"], case["function"], case["grid"], case["tg"],
                           case.get("bufs", {}), case.get("outs", {}),
                           splices=case.get("_splices"),
                           run_timeout=case.get("run_timeout", 15.0),
                           workdir=workdir)
    res = {"case": case, "compute": out}
    verdict = None
    detail = None
    if case.get("oracle"):
        try:
            ok, detail = case["oracle"](res)
            verdict = "MATCH" if ok else "MISMATCH"
        except Exception as e:
            verdict = "ORACLE_ERROR"
            detail = {"exception": str(e)}
    return out, verdict, detail


def do_compile_limit(case, workdir):
    """item 2: attempt to compile the kernel. If it compiles, ALSO dispatch it
    for correctness (extending the HW-validated depth). If it fails to
    compile, record the exact (deterministic, toolchain-pinned) failure --
    this IS the expected/desired result at the boundary depths, not an error
    to hide."""
    tag = case["function"]
    cres = lib.compile_only(case["source"], case["function"], workdir=workdir, tag=tag)
    if cres["status"] != "OK":
        out = {"status": cres["status"], "compile_log_tail": cres["log_tail"]}
        return out, cres["status"], None
    out, verdict, detail = do_compute(case, workdir)
    out["compile_status"] = "OK"
    return out, verdict, detail


def do_locate_splice(case, workdir):
    target = case["locate_target"]
    if target == "reach_jump_offset":
        arch, hexstr, rc, log, timed_out = lib.compile_and_extract(
            case["source"], case["function"], workdir=workdir, tag="reach_locate")
        if hexstr is None:
            return {"status": "LOCATE_FAIL", "log": log[-2000:]}, "LOCATE_FAIL", None
        trc, tout, terr, ttimeout = lib.tokenize(hexstr)
        jump_off = None
        for line in tout.splitlines():
            s = line.strip()
            parts = s.split()
            if len(parts) >= 2 and parts[0].startswith("+0x") and parts[1] == "jump":
                jump_off = int(parts[0][1:], 16)
        if jump_off is None:
            return {"status": "LOCATE_FAIL", "tokenize_out": tout[-3000:]}, "LOCATE_FAIL", None
        off_byte_pos = jump_off + 3  # db.json: offset field starts at instr byte+3, 48 bits LE
        raw_off_bytes = bytes.fromhex(hexstr[off_byte_pos * 2: off_byte_pos * 2 + 12])
        cur_off = int.from_bytes(raw_off_bytes, "little", signed=True)
        new_off = cur_off + case["offset_delta"]
        new_bytes = (new_off & ((1 << 48) - 1)).to_bytes(6, "little")
        splice = f"_agc.main@{off_byte_pos:#x}={new_bytes.hex()}"
        out = lib.run_compute(case["source"], case["function"], case["grid"], case["tg"],
                               case.get("bufs", {}), case.get("outs", {}),
                               splices=[splice], run_timeout=8.0, timeout=13.0, workdir=workdir)
        out["_locate"] = {"jump_offset_field_pos": off_byte_pos, "baseline_offset": cur_off,
                           "delta": case["offset_delta"], "new_offset": new_off,
                           "splice_str": splice}
        return out, out.get("status"), None

    elif target == "predtest_dstpred_ifpush":
        arch, hexstr, rc, log, timed_out = lib.compile_and_extract(
            case["source"], case["function"], workdir=workdir, tag="predtest_locate")
        if hexstr is None:
            return {"status": "LOCATE_FAIL", "log": log[-2000:]}, "LOCATE_FAIL", None
        trc, tout, terr, ttimeout = lib.tokenize(hexstr)
        icmp_off = None
        for line in tout.splitlines():
            s = line.strip()
            parts = s.split()
            if len(parts) >= 2 and parts[0].startswith("+0x") and parts[1] == "icmp_pred":
                icmp_off = int(parts[0][1:], 16)
                break
        if icmp_off is None:
            return {"status": "LOCATE_FAIL", "tokenize_out": tout[-3000:]}, "LOCATE_FAIL", None
        ifpush_off = icmp_off + 6  # icmp_pred is 6 bytes; if_push follows immediately
        byte0_icmp = int(hexstr[icmp_off * 2: icmp_off * 2 + 2], 16)
        byte1_ifpush = int(hexstr[(ifpush_off + 1) * 2: (ifpush_off + 1) * 2 + 2], 16)
        assert (byte0_icmp & 0x0f) == 0x0a, f"expected icmp_pred low nibble at {icmp_off:#x}, got {byte0_icmp:#x}"
        assert (byte1_ifpush & 0x0f) == 0x05, f"expected if_push low nibble at {ifpush_off + 1:#x}, got {byte1_ifpush:#x}"
        new_icmp_byte0 = (case["dst_pred"] << 4) | 0x0a
        new_ifpush_byte1 = (case["ifpush_pred"] << 4) | 0x05
        splices = [
            f"_agc.main@{icmp_off:#x}={new_icmp_byte0:02x}",
            f"_agc.main@{ifpush_off + 1:#x}={new_ifpush_byte1:02x}",
        ]
        out = lib.run_compute(case["source"], case["function"], case["grid"], case["tg"],
                               case.get("bufs", {}), case.get("outs", {}),
                               splices=splices, workdir=workdir)
        out["_locate"] = {"icmp_pred_offset": icmp_off, "if_push_offset": ifpush_off,
                           "natural_icmp_byte0": byte0_icmp, "natural_ifpush_byte1": byte1_ifpush,
                           "dst_pred": case["dst_pred"], "ifpush_pred": case["ifpush_pred"],
                           "splice_strs": splices}
        return out, out.get("status"), None

    elif target == "static_shuffle_lane":
        arch, hexstr, rc, log, timed_out = lib.compile_and_extract(
            case["source"], case["shuffle_fn"], workdir=workdir, tag=f"{case['shuffle_fn']}_locate")
        if hexstr is None:
            return {"status": "LOCATE_FAIL", "log": log[-2000:]}, "LOCATE_FAIL", None
        trc, tout, terr, ttimeout = lib.tokenize(hexstr)
        shuf_off = None
        for line in tout.splitlines():
            s = line.strip()
            parts = s.split()
            if len(parts) >= 2 and parts[0].startswith("+0x") and parts[1] == "simd_shuffle":
                shuf_off = int(parts[0][1:], 16)
                break
        if shuf_off is None:
            return {"status": "LOCATE_FAIL", "tokenize_out": tout[-3000:]}, "LOCATE_FAIL", None
        lane_off = shuf_off + 6  # db.json: "lane" field starts at instr byte+6
        natural_lane = int(hexstr[lane_off * 2: lane_off * 2 + 2], 16)
        new_raw = case["lane_raw"]
        splice = f"_agc.main@{lane_off:#x}={new_raw:02x}"
        out = lib.run_compute(case["source"], case["shuffle_fn"], case["grid"], case["tg"],
                               case.get("bufs", {}), case.get("outs", {}),
                               splices=[splice], workdir=workdir)
        out["_locate"] = {"shuffle_offset": shuf_off, "lane_field_offset": lane_off,
                           "natural_lane_raw": natural_lane, "spliced_lane_raw": new_raw,
                           "splice_str": splice}
        return out, out.get("status"), None

    else:
        raise ValueError(f"unknown locate_target {target}")


def do_structural_pair(case, workdir):
    a_arch, a_hex, a_rc, a_log, a_to = lib.compile_and_extract(
        case["source"], case["function_a"], workdir=workdir, tag=f"struct_{case['function_a']}")
    b_arch, b_hex, b_rc, b_log, b_to = lib.compile_and_extract(
        case["source"], case["function_b"], workdir=workdir, tag=f"struct_{case['function_b']}")
    out = {"status": "OK" if (a_hex and b_hex) else "COMPILE_FAIL",
           "a_len": len(a_hex) // 2 if a_hex else None,
           "b_len": len(b_hex) // 2 if b_hex else None,
           "a_hex": a_hex, "b_hex": b_hex,
           "identical": (a_hex == b_hex) if (a_hex and b_hex) else None}
    return out, out["status"], None


def do_structural_group(case, workdir):
    results = {}
    for fn in case["functions"]:
        arch, hexstr, rc, log, to = lib.compile_and_extract(
            case["source"], fn, workdir=workdir, tag=f"struct_{fn}")
        results[fn] = {"len": len(hexstr) // 2 if hexstr else None, "hex": hexstr}
    lens = {k: v["len"] for k, v in results.items()}
    base_hex = results.get(case["functions"][0], {}).get("hex")
    identical_to_base = {k: (v["hex"] == base_hex) for k, v in results.items()}
    out = {"status": "OK" if all(v["len"] is not None for v in results.values()) else "COMPILE_FAIL",
           "lens": lens, "identical_to_base": identical_to_base, "results": results}
    return out, out["status"], None


def do_render(case, workdir):
    out = lib.run_render(case["source"], case["vertex"], case["fragment"],
                          case["width"], case["height"], workdir=workdir,
                          tag=f"{case['fragment']}_{case['width']}x{case['height']}")
    return out, out.get("status"), None


def strip_nongated(d):
    """Split a raw case-output dict into (gated, nongated) sub-dicts."""
    nongated_keys = {"gputime_ns", "stderr_tail", "compile_out", "timed_out", "rc",
                      "compile_timed_out", "compile_rc", "compile_log_tail", "log_tail"}
    gated = {}
    nongated = {}
    for k, v in d.items():
        if k in nongated_keys:
            nongated[k] = v
        else:
            gated[k] = v
    return gated, nongated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only", default=None, help="only run case ids starting with this prefix")
    args = ap.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(WORK_DIR, exist_ok=True)
    gated_path = os.path.join(RAW_DIR, f"{args.run_id}.jsonl")
    nongated_path = os.path.join(RAW_DIR, f"{args.run_id}.nongated.jsonl")
    if os.path.exists(gated_path):
        print(f"REFUSING to overwrite existing {gated_path} -- run ids are never reused", file=sys.stderr)
        sys.exit(1)

    gw = lib.RecordWriter(gated_path)
    nw = lib.RecordWriter(nongated_path)

    cases = matrix.build_matrix()
    if args.only:
        cases = [c for c in cases if c["id"].startswith(args.only)]
    if args.limit:
        cases = cases[:args.limit]

    manifest_meta = {
        "run_id": args.run_id, "started_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "total_cases": len(cases), "blob_hashes": blob_hashes(),
    }
    nw.append({"_meta": manifest_meta})
    gw.append({"_meta": {"run_id": args.run_id, "total_cases": len(cases),
                          "blob_hashes": manifest_meta["blob_hashes"]}})

    n_ok = n_mismatch = n_fault = n_hang = n_other = 0
    for idx, case in enumerate(cases):
        t0 = time.time()
        case_id = case["id"]
        workdir = os.path.join(WORK_DIR, "run_" + args.run_id)
        os.makedirs(workdir, exist_ok=True)
        kind = case["kind"]
        try:
            if kind == "compute":
                out, verdict, detail = do_compute(case, workdir)
            elif kind == "locate_splice":
                out, verdict, detail = do_locate_splice(case, workdir)
            elif kind == "compile_limit":
                out, verdict, detail = do_compile_limit(case, workdir)
            elif kind == "structural_pair":
                out, verdict, detail = do_structural_pair(case, workdir)
            elif kind == "structural_group":
                out, verdict, detail = do_structural_group(case, workdir)
            elif kind == "render":
                out, verdict, detail = do_render(case, workdir)
            else:
                out, verdict, detail = {"status": "UNKNOWN_KIND"}, "UNKNOWN_KIND", None
        except Exception as e:
            out, verdict, detail = {"status": "DRIVER_EXCEPTION"}, "DRIVER_EXCEPTION", {"exception": repr(e)}
        dt = time.time() - t0

        status = out.get("status", "UNKNOWN")
        if status == "OK" and verdict in (None, "MATCH"):
            n_ok += 1
        elif verdict == "MISMATCH":
            n_mismatch += 1
        elif status == "HANG" or out.get("timed_out"):
            n_hang += 1
        elif "FAIL" in str(status) or "ERROR" in str(status) or "CMDBUF" in str(status) or "TIMEOUT" in str(status):
            n_fault += 1
        else:
            n_other += 1

        gated_out, nongated_out = strip_nongated(out)
        case_public = {k: v for k, v in case.items() if k not in ("oracle",)}

        gw.append({
            "run_id": args.run_id, "seq": idx, "case_id": case_id, "item": case["item"],
            "kind": kind, "note": case.get("note"), "status": status, "verdict": verdict,
            "detail": detail, "out": gated_out, "case_params": case_public,
        })
        nw.append({
            "run_id": args.run_id, "seq": idx, "case_id": case_id,
            "wall_seconds": round(dt, 3), "out_nongated": nongated_out,
        })
        print(f"[{idx+1}/{len(cases)}] {case_id:28s} status={status:16s} "
              f"verdict={str(verdict):10s} {dt:.2f}s")

    summary = {"run_id": args.run_id, "n_cases": len(cases), "n_ok": n_ok,
               "n_mismatch": n_mismatch, "n_fault": n_fault, "n_hang": n_hang,
               "n_other": n_other, "finished_utc": datetime.datetime.utcnow().isoformat() + "Z"}
    nw.append({"_summary": summary})
    print(f"DONE {args.run_id}: ok={n_ok} mismatch={n_mismatch} fault={n_fault} "
          f"hang={n_hang} other={n_other} / {len(cases)} total")


if __name__ == "__main__":
    main()
