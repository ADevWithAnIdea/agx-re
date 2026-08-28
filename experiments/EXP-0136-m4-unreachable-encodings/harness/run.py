#!/usr/bin/env python3
"""EXP-0136 run driver. Each case invokes ONE FRESH SUBPROCESS (descpatch,
gfxprobe, or agxtest.py depending on case["mechanism"]) with a hard timeout,
classifies the outcome, and appends gated+nongated JSONL records with
fflush+fsync after every record (kill-safety per SUBAGENT_BRIEF.md).

Usage: run.py --run RUN_ID --out raw/RUN_ID
"""
import argparse, json, os, subprocess, sys, time, shutil
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import casematrix as CM

WORK = EXP / "work"
BIN = WORK / "bin"
HARD_TIMEOUT_S = 25.0
AGXTEST_TIMEOUT_S = 40.0  # covers shdump compile + agxrun dispatch


# --------------------------------------------------------------- helpers
def run_subprocess(argv, env, timeout):
    t0 = time.time()
    try:
        r = subprocess.run(argv, capture_output=True, timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr, (time.time() - t0) * 1000.0, False
    except subprocess.TimeoutExpired as e:
        return None, e.stdout or b"", e.stderr or b"", (time.time() - t0) * 1000.0, True


def parse_json_line(stdout_bytes):
    txt = stdout_bytes.decode("utf-8", errors="replace").strip()
    if not txt:
        return None
    line = txt.splitlines()[-1]
    try:
        return json.loads(line)
    except Exception:
        return None


# arg_bo_cpu/desc_bo_cpu are the LIVE CPU-side pointer values descpatch.m
# reads out of Metal's own resource-registration data for its own in-process
# patch (see harness/descpatch.m). Confirmed by a non-recorded smoke run
# (work/smoke/, 5 descpatch cases in one batch): every GPU-VA-space field
# (arg_bo_gpu_va, tex_desc_gpu_va, smp_desc_gpu_va, out_gpu_va, slot2_off,
# desc_off_in_bo, n_bos_loaded) is DETERMINISTIC per case shape across
# separate process launches -- GPU VA space is not ASLR'd on this platform for
# this allocation pattern -- but arg_bo_cpu/desc_bo_cpu (ordinary CPU heap
# addresses) vary every single process launch (standard macOS ASLR). These are
# a harness bookkeeping artifact, not a hardware fact under test, so per the
# standing "no nondeterministic field in byte-compared records" gate they are
# stripped from the gated `observed` payload here (never claimed as a
# hardware finding) rather than promoted to their own excluded-fields dance;
# nongated raw process stdout is preserved for audit via the raw_tail field
# regardless.
_NONDET_KEYS = ("gputime_ns", "wall_ms", "pid", "raw_tail", "arg_bo_cpu", "desc_bo_cpu")


def _strip_nondet(d):
    return {k: v for k, v in d.items() if k not in _NONDET_KEYS}


# ------------------------------------------------------- descpatch case build
_ANISO_CODE = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4, 32: 5, 64: 6, 128: 7}


