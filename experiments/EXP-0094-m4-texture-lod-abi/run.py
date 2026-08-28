#!/usr/bin/env python3
"""EXP-0094 capture runner. Never runs a device operation without --execute.

Six backends (casematrix.BACKENDS), one gated record shape. Every case is its
own subprocess (harness/texrender or harness/texcompute, a fresh process per
invocation); single-threaded, sequential; every raw record line is flushed to
disk before the next case starts.

Two records per case, split per the standing NO-NONDETERMINISM gate:
  04_results.jsonl      -- GATED (byte/JSON-comparable across runs): case
                            identity, params, status, pipeline_source,
                            observed, expected, VERDICT. No timing field.
  04_results_raw.jsonl  -- NOT gated: full subprocess receipt, timing included.
"""
import argparse, datetime, hashlib, json, math, platform, shutil, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0094-m4-texture-lod-abi"
sys.path.insert(0, str(HERE / "analysis"))
import casematrix as CM   # noqa: E402
import reference as REF   # noqa: E402

RUNS = ("m4-20260828c-run01", "m4-20260828c-run02")

BOUNDARY = ("public Metal API only; runtime MSL compile of our own kernels via "
           "harness/texrender + harness/texcompute (bias_sweep/grad_sweep/lodquery/"
           "cube_faceid/cube_grad); binary-archive splice of our own compiled shader "
           "bytes (harness/bin/shdump, our own build of the read-only tools/shdump/shdump.m "
           "source) via harness/texrender --archive for regsplice_bias only; owned shared "
           "buffers/textures; every case a fresh process; no Apple binary, archive, BO or "
           "command-stream inspection beyond our own compiled shader bytes")

TIMEOUTS = {"env_command": 10, "host_build": 60, "archive_build": 30,
           "case_process": 30, "smoke_process": 30}

AUTH_CODE = ("kernels/bias_probe.metal", "kernels/grad_probe.metal",
            "kernels/lodquery_probe.metal", "kernels/cube_faceid.metal",
            "kernels/cube_grad.metal", "kernels/regpair_bias_A.metal",
            "kernels/regpair_bias_B.metal",
            "harness/build.sh", "harness/texrender.m", "harness/texcompute.m",
            "analysis/reference.py", "analysis/casematrix.py",
            "run.py", "verify.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")

# authoritative record key sets (imported by verify.py; never restated there)
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit",
           "stdout", "stderr", "exception"}
CASE_KEYS = {"i", "backend", "case_name", "params", "status", "pipeline_source",
            "observed", "expected", "verdict"}
CASE_RAW_KEYS = {"i", "duration_ms", "exit", "timed_out", "exception", "stdout", "stderr"}
DISPATCH_KEYS = {"argv", "cwd", "started_utc", "finished_utc", "duration_seconds",
                 "n_cases", "status_counts", "verdict_counts", "results_sha256",
                 "results_lines"}

STATUS_ALLOWED = {"OK", "COMPILE_FAIL", "FUNCTION_MISSING", "ARCHIVE_FAIL",
                  "PIPELINE_MISS", "PIPELINE_FAIL", "CMDBUF_ERROR", "HANG", "NO_STATUS"}
VERDICT_ALLOWED = {"MATCH_EXPECTED", "MISMATCH_EXPECTED", "OBSERVED_NO_ORACLE", "FAULT"}

FLOAT_TOL = 1.0e-3


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def farg(v):
    """python float/str -> the exact CLI token the harnesses accept."""
    if isinstance(v, str):
        return v
    if v != v:
        return "nan"
    if v == float("inf"):
        return "inf"
    if v == float("-inf"):
        return "-inf"
    return repr(float(v))


def rec(argv, timeout, cwd):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p = subprocess.run([str(x) for x in argv], cwd=str(cwd), text=True,
                           capture_output=True, timeout=timeout)
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr, "exception": None}
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": True, "exit": None,
                "stdout": out, "stderr": err, "exception": "TimeoutExpired"}
    except OSError as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": None,
                "stdout": "", "stderr": "", "exception": type(e).__name__}


def provenance():
    def git(*a):
        return subprocess.run(["git", *a], cwd=REPO, text=True, capture_output=True,
                              check=True).stdout
    exp = git("status", "--porcelain", "--", EXP_REL)
    return {
        "git_revision": git("rev-parse", "HEAD").strip(),
        "git_dirty": git("status", "--porcelain").strip() != "",
        "experiment_tree_dirty_entries": len([l for l in exp.splitlines() if l.strip()]),
        "authored_code_sha256": {p: sha(HERE / p) for p in AUTH_CODE},
        "authored_doc_sha256": {p: sha(HERE / p) for p in AUTH_DOC},
    }


