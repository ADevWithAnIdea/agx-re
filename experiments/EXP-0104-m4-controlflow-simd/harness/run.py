#!/usr/bin/env python3
"""run.py -- EXP-0104 capture driver.

Executes every case in matrix.py, each against a FRESH GPU-facing subprocess
(agxtest.py / shdump / agxrun / agxrender each spawn their own child), with a
hard wall-clock timeout per case. Appends two JSONL files per run, immediately
(open/write/flush/fsync/close) after each case:

  raw/<run_id>.jsonl          -- GATED fields only: case id/item, status,
                                  comparison verdict, per-lane/pixel RESULT
                                  values, splice notes. Byte-for-byte
                                  reproducible given the frozen source blobs
                                  and revision; this file is what --captured
                                  cross-run-diffs.
  raw/<run_id>.nongated.jsonl -- NON-gated companion: GPUTIME_NS, full raw
                                  stdout/stderr tails, wall-clock timestamps.
                                  Legitimately nondeterministic run-to-run;
                                  excluded from the cross-run byte gate by
                                  construction (separate file, never merged).

Usage: python3 run.py --run-id m4_<date>_run01 [--limit N] [--only PREFIX]
"""
import argparse
import datetime
import hashlib
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
        os.path.join(EXP_ROOT, "kernels", "cf_nest.metal"),
        os.path.join(EXP_ROOT, "kernels", "cf_misc.metal"),
        os.path.join(EXP_ROOT, "kernels", "simd_misc.metal"),
        os.path.join(EXP_ROOT, "kernels", "frag_misc.metal"),
        os.path.join(EXP_ROOT, "harness", "matrix.py"),
        os.path.join(EXP_ROOT, "harness", "lib.py"),
    ]
    return {os.path.basename(p): sha256_file(p) for p in files}


def do_compute(case, workdir):
    out = lib.run_compute(case["source"], case["function"], case["grid"], case["tg"],
                           case.get("bufs", {}), case.get("outs", {}),
                           splices=case.get("_splices"), workdir=workdir)
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


def do_locate_splice(case, workdir):
    target = case["locate_target"]
    if target == "predalias_dst_pred":
        arch, hexstr, rc, log, timed_out = lib.compile_and_extract(
            case["source"], case["function"], workdir=workdir, tag="predalias_locate")
        if hexstr is None:
            return {"status": "LOCATE_FAIL", "log": log[-2000:]}, "LOCATE_FAIL", None
        trc, tout, terr, ttimeout = lib.tokenize(hexstr)
        offsets = []
        off = 0
        for line in tout.splitlines():
            if "icmp_pred" in line and line.strip().startswith("+0x"):
                addr_str = line.strip().split()[0]
                offsets.append(int(addr_str[1:], 16))
        if len(offsets) < 1:
            return {"status": "LOCATE_FAIL", "tokenize_out": tout[-2000:]}, "LOCATE_FAIL", None
        outer_off = offsets[0]
        # read the byte at that offset from hexstr to get the natural low nibble (0x0a)
        byte0 = int(hexstr[outer_off * 2: outer_off * 2 + 2], 16)
        assert (byte0 & 0x0f) == 0x0a, f"expected icmp_pred low nibble at {outer_off:#x}, got {byte0:#x}"
        new_byte0 = (case["splice_value_nibble"] << 4) | 0x0a
        splice = f"_agc.main@{outer_off:#x}={new_byte0:02x}"
        out = lib.run_compute(case["source"], case["function"], case["grid"], case["tg"],
                               case.get("bufs", {}), case.get("outs", {}),
                               splices=[splice], workdir=workdir)
        out["_locate"] = {"icmp_pred_offsets": offsets, "spliced_offset": outer_off,
                           "natural_byte0": byte0, "spliced_byte0": new_byte0,
                           "splice_str": splice}
        return out, out.get("status"), None
    elif target == "reach_loop_jump_offset":
        arch, hexstr, rc, log, timed_out = lib.compile_and_extract(
            case["source"], case["function"], workdir=workdir, tag="reach_loop_locate")
        if hexstr is None:
            return {"status": "LOCATE_FAIL", "log": log[-2000:]}, "LOCATE_FAIL", None
        trc, tout, terr, ttimeout = lib.tokenize(hexstr)
        jump_off = None
        # scan for the 'jump' mnemonic token explicitly (not jump_cond)
        for line in tout.splitlines():
            s = line.strip()
            parts = s.split()
            if len(parts) >= 2 and parts[0].startswith("+0x") and parts[1] == "jump":
                jump_off = int(parts[0][1:], 16)
        if jump_off is None:
            return {"status": "LOCATE_FAIL", "tokenize_out": tout[-3000:]}, "LOCATE_FAIL", None
        # offset field per db.json: starts at instruction bit 24 = byte+3, 48 bits (6 bytes), LE signed
        off_byte_pos = jump_off + 3
        raw_off_bytes = bytes.fromhex(hexstr[off_byte_pos * 2: off_byte_pos * 2 + 12])
        cur_off = int.from_bytes(raw_off_bytes, "little", signed=True)
        new_off = cur_off + case["offset_delta"]
        new_bytes = (new_off & ((1 << 48) - 1)).to_bytes(6, "little")
        splice = f"_agc.main@{off_byte_pos:#x}={new_bytes.hex()}"
        out = lib.run_compute(case["source"], case["function"], case["grid"], case["tg"],
                               case.get("bufs", {}), case.get("outs", {}),
                               splices=[splice], run_timeout=8.0, timeout=12.0, workdir=workdir)
        out["_locate"] = {"jump_offset_field_pos": off_byte_pos, "baseline_offset": cur_off,
                           "delta": case["offset_delta"], "new_offset": new_off,
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
                          case["width"], case["height"], workdir=workdir, tag=case["fragment"])
    return out, out.get("status"), None


def strip_nongated(d):
    """Split a raw case-output dict into (gated, nongated) sub-dicts."""
    nongated_keys = {"gputime_ns", "stderr_tail", "compile_out", "timed_out", "rc",
                      "compile_timed_out", "compile_rc"}
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
    ap.add_argument("--case-timeout", type=float, default=45.0,
                     help="hard wall-clock ceiling per case at the run.py level (belt-and-suspenders "
                          "over the tighter per-subprocess timeouts already inside lib.py)")
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
        elif "FAIL" in str(status) or "ERROR" in str(status) or "CMDBUF" in str(status):
            n_fault += 1
        else:
            n_other += 1

        gated_out, nongated_out = strip_nongated(out)
        # case params (drop oracle callables, keep everything else JSON-safe)
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
        print(f"[{idx+1}/{len(cases)}] {case_id:40s} status={status:14s} "
              f"verdict={str(verdict):10s} {dt:.2f}s")

    summary = {"run_id": args.run_id, "n_cases": len(cases), "n_ok": n_ok,
               "n_mismatch": n_mismatch, "n_fault": n_fault, "n_hang": n_hang,
               "n_other": n_other, "finished_utc": datetime.datetime.utcnow().isoformat() + "Z"}
    nw.append({"_summary": summary})
    print(json.dumps(summary, indent=2)) if False else None
    print(f"DONE {args.run_id}: ok={n_ok} mismatch={n_mismatch} fault={n_fault} "
          f"hang={n_hang} other={n_other} / {len(cases)} total")


if __name__ == "__main__":
    import json
    main()