def build_descpatch_case(case):
    k, p = case["kind"], case["params"]
    if k in ("aniso_real", "aniso_patch"):
        ratio = p["ratio"]
        uvg = [0.5, 1.5 / 32.0, ratio / 32.0, 1.0 / 32.0]
        creation_aniso = p["aniso"] if k == "aniso_real" else 16
        sampler = {"min_filter": "nearest", "mag_filter": "nearest", "mip_filter": "linear",
                   "address_s": "repeat", "address_t": "clampToEdge", "aniso": creation_aniso}
        patch = []
        if k == "aniso_patch":
            code = _ANISO_CODE[p["aniso"]]
            patch = [{"byte": 2, "mask": 112, "value": code << 4}]
        return {"target": "sampler", "pattern": "ystripe", "tex_w": 32, "tex_h": 32, "mip_count": 6,
                "sampler": sampler, "uvg": uvg, "patch": patch}
    if k == "addrmode":
        code, u = p["code"], p["u"]
        sampler = {"min_filter": "nearest", "mag_filter": "nearest", "mip_filter": "notMipmapped",
                   "address_s": "clampToEdge", "address_t": "clampToEdge", "aniso": 1}
        patch = [{"byte": 3, "mask": 224, "value": code << 5}]
        return {"target": "sampler", "pattern": "grid", "tex_w": 4, "tex_h": 4, "mip_count": 1,
                "sampler": sampler, "uvg": [u, 0.5, 0.001, 0.001], "patch": patch}
    if k == "border":
        code = p["code"]
        sampler = {"min_filter": "nearest", "mag_filter": "nearest", "mip_filter": "notMipmapped",
                   "address_s": "clampToBorderColor", "address_t": "clampToBorderColor", "aniso": 1,
                   "border": p["creation_border"]}
        patch = [{"byte": 7, "mask": 96, "value": code << 5}]
        return {"target": "sampler", "pattern": "grid", "tex_w": 4, "tex_h": 4, "mip_count": 1,
                "sampler": sampler, "uvg": [2.7, 2.7, 0.001, 0.001], "patch": patch}
    if k == "swizzle":
        comp, code = p["component"], p["code"]
        mask = 0x07 if comp == 0 else 0x38
        value = code if comp == 0 else (code << 3)
        sampler = {"min_filter": "nearest", "mag_filter": "nearest", "mip_filter": "notMipmapped",
                   "address_s": "clampToEdge", "address_t": "clampToEdge", "aniso": 1}
        patch = [{"byte": 2, "mask": mask, "value": value}]
        return {"target": "texture", "pattern": "grid", "tex_w": 4, "tex_h": 4, "mip_count": 1,
                "sampler": sampler, "uvg": [0.5, 0.5, 0.001, 0.001], "patch": patch}
    raise ValueError(k)


def build_gfxprobe_case(case):
    k, p = case["kind"], case["params"]
    if k == "restart":
        d = {"op": "restart_line", "index_type": p["index_type"]}
        if p["sentinel_kind"] == "allones_minus1":
            d["sentinel"] = 65534 if p["index_type"] == "u16" else 4294967294
        elif p["sentinel_kind"] == "small_oob":
            d["sentinel"] = p["sentinel"]
        return d
    if k == "norender":
        return {"op": "norender_draw", "raster_enabled": p["raster_enabled"]}
    raise ValueError(k)


# --------------------------------------------------------------- expectations
_GRID_X, _GRID_Y = 2, 2  # nearest texel sampled at u=v=0.5 in a 4x4 "grid" texture
_GRID_R = (_GRID_Y * 4 + _GRID_X) / 15.0
_GRID_G = 200.0 / 255.0
_GRID_B = (_GRID_X * 20) / 255.0
_BORDER_EXPECT = {0: (0.0, 0.0, 0.0, 0.0), 1: (0.0, 0.0, 0.0, 1.0), 2: (1.0, 1.0, 1.0, 1.0)}
_SWZ0_EXPECT = {0: _GRID_R, 1: _GRID_G, 2: _GRID_B, 3: 1.0, 4: 1.0, 5: 0.0}
_SWZ1_EXPECT = {0: _GRID_R, 4: 1.0}  # component1 (G-dst) subset tested


def approx(a, b, tol=0.02):
    return a is not None and abs(a - b) <= tol


def verdict_descpatch(case, result):
    k, p = case["kind"], case["params"]
    if result is None:
        return "CRASH", "FAIL", {"note": "no parseable JSON on stdout"}
    status = result.get("status", "?")
    observed = _strip_nondet(result)
    if k in ("aniso_real", "aniso_patch"):
        return status, ("PASS" if status == "OK" else "FAIL"), observed
    if k == "addrmode":
        return status, ("PASS" if status == "OK" else "FAIL"), observed
    if k == "border":
        code = p["code"]
        pixel = result.get("pixel")
        if status != "OK" or not pixel:
            return status, "FAIL", observed
        if code in _BORDER_EXPECT:
            exp = _BORDER_EXPECT[code]
            ok = all(approx(pixel[i], exp[i]) for i in range(4))
        else:  # code 3: must be a well-defined (non-garbage) result close to ONE of the 3 presets
            ok = any(all(approx(pixel[i], exp[i]) for i in range(4)) for exp in _BORDER_EXPECT.values())
        return status, ("PASS" if ok else "FAIL"), observed
    if k == "swizzle":
        comp, code = p["component"], p["code"]
        pixel = result.get("pixel")
        if status not in ("OK", "CMDBUF_ERROR"):
            return status, "FAIL", observed
        if status == "CMDBUF_ERROR":
            return status, "PASS", observed  # a hard fault is an informative, valid H4 outcome
        table = _SWZ0_EXPECT if comp == 0 else _SWZ1_EXPECT
        chan = 0 if comp == 0 else 1
        if code in table:
            ok = pixel is not None and approx(pixel[chan], table[code])
        else:
            ok = pixel is not None  # codes 6/7 (or comp1 code6): OK-with-a-value is informative
        return status, ("PASS" if ok else "FAIL"), observed
    raise ValueError(k)