def parse_lines(stdout, prefixes):
    out = {k: None for k in prefixes.values()}
    for line in stdout.splitlines():
        for pfx, key in prefixes.items():
            if line.startswith(pfx):
                out[key] = line[len(pfx):].strip()
    return out


def close(a, b, tol=FLOAT_TOL):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a != a or b != b:  # nan
            return a != a and b != b
        return abs(a - b) <= tol
    return a == b


def compute_verdict(status, observed, expected, matcher):
    if status != "OK":
        return "FAULT"
    if expected is None:
        return "OBSERVED_NO_ORACLE"
    if observed is None:
        return "MISMATCH_EXPECTED"
    return "MATCH_EXPECTED" if matcher(observed, expected) else "MISMATCH_EXPECTED"


# --- backend: bias_sweep (harness/texrender, own compile, no splice) -------
def run_bias_sweep(shared, case, timeout):
    p = case
    argv = [shared / "texrender", "--source", HERE / "kernels" / "bias_probe.metal",
           "--vertex", "vmain", "--fragment", "fmain",
           "--tex-lodramp", "--tex-levels", str(CM.TEX_LEVELS),
           "--tex-size", f"{CM.TEX_W},{CM.TEX_H}", "--rt-format", "r32float",
           "--sampler-mipfilter", "linear", "--no-fast-math",
           "--params", ",".join([farg(1.0 / CM.TEX_W), farg(0.0), farg(p["bias"])])]
    if p["lod_min"] is not None:
        argv += ["--sampler-lodmin", farg(p["lod_min"])]
    if p["lod_max"] is not None:
        argv += ["--sampler-lodmax", farg(p["lod_max"])]
    if p["view"] is not None:
        argv += ["--view-levels", f"{p['view'][0]},{p['view'][1]}"]
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    parsed = parse_lines(r["stdout"], {"STATUS ": "status", "PIPELINE_SOURCE ": "pipeline_source",
                                       "PIXEL ": "pixel"})
    status = parsed["status"] or "NO_STATUS"
    observed = None
    if parsed["pixel"]:
        vals = dict(tok.split("=") for tok in parsed["pixel"].split())
        observed = {"lod": float(vals["r"])}
    if r["timed_out"] or r["exception"] is not None:
        status = "HANG" if r["timed_out"] else status
    matcher = lambda o, e: close(o.get("lod"), e.get("lod"))
    verdict = compute_verdict(status, observed, p["expected"], matcher)
    gated = {"backend": "bias_sweep", "case_name": p["case_name"], "params": p,
            "status": status, "pipeline_source": parsed["pipeline_source"],
            "observed": observed, "expected": p["expected"], "verdict": verdict}
    rawrec = {"duration_ms": dur, "exit": r["exit"], "timed_out": r["timed_out"],
             "exception": r["exception"], "stdout": r["stdout"], "stderr": r["stderr"]}
    return gated, rawrec


# --- backend: grad_sweep (harness/texcompute, own compile, no splice) ------
def run_grad_sweep(shared, case, timeout):
    p = case
    dx, dy = p["dx"], p["dy"]
    argv = [shared / "texcompute", "--source", HERE / "kernels" / "grad_probe.metal",
           "--function", "kmain", "--tex-lodramp", "--tex-levels", str(CM.TEX_LEVELS),
           "--tex-size", f"{CM.TEX_W},{CM.TEX_H}", "--sampler-mipfilter", "linear",
           "--no-fast-math", "--out-count", "1",
           "--params", ",".join(farg(v) for v in [dx[0], dx[1], dy[0], dy[1]])]
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    parsed = parse_lines(r["stdout"], {"STATUS ": "status", "PIPELINE_SOURCE ": "pipeline_source",
                                       "OUT ": "out"})
    status = parsed["status"] or "NO_STATUS"
    observed = None
    if parsed["out"]:
        toks = parsed["out"].split()
        observed = {"lod": float(toks[1])}
    if r["timed_out"] or r["exception"] is not None:
        status = "HANG" if r["timed_out"] else status
    matcher = lambda o, e: close(o.get("lod"), e.get("lod"))
    verdict = compute_verdict(status, observed, p["expected"], matcher)
    gated = {"backend": "grad_sweep", "case_name": p["case_name"], "params": p,
            "status": status, "pipeline_source": parsed["pipeline_source"],
            "observed": observed, "expected": p["expected"], "verdict": verdict}
    rawrec = {"duration_ms": dur, "exit": r["exit"], "timed_out": r["timed_out"],
             "exception": r["exception"], "stdout": r["stdout"], "stderr": r["stderr"]}
    return gated, rawrec


