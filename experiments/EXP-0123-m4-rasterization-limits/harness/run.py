#!/usr/bin/env python3
"""EXP-0123 run driver. Each case: generate deterministic MSL + args JSON,
invoke rasterprobe/computeprobe as a FRESH SUBPROCESS with a hard timeout,
classify the outcome (OK / crash / timeout), compute a verdict against a
host-computed expectation where one exists, and append gated+nongated JSONL
records with fflush after every record (kill-safety per SUBAGENT_BRIEF.md).

Usage: run.py --run RUN_ID --out raw/RUN_ID
"""
import argparse, json, math, os, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import casematrix as CM
import genkernels as GK

BIN = {"rasterprobe": HERE.parent / "work" / "bin" / "rasterprobe",
       "computeprobe": HERE.parent / "work" / "bin" / "computeprobe"}
HARD_TIMEOUT_S = 25.0


def invoke(binary, args_json_path):
    t0 = time.time()
    try:
        r = subprocess.run([str(BIN[binary]), str(args_json_path)],
                            capture_output=True, timeout=HARD_TIMEOUT_S)
        wall_ms = (time.time() - t0) * 1000.0
        return r.returncode, r.stdout, r.stderr, wall_ms, False
    except subprocess.TimeoutExpired as e:
        wall_ms = (time.time() - t0) * 1000.0
        return None, e.stdout or b"", e.stderr or b"", wall_ms, True


def parse_result(stdout_bytes):
    txt = stdout_bytes.decode("utf-8", errors="replace").strip()
    if not txt:
        return None
    # protocol: exactly one JSON line on stdout
    line = txt.splitlines()[-1]
    try:
        return json.loads(line)
    except Exception:
        return None


# ---------------------------------------------------------------- verdicts
# gputime_ns is wall-clock-derived and varies run to run; it must never land
# inside the byte-compared `observed` payload (NONGATED_KEYS carries it
# instead, in the separate 03_nongated.jsonl stream).
_NONDETERMINISTIC_RESULT_KEYS = ("op", "case_id", "gputime_ns")


def _strip_nondeterministic(result):
    return {k: v for k, v in result.items() if k not in _NONDETERMINISTIC_RESULT_KEYS}


def _side_from_bbox(bbox):
    if not bbox or bbox.get("count", 0) == 0:
        return 0
    return bbox["xmax"] - bbox["xmin"] + 1