def verdict_gfxprobe(case, result):
    k, p = case["kind"], case["params"]
    if result is None:
        return "CRASH", "FAIL", {"note": "no parseable JSON on stdout"}
    status = result.get("status", "?")
    observed = _strip_nondet(result)
    if k == "restart":
        expect_restart = p["sentinel_kind"] == "allones"
        if expect_restart:
            ok = (status == "OK" and result.get("connector_band_lit") == 0
                  and result.get("left_segment_lit") == 1 and result.get("right_segment_lit") == 1)
        else:
            ok = (status == "OK" and result.get("connector_band_lit") == 1) or status == "CMDBUF_ERROR"
        return status, ("PASS" if ok else "FAIL"), observed
    if k == "norender":
        raster = p["raster_enabled"]
        ok = (status == "OK" and result.get("vertex_invocations_observed") == 3
              and result.get("any_fragment_rendered") == (1 if raster else 0))
        return status, ("PASS" if ok else "FAIL"), observed
    raise ValueError(k)


# ------------------------------------------------------------------- agxtest
def run_agxtest_case(case, gen_dir, run_id):
    p = case["params"]
    offset, value = p["offset"], p["value"]
    argv = [sys.executable, str(BIN / "agxtest" / "agxtest.py"),
            "--source", str(HERE / "kernels" / "add.metal"), "--function", "k",
            "--grid", "8", "--tg", "8",
            "--buf", "0=1,2,3,4,5,6,7,8", "--buf", "1=10,20,30,40,50,60,70,80",
            "--out", "2=8", "--expect", "2=11,22,33,44,55,66,77,88",
            "--splice", f"_agc.main@{offset}={value}",
            "--run-timeout", "15",
            "--workdir", str(gen_dir / f"agxtest_{case['id']}"),
            "--shdump", str(BIN / "agxtest" / "shdump"),
            "--agxrun", str(BIN / "agxtest" / "agxrun"),
            "--agxparse", str(BIN / "agxtest" / "agxparse.py")]
    rc, stdout, stderr, wall_ms, timed_out = run_subprocess(argv, os.environ.copy(), AGXTEST_TIMEOUT_S)
    txt = stdout.decode("utf-8", errors="replace")
    if timed_out:
        return "TIMEOUT", "TIMEOUT", {"note": "outer hard timeout"}, wall_ms, rc, stderr
    status_line = next((l for l in txt.splitlines() if l.startswith("STATUS ")), "STATUS ?")
    status = status_line.split(" ", 1)[1].strip()
    compare_line = next((l for l in txt.splitlines() if l.startswith("COMPARE ")), None)
    compare = compare_line.split()[-1] if compare_line else None
    observed = {"status": status, "compare": compare, "splice_offset": offset, "splice_value": value}
    if status == "HANG":
        return status, "TIMEOUT", observed, wall_ms, rc, stderr
    ok = (status == "OK" and compare == "MATCH")
    return status, ("PASS" if ok else "FAIL"), observed, wall_ms, rc, stderr