# --- backend: lodquery (harness/texrender, own compile, no splice) ---------
def run_lodquery(shared, case, timeout):
    p = case
    argv = [shared / "texrender", "--source", HERE / "kernels" / "lodquery_probe.metal",
           "--vertex", "vmain", "--fragment", "fmain",
           "--tex-lodramp", "--tex-levels", str(CM.TEX_LEVELS),
           "--tex-size", f"{CM.TEX_W},{CM.TEX_H}", "--rt-format", "rgba32float",
           "--sampler-mipfilter", "linear", "--no-fast-math",
           "--params", ",".join([farg(p["uvsx"]), farg(p["uvsy"])])]
    if p["lod_min"] is not None:
        argv += ["--sampler-lodmin", farg(p["lod_min"])]
    if p["lod_max"] is not None:
        argv += ["--sampler-lodmax", farg(p["lod_max"])]
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    parsed = parse_lines(r["stdout"], {"STATUS ": "status", "PIPELINE_SOURCE ": "pipeline_source",
                                       "PIXEL ": "pixel"})
    status = parsed["status"] or "NO_STATUS"
    observed = None
    if parsed["pixel"]:
        vals = dict(tok.split("=") for tok in parsed["pixel"].split())
        observed = {"sampled_lod": float(vals["r"]), "clamped_lod": float(vals["g"]),
                    "unclamped_lod": float(vals["b"])}
    if r["timed_out"] or r["exception"] is not None:
        status = "HANG" if r["timed_out"] else status
    matcher = lambda o, e: all(close(o.get(k), e.get(k)) for k in ("sampled_lod", "clamped_lod", "unclamped_lod"))
    verdict = compute_verdict(status, observed, p["expected"], matcher)
    gated = {"backend": "lodquery", "case_name": p["case_name"], "params": p,
            "status": status, "pipeline_source": parsed["pipeline_source"],
            "observed": observed, "expected": p["expected"], "verdict": verdict}
    rawrec = {"duration_ms": dur, "exit": r["exit"], "timed_out": r["timed_out"],
             "exception": r["exception"], "stdout": r["stdout"], "stderr": r["stderr"]}
    return gated, rawrec


# --- backend: cube_faceid (harness/texcompute, own compile, no splice) -----
def run_cube_faceid(shared, case, timeout):
    p = case
    argv = [shared / "texcompute", "--source", HERE / "kernels" / "cube_faceid.metal",
           "--function", "kmain", "--tex-cube", "--tex-format", "rgba8unorm",
           "--no-fast-math", "--out-count", "4"]
    for i, col in enumerate(CM.CUBE_FACE_COLORS):
        argv += ["--tex-face", f"{i}=" + ",".join(str(c) for c in col)]
    argv += ["--params", ",".join(farg(v) for v in p["dir"])]
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    parsed = parse_lines(r["stdout"], {"STATUS ": "status", "PIPELINE_SOURCE ": "pipeline_source",
                                       "OUT ": "out"})
    status = parsed["status"] or "NO_STATUS"
    observed = None
    if parsed["out"]:
        toks = parsed["out"].split()
        rgba01 = [float(x) for x in toks[1:5]]
        col255 = [round(x * 255) for x in rgba01]
        best = min(range(6), key=lambda i: sum(abs(col255[k] - CM.CUBE_FACE_COLORS[i][k]) for k in range(4)))
        observed = {"face": best, "face_name": REF.FACE_NAMES[best], "color": col255,
                    "raw_rgba01": rgba01}
    if r["timed_out"] or r["exception"] is not None:
        status = "HANG" if r["timed_out"] else status
    matcher = lambda o, e: o.get("face") == e.get("face")
    verdict = compute_verdict(status, observed, p["expected"], matcher)
    gated = {"backend": "cube_faceid", "case_name": p["case_name"], "params": p,
            "status": status, "pipeline_source": parsed["pipeline_source"],
            "observed": observed, "expected": p["expected"], "verdict": verdict}
    rawrec = {"duration_ms": dur, "exit": r["exit"], "timed_out": r["timed_out"],
             "exception": r["exception"], "stdout": r["stdout"], "stderr": r["stderr"]}
    return gated, rawrec