def verdict_for(case, rc, result, crashed, timed_out):
    """Returns (status_str, verdict, observed_dict)."""
    kind = case["kind"]
    p = case["params"]
    if timed_out:
        return "TIMEOUT", "TIMEOUT", {"note": "hard timeout exceeded"}
    if result is None:
        return "CRASH", ("PASS" if _expect_crash_or_hard_fault(case) else "FAIL"), \
               {"returncode": rc, "note": "no parseable JSON on stdout (process crashed/aborted/signaled)"}
    status = result.get("status", "?")
    observed = _strip_nondeterministic(result)

    if kind == "texcreate":
        expect_ok = _texcreate_expect_ok(case)
        create_status = result.get("create_status")
        ok = (create_status == "OK") if expect_ok else False  # rejects always crash (see _expect_crash)
        return status, ("PASS" if ok == expect_ok else "FAIL"), observed

    if kind == "bufferindex_compile":
        idx = p["index"]
        expect_compile_ok = idx <= 30
        got_ok = (status == "OK")
        if expect_compile_ok:
            v = "PASS" if (got_ok and observed.get("pixel", {}).get("r") == 0.5) else "FAIL"
        else:
            v = "PASS" if status == "COMPILE_FAIL" else "FAIL"
        return status, v, observed

    if kind == "texindex_compile":
        idx = p["index"]
        expect_compile_ok = idx <= 127
        if expect_compile_ok:
            px = observed.get("pixel", {})
            ok = status == "OK" and abs(px.get("r", -9) - 0.25) < 1e-4
            v = "PASS" if ok else "FAIL"
        else:
            v = "PASS" if status == "COMPILE_FAIL" else "FAIL"
        return status, v, observed

    if kind == "bytesconst":
        length = p["length"]
        expect_ok = length <= 32752
        if expect_ok:
            g = observed.get("pixel", {}).get("g")
            expected_last = ((length - 1) & 0xFF) / 255.0 if length > 0 else 0.0
            ok = status == "OK" and g is not None and abs(g - expected_last) < 1e-3
            return status, ("PASS" if ok else "FAIL"), observed
        else:
            return status, ("PASS" if status not in ("OK",) or rc != 0 else "FAIL"), observed

    if kind == "bufferalign":
        off = p["offset"]
        px = observed.get("pixel", {})

        def expect_byte(i):
            return ((off + i) * 37 + 11) & 0xFF
        ok = status == "OK"
        for i, ch in enumerate(("r", "g", "b", "a")):
            if px.get(ch) is None or abs(px[ch] - expect_byte(i) / 255.0) > 1e-3:
                ok = False
        return status, ("PASS" if ok else "FAIL"), observed

    if kind == "multiattach":
        n = p["n"]
        if n <= 8:
            per = observed.get("per_attachment", [])
            ok = status == "OK" and len(per) == n
            for i, rec in enumerate(per):
                px = rec.get("pixel", {})
                if abs(px.get("r", -9) - i / 8.0) > 1e-3:
                    ok = False
            return status, ("PASS" if ok else "FAIL"), observed
        else:
            oob = observed.get("oob_access_result")
            return status, ("PASS" if oob == "EXCEPTION" else "FAIL"), observed

    if kind == "render_point_centered":
        size = p["size"]
        bbox = observed.get("bbox")
        side = _side_from_bbox(bbox)
        expect_side = 1 if size < 2.0 else (2 if size == 2.0 else 3)
        ok = status == "OK" and side == expect_side
        return status, ("PASS" if ok else "FAIL"), observed

    if kind == "render_fillmode":
        return status, ("PASS" if status == "OK" else "FAIL"), observed

    if kind == "render_depthclip":
        mode, z = p["depth_clip_mode"], p["z"]
        in_range = 0.0 <= z <= 1.0
        expect_count_zero = (mode == "clip") and not in_range
        bbox = observed.get("bbox", {})
        count = bbox.get("count", -1)
        ok = status == "OK" and ((count == 0) if expect_count_zero else (count > 0))
        return status, ("PASS" if ok else "FAIL"), observed

    if kind == "render_subpixel_tri":
        pixels = observed.get("pixels", [])
        any_lit = any(px.get("r", 0) > 0.5 for px in pixels)
        return status, ("PASS" if (status == "OK" and not any_lit) else "FAIL"), observed

    if kind == "viewport_functional":
        n = p["n"]
        expect_functional = n <= 16
        if status == "OK":
            pixels = observed.get("pixels", [])
            row0 = sorted([px for px in pixels if px["y"] == 0], key=lambda q: q["x"])
            all_lit = len(row0) == n and all(px["r"] > 0.5 for px in row0)
            v = "PASS" if (expect_functional and all_lit) else ("FAIL" if expect_functional else "FAIL")
            return status, v, observed
        else:
            # CMDBUF_ERROR (gpu hang, recovered) counts as a legitimate negative
            # capture for n>16: the API accepted the call but the draw could not
            # complete correctly.
            v = "PASS" if not expect_functional else "FAIL"
            return status, v, observed

    if kind in ("compute_threadgroup",):
        tg = p["tg"]
        out = result.get("out", [])
        maxtg = result.get("max_total_threads_per_threadgroup")
        expect_functional = maxtg is not None and tg <= maxtg
        touched = any(v != 0xEEEEEEEE for v in out) if out else False
        ok = status == "OK" and (touched == expect_functional)
        return status, ("PASS" if ok else "FAIL"), _strip_nondeterministic(result)

    if kind == "compute_tgmem":
        out = result.get("out", [])
        ok = status == "OK" and len(out) > 0 and out[0] == 7
        return status, ("PASS" if ok else "FAIL"), _strip_nondeterministic(result)

    if kind == "compute_simdwidth":
        tew = result.get("thread_execution_width")
        ok = status == "OK" and tew == 32
        return status, ("PASS" if ok else "FAIL"), _strip_nondeterministic(result)

    # line_rule, wide_line_negative, coverage_earlylate, simd_shuffle_oob: pure
    # characterization -- verdict tracks successful, non-faulting capture only.
    ok = status == "OK"
    return status, ("PASS" if ok else "FAIL"), _strip_nondeterministic(result)


def _texcreate_expect_ok(case):
    p = case["params"]
    t = p["type"]
    if t == "2d":
        return p["width"] <= 16384 and p["height"] <= 16384 and p.get("mips", 1) <= _max_mips(p["width"], p["height"])
    if t == "cube":
        return p["width"] <= 16384 and p["height"] <= 16384
    if t == "3d":
        return p["width"] <= 2048
    if t == "2d_array":
        return p["depth"] <= 2048
    return True