# ------------------------------------------------------------------- runner
def run_all(run_id, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    gen_dir = WORK / "gen" / run_id
    gen_dir.mkdir(parents=True, exist_ok=True)

    gated_f = open(out_dir / "02_gated.jsonl", "a")
    nongated_f = open(out_dir / "03_nongated.jsonl", "a")

    inputs = {"run_id": run_id, "cases_planned": CM.TOTAL,
              "git_revision": subprocess.check_output(
                  ["git", "-C", str(EXP.parent.parent), "rev-parse", "HEAD"]).decode().strip()}
    (out_dir / "00_inputs.json").write_text(json.dumps(inputs, indent=2))

    iotrace_dylib = str(BIN / "iotrace.dylib")

    for i, case in enumerate(CM.MATRIX):
        cid, mech = case["id"], case["mechanism"]
        wall_ms = 0.0
        pid_for_record = -1
        stderr_tail = b""

        if mech == "descpatch":
            case_json = build_descpatch_case(case)
            case_json["case_id"] = cid
            case_dir = gen_dir / f"d_{cid}"
            case_dir.mkdir(parents=True, exist_ok=True)
            case_path = case_dir / "case.json"
            case_path.write_text(json.dumps(case_json))
            dump_dir = case_dir / "dump"
            dump_dir.mkdir(exist_ok=True)
            env = os.environ.copy()
            env["DYLD_INSERT_LIBRARIES"] = iotrace_dylib
            env["IOTRACE_LOG"] = str(case_dir / "trace.log")
            env["IOTRACE_DUMP_DIR"] = str(dump_dir)
            rc, stdout, stderr, wall_ms, timed_out = run_subprocess(
                [str(BIN / "descpatch"), str(case_path)], env, HARD_TIMEOUT_S)
            stderr_tail = stderr
            pid_for_record = rc if rc is not None else -1
            result = None if timed_out else parse_json_line(stdout)
            if timed_out:
                status, verdict, observed = "TIMEOUT", "TIMEOUT", {"note": "hard timeout"}
            else:
                status, verdict, observed = verdict_descpatch(case, result)
            gputime = 0
            shutil.rmtree(dump_dir, ignore_errors=True)  # each dump is O(30 BOs x <=1MB); drop after use

        elif mech == "gfxprobe":
            case_json = build_gfxprobe_case(case)
            case_json["case_id"] = cid
            case_dir = gen_dir / f"g_{cid}"
            case_dir.mkdir(parents=True, exist_ok=True)
            case_path = case_dir / "case.json"
            case_path.write_text(json.dumps(case_json))
            env = os.environ.copy()
            if case["kind"] == "norender":
                dump_dir = case_dir / "dump"
                dump_dir.mkdir(exist_ok=True)
                env["DYLD_INSERT_LIBRARIES"] = iotrace_dylib
                env["IOTRACE_LOG"] = str(case_dir / "trace.log")
                env["IOTRACE_DUMP_DIR"] = str(dump_dir)
            rc, stdout, stderr, wall_ms, timed_out = run_subprocess(
                [str(BIN / "gfxprobe"), str(case_path)], env, HARD_TIMEOUT_S)
            stderr_tail = stderr
            pid_for_record = rc if rc is not None else -1
            result = None if timed_out else parse_json_line(stdout)
            if timed_out:
                status, verdict, observed = "TIMEOUT", "TIMEOUT", {"note": "hard timeout"}
            else:
                status, verdict, observed = verdict_gfxprobe(case, result)
            gputime = 0
            if case["kind"] == "norender":
                shutil.rmtree(case_dir / "dump", ignore_errors=True)

        elif mech == "agxtest":
            status, verdict, observed, wall_ms, rc, stderr = run_agxtest_case(case, gen_dir, run_id)
            stderr_tail = stderr
            pid_for_record = rc if rc is not None else -1
            gputime = 0
        else:
            raise ValueError(mech)

        gated = {"case_id": cid, "family": case["family"], "kind": case["kind"],
                 "params": case["params"], "status": status, "verdict": verdict, "observed": observed}
        nongated = {"case_id": cid, "gputime_ns": gputime, "wall_ms": round(wall_ms, 3),
                    "pid": pid_for_record, "raw_tail": stderr_tail.decode("utf-8", errors="replace")[-500:]}
        gated_f.write(json.dumps(gated, sort_keys=True) + "\n"); gated_f.flush(); os.fsync(gated_f.fileno())
        nongated_f.write(json.dumps(nongated, sort_keys=True) + "\n"); nongated_f.flush(); os.fsync(nongated_f.fileno())

        print(f"[{i+1}/{CM.TOTAL}] {cid:34s} {status:14s} {verdict}", flush=True)

    gated_f.close(); nongated_f.close()
    manifest = {"cases_planned": CM.TOTAL, "run_id": run_id,
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (out_dir / "04_manifest.json").write_text(json.dumps(manifest, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run_all(args.run, args.out)


if __name__ == "__main__":
    main()