# --- backend: cube_grad (harness/texcompute, own compile, no splice) -------
def run_cube_grad(shared, case, timeout):
    p = case
    params = list(p["dir"]) + list(p["dPdx"]) + list(p["dPdy"])
    argv = [shared / "texcompute", "--source", HERE / "kernels" / "cube_grad.metal",
           "--function", "kmain", "--tex-cube", "--tex-lodramp",
           "--tex-levels", str(CM.CUBE_LEVELS), "--tex-size", f"{CM.FACE_SIZE},{CM.FACE_SIZE}",
           "--sampler-mipfilter", "linear", "--no-fast-math", "--out-count", "1",
           "--params", ",".join(farg(v) for v in params)]
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    parsed = parse_lines(r["stdout"], {"STATUS ": "status", "PIPELINE_SOURCE ": "pipeline_source",
                                       "OUT ": "out"})
    status = parsed["status"] or "NO_STATUS"
    observed = None
    if parsed["out"]:
        toks = parsed["out"].split()
        observed = {"lod": float(toks[1])}
    if r["timed_out"] or r["exception"] is not None:
        status = "HANG" if r["timed_out"] else status
    matcher = lambda o, e: close(o.get("lod"), e.get("lod"), tol=0.15)
    verdict = compute_verdict(status, observed, p["expected"], matcher)
    gated = {"backend": "cube_grad", "case_name": p["case_name"], "params": p,
            "status": status, "pipeline_source": parsed["pipeline_source"],
            "observed": observed, "expected": p["expected"], "verdict": verdict}
    rawrec = {"duration_ms": dur, "exit": r["exit"], "timed_out": r["timed_out"],
             "exception": r["exception"], "stdout": r["stdout"], "stderr": r["stderr"]}
    return gated, rawrec


# --- backend: regsplice_bias (harness/texrender --archive, HW-VALIDATED) ---
def build_regsplice_archives(shared):
    out_dir = shared / "regsplice"
    out_dir.mkdir(parents=True, exist_ok=True)
    a_bin = out_dir / "A.bin"
    b_bin = out_dir / "B.bin"
    for src, out in ((HERE / "kernels" / "regpair_bias_A.metal", a_bin),
                     (HERE / "kernels" / "regpair_bias_B.metal", b_bin)):
        # NOTE: fast-math is left at its DEFAULT (ON) here, deliberately matching the
        # pilot compile that produced the FROZEN regsplice offset/native-byte values
        # (PROGRESS.md T2 / PRE_REGISTRATION.md hypothesis 3) -- changing this would
        # shift the AIR hash and the compiled byte layout, invalidating the frozen
        # splice offset. The texrender invocation below matches (no --no-fast-math)
        # for this backend only, so the archive's function hash matches what
        # texrender recompiles for identity.
        subprocess.run([shared / "bin" / "shdump", "-o", out, "--render", "--color-format", "55",
                        "--vertex", "vmain", "--fragment", "fmain", src],
                       check=True, capture_output=True, timeout=TIMEOUTS["archive_build"])
    archives = {"A": a_bin, "B": b_bin}
    spliced_paths = {}
    for case in CM.REGSPLICE_CASES:
        name, base, splice_byte, _ = case
        if splice_byte is None:
            spliced_paths[name] = archives[base]
            continue
        dst = out_dir / f"{name}.bin"
        data = bytearray(archives[base].read_bytes())
        data[CM.REGSPLICE_ABS_OFFSET] = splice_byte
        dst.write_bytes(bytes(data))
        spliced_paths[name] = dst
    return archives, spliced_paths