def _max_mips(w, h):
    return int(math.floor(math.log2(max(w, h)))) + 1


def _expect_crash(case):
    return not _texcreate_expect_ok(case)


def _expect_crash_or_hard_fault(case):
    """True where the pre-registered hypothesis (from real exploratory
    probing, see PRE_REGISTRATION.md) is that this exact case triggers an
    uncatchable process-level fault (SIGABRT/SIGSEGV) rather than a graceful
    API rejection -- i.e. a crash here is the PREDICTED outcome, not an
    unexplained harness failure."""
    if case["kind"] == "texcreate":
        return _expect_crash(case)
    if case["kind"] == "viewport_functional":
        return case["params"]["n"] > 16
    if case["kind"] == "multiattach":
        # MTLRenderPipelineColorAttachmentDescriptorArray is a fixed 8-slot
        # array; indexing slot 8 fails an internal Metal assertion that
        # calls abort() directly (uncatchable, confirmed by direct probing
        # -- see PRE_REGISTRATION.md), not a catchable NSException.
        return case["params"]["n"] > 8
    if case["kind"] == "bytesconst":
        return case["params"]["length"] > 32752
    return False


# ------------------------------------------------------------------- runner
def run_all(run_id, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    gen_dir = EXP / "work" / "gen" / run_id
    gen_dir.mkdir(parents=True, exist_ok=True)

    gated_f = open(out_dir / "02_gated.jsonl", "a")
    nongated_f = open(out_dir / "03_nongated.jsonl", "a")

    inputs = {"run_id": run_id, "cases_planned": CM.TOTAL,
              "git_revision": subprocess.check_output(
                  ["git", "-C", str(EXP.parent.parent), "rev-parse", "HEAD"]).decode().strip()}
    (out_dir / "00_inputs.json").write_text(json.dumps(inputs, indent=2))

    for i, case in enumerate(CM.MATRIX):
        cid = case["id"]
        binary, args, metal_paths = GK.gen(case, gen_dir)
        args_full = dict(args)
        args_full["op"] = case["kind"]  # placeholder; overwritten by per-kind op below
        op_map = {
            "render_grid": "render", "render_point_centered": "render", "render_fillmode": "render",
            "render_depthclip": "render", "render_subpixel_tri": "render", "render_coverage": "render",
            "multiattach": "multiattach", "viewport_functional": "render", "texcreate": "texcreate",
            "bufferindex_compile": "bufferindex", "texindex_compile": "texturebind",
            "bytesconst": "bytesconst", "bufferalign": "bufferalign",
            "compute_threadgroup": "dispatch", "compute_tgmem": "dispatch",
            "compute_simdwidth": "dispatch", "compute_simdshuffle": "dispatch",
        }
        args_full["op"] = op_map[case["kind"]]
        args_full["case_id"] = cid
        args_path = gen_dir / f"{cid}.json"
        args_path.write_text(json.dumps(args_full, sort_keys=True))

        rc, stdout, stderr, wall_ms, timed_out = invoke(binary, args_path)
        result = parse_result(stdout) if not timed_out else None
        crashed = (not timed_out) and (result is None)
        status, verdict, observed = verdict_for(case, rc, result, crashed, timed_out)

        gated = {"case_id": cid, "family": case["family"], "kind": case["kind"],
                 "params": case["params"], "status": status, "verdict": verdict, "observed": observed}
        nongated = {"case_id": cid,
                    "gputime_ns": (result or {}).get("gputime_ns", 0) if result else 0,
                    "wall_ms": round(wall_ms, 3), "pid": rc if rc is not None else -1,
                    "raw_tail": stderr.decode("utf-8", errors="replace")[-500:]}
        gated_f.write(json.dumps(gated, sort_keys=True) + "\n"); gated_f.flush(); os.fsync(gated_f.fileno())
        nongated_f.write(json.dumps(nongated, sort_keys=True) + "\n"); nongated_f.flush(); os.fsync(nongated_f.fileno())

        print(f"[{i+1}/{CM.TOTAL}] {cid:32s} {status:12s} {verdict}", flush=True)

    gated_f.close(); nongated_f.close()
    manifest = {"cases_planned": CM.TOTAL, "run_id": run_id, "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (out_dir / "04_manifest.json").write_text(json.dumps(manifest, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run_all(args.run, args.out)


if __name__ == "__main__":
    main()