def run_regsplice_bias(shared, case, timeout, archive_map):
    p = case
    archive_path = archive_map[p["case_name"]]
    src = HERE / "kernels" / f"regpair_bias_{p['base_archive']}.metal"
    # NO --no-fast-math here: must match build_regsplice_archives()'s shdump
    # compile (default fast-math ON) so the AIR/function hash texrender
    # recomputes for pipeline identity matches the archive's.
    argv = [shared / "texrender", "--archive", archive_path, "--source", src,
           "--vertex", "vmain", "--fragment", "fmain",
           "--tex-lodramp", "--tex-levels", str(CM.TEX_LEVELS),
           "--tex-size", f"{CM.TEX_W},{CM.TEX_H}", "--rt-format", "r32float",
           "--sampler-mipfilter", "linear",
           "--params", ",".join(farg(v) for v in [1.0 / CM.TEX_W, 0.0, CM.BIAS_A_VALUE, CM.BIAS_B_VALUE])]
    t0 = time.monotonic()
    r = rec(argv, timeout, HERE)
    dur = int((time.monotonic() - t0) * 1000)
    parsed = parse_lines(r["stdout"], {"STATUS ": "status", "PIPELINE_SOURCE ": "pipeline_source",
                                       "PIXEL ": "pixel"})
    status = parsed["status"] or "NO_STATUS"
    observed = None
    if parsed["pixel"]:
        vals = dict(tok.split("=") for tok in parsed["pixel"].split())
        observed = {"lod": float(vals["r"])}
    if r["timed_out"] or r["exception"] is not None:
        status = "HANG" if r["timed_out"] else status
    matcher = lambda o, e: close(o.get("lod"), e.get("lod"))
    verdict = compute_verdict(status, observed, p["expected"], matcher)
    gated = {"backend": "regsplice_bias", "case_name": p["case_name"], "params": p,
            "status": status, "pipeline_source": parsed["pipeline_source"],
            "observed": observed, "expected": p["expected"], "verdict": verdict}
    rawrec = {"duration_ms": dur, "exit": r["exit"], "timed_out": r["timed_out"],
             "exception": r["exception"], "stdout": r["stdout"], "stderr": r["stderr"]}
    return gated, rawrec


def run_one_case(shared, case, timeout, archive_map=None):
    backend = case["backend"]
    if backend == "bias_sweep":
        return run_bias_sweep(shared, case, timeout)
    if backend == "grad_sweep":
        return run_grad_sweep(shared, case, timeout)
    if backend == "lodquery":
        return run_lodquery(shared, case, timeout)
    if backend == "cube_faceid":
        return run_cube_faceid(shared, case, timeout)
    if backend == "cube_grad":
        return run_cube_grad(shared, case, timeout)
    if backend == "regsplice_bias":
        return run_regsplice_bias(shared, case, timeout, archive_map)
    raise ValueError(backend)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved "
                         "pre-GPU review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ", ".join(RUNS))
    for gate in ("--selftest", "--seqtest"):
        if subprocess.run([sys.executable, "-B", "verify.py", gate], cwd=HERE).returncode:
            raise SystemExit("verify.py %s failed: no capture is authorized" % gate)
    gate = "--preflight" if a.run_id == RUNS[0] else "--between-runs"
    if subprocess.run([sys.executable, "-B", "verify.py", gate], cwd=HERE).returncode:
        raise SystemExit("run gate failed")
    current = provenance()
    if a.run_id == RUNS[1]:
        first = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        for k in ("authored_code_sha256", "authored_doc_sha256"):
            if first.get(k) != current[k]:
                raise SystemExit("run02 provenance differs from closed run01: " + k)

    raw = HERE / "raw" / a.run_id
    work = HERE / "work" / a.run_id
    if raw.exists() or work.exists():
        raise SystemExit("append-only path already exists")
    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.monotonic()
    try:
        # --- PHASE 1 (pre-raw): build, archives, NON-RECORDED smoke gate. ---
        shared = work / "shared"
        shared.mkdir(parents=True)
        build = rec([HERE / "harness" / "build.sh"], TIMEOUTS["host_build"], HERE)
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None:
            print(json.dumps({"pre_capture_stop": "host_build", "harness_build": build}, indent=2))
            raise SystemExit(3)
        for f in ("texrender", "texcompute"):
            shutil.copy(HERE / "harness" / f, shared / f)
        (shared / "bin").mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE / "harness" / "bin" / "shdump", shared / "bin" / "shdump")

        archives, archive_map = build_regsplice_archives(shared)
        # frozen-byte check: the base archives must carry A's/B's NATIVE byte
        # at the frozen offset before any splice is applied (stop on drift).
        a_native = archives["A"].read_bytes()[CM.REGSPLICE_ABS_OFFSET]
        b_native = archives["B"].read_bytes()[CM.REGSPLICE_ABS_OFFSET]
        if a_native != CM.REGSPLICE_A_NATIVE or b_native != CM.REGSPLICE_B_NATIVE:
            print(json.dumps({"pre_capture_stop": "regsplice_anchor_mismatch",
                              "a_native": a_native, "b_native": b_native,
                              "expected_a": CM.REGSPLICE_A_NATIVE,
                              "expected_b": CM.REGSPLICE_B_NATIVE}, indent=2))
            raise SystemExit(3)

        # --- NON-RECORDED smoke gate: one scratch bias_sweep case ----------
        smoke_case = dict(CM.full_case_list()[0])
        assert smoke_case["backend"] == "bias_sweep"
        smoke_case["i"] = -1
        smoke_gated, smoke_raw = run_one_case(shared, smoke_case, TIMEOUTS["smoke_process"])
        smoke_ok = (smoke_gated["status"] == "OK" and smoke_gated["verdict"] == "MATCH_EXPECTED"
                   and not smoke_raw["timed_out"])
        if not smoke_ok:
            print(json.dumps({"pre_capture_stop": "smoke_gate",
                              "smoke_gated": smoke_gated, "smoke_raw": smoke_raw}, indent=2))
            raise SystemExit(3)

        # --- PHASE 2: the append-only capture -------------------------------
        raw.mkdir(parents=True)
        results_path = raw / "04_results.jsonl"
        results_raw_path = raw / "04_results_raw.jsonl"
        env = {"schema": 1, **current,
              "sw_vers": rec(["sw_vers"], TIMEOUTS["env_command"], HERE),
              "xcrun_version": rec(["xcrun", "--version"], TIMEOUTS["env_command"], HERE),
              "python": sys.version.split()[0], "machine": platform.machine(),
              "boundary": BOUNDARY, "timeouts_seconds": TIMEOUTS}
        put(raw / "00_inputs.json", env)
        if any(env[z]["timed_out"] or env[z]["exit"] != 0 or env[z]["exception"] is not None
              for z in ("sw_vers", "xcrun_version")):
            put(raw / "STOP.json", {"schema": 1, "phase": "environment", "automatic_retry": False})
            return

        cases = CM.full_case_list()
        put(raw / "01_cases.json", {
            "schema": 1, "run_id": a.run_id, "total": len(cases),
            "cases": [{"i": c["i"], "backend": c["backend"], "case_name": c["case_name"]}
                     for c in cases]})
        put(raw / "02_build.json", {"schema": 1, "harness_build": build})

        status_counts = {}
        verdict_counts = {}
        try:
            with results_path.open("a") as rf, results_raw_path.open("a") as rrf:
                for c in cases:
                    gated, rawrec = run_one_case(shared, c, TIMEOUTS["case_process"], archive_map)
                    gated_full = {"i": c["i"], **gated}
                    raw_full = {"i": c["i"], **rawrec}
                    assert set(gated_full) == CASE_KEYS, sorted(set(gated_full) ^ CASE_KEYS)
                    assert set(raw_full) == CASE_RAW_KEYS, sorted(set(raw_full) ^ CASE_RAW_KEYS)
                    rf.write(json.dumps(gated_full, sort_keys=True, default=str) + "\n")
                    rf.flush()
                    rrf.write(json.dumps(raw_full, sort_keys=True, default=str) + "\n")
                    rrf.flush()
                    status_counts[gated["status"]] = status_counts.get(gated["status"], 0) + 1
                    verdict_counts[gated["verdict"]] = verdict_counts.get(gated["verdict"], 0) + 1
        except Exception as e:
            put(raw / "STOP.json", {"schema": 1, "phase": "dispatch_loop",
                                    "automatic_retry": False,
                                    "error": "%s: %s" % (type(e).__name__, e),
                                    "cases_completed": sum(status_counts.values())})
            return

        results_lines = sum(1 for _ in results_path.open("rb"))
        dispatch = {"argv": [sys.executable] + sys.argv, "cwd": str(HERE),
                   "started_utc": started_utc,
                   "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "duration_seconds": round(time.monotonic() - t0, 3),
                   "n_cases": len(cases), "status_counts": status_counts,
                   "verdict_counts": verdict_counts, "results_sha256": sha(results_path),
                   "results_lines": results_lines}
        assert set(dispatch) == DISPATCH_KEYS
        put(raw / "03_dispatch.json", dispatch)
        if results_lines != len(cases):
            put(raw / "STOP.json", {"schema": 1, "phase": "dispatch_loop", "automatic_retry": False})
            return
        put(raw / "05_run_manifest.json", {
            "schema": 1, "run_id": a.run_id, "total_cases": len(cases),
            "runner_sha256": sha(HERE / "run.py"), "casematrix_sha256": sha(HERE / "analysis" / "casematrix.py"),
            "harness_sha256": sha(HERE / "harness" / "build.sh"),
            "cases_sha256": sha(raw / "01_cases.json"),
            "results_sha256": dispatch["results_sha256"]})
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
