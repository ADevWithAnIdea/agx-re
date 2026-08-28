#!/usr/bin/env python3
"""EXP-0117 capture driver. One process per invocation; appends one JSON line
per case to raw/<run_id>/04_results.jsonl immediately after the case
completes (flushed + fsynced), so a kill costs at most the current case.
Every external tool invocation is our own binary (built fresh from committed
source, never a prebuilt artifact) or the unmodified tools/shdump/shdump.m
and tools/shdump/agxparse.py.

Usage:
  python3 run.py --run <run_id> --out raw/<run_id> [--smoke-only]
"""
import argparse, hashlib, json, os, re, subprocess, sys, time, datetime, platform
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import casematrix as CM

SHDUMP_SRC = REPO / "tools" / "shdump" / "shdump.m"
AGXPARSE = REPO / "tools" / "shdump" / "agxparse.py"

AUTHORED_FILES = [
    "PRE_REGISTRATION.md", "README.md", "casematrix.py", "run.py", "verify.py",
    "kernels/blend.metal", "kernels/fsorder.metal", "kernels/barycentric.metal",
    "kernels/msaa_diff.metal", "kernels/samplemask.metal", "kernels/stencil.metal",
    "kernels/stencil_i32_negative.metal", "kernels/callabi.metal", "kernels/callchain.metal",
    "harness/struct_extract.m", "harness/render.m", "harness/compute_run.m",
    "harness/gen_callchain.py",
]

TIMEOUT_CASE = 30
TIMEOUT_BUILD = 60

NONDET_FORBIDDEN = {"duration_ms", "pid", "timestamp", "started_utc", "address", "elapsed"}

CALL_RE = re.compile("0f0554")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def authored_hashes():
    return {f: sha256_file(HERE / f) for f in AUTHORED_FILES}


def git_rev():
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                            text=True, timeout=10)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                                capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), bool(dirty.stdout.strip())
    except Exception as e:
        return f"ERROR:{e}", None


def env_info():
    sw = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True, timeout=10).stdout.strip()
    xc = subprocess.run(["xcrun", "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
    return {"sw_vers": sw, "xcrun_version": xc, "python": platform.python_version(),
            "machine": platform.machine()}


def build_binaries(bindir: Path):
    bindir.mkdir(parents=True, exist_ok=True)
    targets = {
        "struct_extract": HERE / "harness" / "struct_extract.m",
        "render": HERE / "harness" / "render.m",
        "compute_run": HERE / "harness" / "compute_run.m",
        "shdump": SHDUMP_SRC,
    }
    built = {}
    for name, src in targets.items():
        out = bindir / name
        cmd = ["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
               "-o", str(out), str(src)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_BUILD)
        built[name] = {"ok": r.returncode == 0 and out.exists(), "stderr_tail": r.stderr[-2000:]}
        if not built[name]["ok"]:
            raise SystemExit(f"build failed for {name}: {r.stderr}")
    return bindir, built


def run_cmd(argv, timeout=TIMEOUT_CASE):
    t0 = time.time()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
                "timed_out": False, "duration_ms": int((time.time() - t0) * 1000)}
    except subprocess.TimeoutExpired as e:
        return {"returncode": None, "stdout": e.stdout or "", "stderr": e.stderr or "",
                "timed_out": True, "duration_ms": int((time.time() - t0) * 1000)}


def _abort_or_parse_json(res, backend, extra_gated=None):
    """Shared post-processing for our render/compute_run/struct_extract JSON-emitting
    binaries: distinguishes a clean JSON result from a FATAL PROCESS ABORT (a
    Metal API validation assertion that SIGABRTs the process rather than
    returning a catchable NSError -- discovered during harness development,
    see PROGRESS.md) from an ordinary nonzero-exit failure."""
    gated = {"backend": backend}
    if extra_gated:
        gated.update(extra_gated)
    if res["timed_out"]:
        gated["status"] = "TIMEOUT"
        return gated
    rc = res["returncode"]
    if rc is not None and rc < 0:
        # Killed by signal (e.g. -6 == SIGABRT from a fatal Metal validation assertion).
        gated["status"] = "PROCESS_ABORT"
        gated["signal"] = -rc
        gated["stderr_tail"] = res["stderr"][-1500:].strip()
        return gated
    try:
        j = json.loads(res["stdout"].strip())
        gated["status"] = j.get("status", "UNKNOWN")
        gated["result"] = j
    except Exception:
        gated["status"] = "PARSE_FAIL"
        gated["stdout_tail"] = res["stdout"][-800:]
        gated["stderr_tail"] = res["stderr"][-800:]
        gated["returncode"] = rc
    return gated


def do_render(bindir, workdir, case):
    p = dict(case["params"])
    mode = p.pop("mode")
    src = REPO_or_here(case["source"])
    argv = [str(bindir / "render"), "--source", str(src), "--mode", mode]
    for k, v in p.items():
        argv += [f"--{k}", str(v)]
    res = run_cmd(argv)
    gated = _abort_or_parse_json(res, "render", {"mode": mode, "params": p})
    return gated, res


def do_struct_extract(bindir, workdir, case):
    p = case["params"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "struct_extract"), "-o", str(out), "--source", str(HERE / case["source"])]
    for k, v in p.items():
        argv += [f"--{k}", str(v)]
    res = run_cmd(argv)
    gated = {"backend": "struct_extract", "params": p}
    if res["timed_out"]:
        gated["status"] = "TIMEOUT"
        return gated, res
    rc = res["returncode"]
    if rc is not None and rc < 0:
        gated["status"] = "PROCESS_ABORT"
        gated["signal"] = -rc
        gated["stderr_tail"] = res["stderr"][-1500:].strip()
        return gated, res
    stdout = res["stdout"].strip()
    if stdout == "OK":
        gated["status"] = "OK"
        hexstr, err = extract_hex(out, "fragment")
        gated["fragment_hex"] = hexstr
        gated["fragment_hex_len"] = len(hexstr) // 2 if hexstr else None
        gated["structure"] = struct_report(out)
        gated["has_tile_read"] = bool(hexstr and "670e" in hexstr)
    elif stdout.startswith("FAIL:"):
        gated["status"] = "FAIL"
        gated["error"] = stdout[len("FAIL:"):].strip()
    else:
        gated["status"] = "UNKNOWN"
        gated["stdout_tail"] = stdout[-800:]
        gated["stderr_tail"] = res["stderr"][-800:]
    return gated, res


def do_compute_run(bindir, workdir, case):
    p = case["params"]
    argv = [str(bindir / "compute_run"), "--source", str(HERE / case["source"]),
            "--function", p["function"], "--n", str(p["n"])]
    res = run_cmd(argv)
    gated = _abort_or_parse_json(res, "compute_run", {"function": p["function"], "n": p["n"]})
    return gated, res


def scan_calls(hexstr):
    """Locate every 14-byte direct-CALL instance (`0f 05 54 1a 8f 00 xx <off40> 00`)
    in an extracted hex string and report byte+5, byte+6, and the signed 40-bit
    PC-relative offset -- our own deterministic byte-level parser, not a
    disassembler of any Apple binary (it parses hex WE extracted from OUR OWN
    compiled shader bytes via the public archive/parse pipeline)."""
    calls = []
    if not hexstr:
        return calls
    b = bytes.fromhex(hexstr)
    idx = 0
    while True:
        i = hexstr.find("0f0554", idx * 2)
        if i == -1:
            break
        pos = i // 2
        chunk = b[pos:pos + 14]
        if len(chunk) == 14:
            off_bytes = chunk[7:12]
            off_val = int.from_bytes(off_bytes, "little", signed=False)
            if off_val & (1 << 39):
                off_val -= (1 << 40)
            calls.append({"byte_offset": pos, "byte5": chunk[5], "byte6": chunk[6],
                           "off40": off_val, "raw14": chunk.hex()})
        idx = pos + 1
    return calls


def do_shdump_call(bindir, workdir, case):
    p = case["params"]
    fn = p["function"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "shdump"), "-o", str(out), "-f", fn, str(HERE / case["source"])]
    res = run_cmd(argv)
    gated = {"backend": "shdump_call", "function": fn}
    if p.get("symbol"):
        gated["symbol"] = p["symbol"]
    if res["timed_out"]:
        gated["status"] = "TIMEOUT"
        return gated, res
    if res["returncode"] != 0 or not out.exists():
        gated["status"] = "FAIL"
        gated["error"] = res["stderr"][-1000:]
        return gated, res
    symbol = p.get("symbol")
    hexstr, err = extract_hex(out, "compute", symbol=symbol)
    gated["status"] = "OK" if hexstr else "EXTRACT_FAIL"
    gated["hex"] = hexstr
    gated["hex_len"] = len(hexstr) // 2 if hexstr else None
    gated["calls"] = scan_calls(hexstr or "")
    if not symbol:
        gated["structure"] = struct_report(out)
    return gated, res


def REPO_or_here(rel):
    return HERE / rel


def extract_hex(archive: Path, stage: str, symbol=None):
    argv = ["python3", str(AGXPARSE), str(archive), "--stage", stage, "--extract-hex"]
    if symbol:
        argv += ["--symbol", symbol]
    r = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        return None, r.stdout + r.stderr
    return r.stdout.strip(), None


def struct_report(archive: Path):
    r = subprocess.run(["python3", str(AGXPARSE), str(archive), "--json"],
                        capture_output=True, text=True, timeout=20)
    try:
        j = json.loads(r.stdout)
    except Exception:
        return {"parse_error": True, "raw": r.stdout[-2000:]}
    sections = []
    for im in j.get("images", []):
        sections.extend(im.get("sections", []))
    regions = j.get("agx", {}).get("regions", [])
    region_names = [reg[0] if isinstance(reg, list) else reg for reg in regions]
    return {"sections": sections, "region_names": region_names}


BACKEND_FN = {
    "render": do_render,
    "struct_extract": do_struct_extract,
    "compute_run": do_compute_run,
    "shdump_call": do_shdump_call,
}


def check_no_nondet(gated: dict, path=""):
    for k, v in (gated.items() if isinstance(gated, dict) else []):
        if k in NONDET_FORBIDDEN:
            raise SystemExit(f"NONDET_FORBIDDEN key '{k}' found in gated record at {path}.{k}")
        if isinstance(v, dict):
            check_no_nondet(v, f"{path}.{k}")
        if isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    check_no_nondet(item, f"{path}.{k}[{i}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--smoke-only", action="store_true")
    args = ap.parse_args()

    outdir = Path(args.out)
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"refusing to reuse non-empty run dir {outdir} (run-id reuse forbidden)")
    outdir.mkdir(parents=True, exist_ok=True)
    workdir = HERE / "work" / "gen" / args.run
    workdir.mkdir(parents=True, exist_ok=True)
    bindir = HERE / "work" / "bin" / args.run
    _, built = build_binaries(bindir)

    rev, dirty = git_rev()
    inputs = {
        "schema": 1, "run_id": args.run, "git_revision_at_run_time": rev,
        "git_dirty_at_run_time": dirty, "authored_sha256": authored_hashes(),
        "env": env_info(), "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "harness_build": built,
    }
    (outdir / "00_inputs.json").write_text(json.dumps(inputs, indent=2))

    cases = CM.full_case_list()
    (outdir / "01_cases.json").write_text(json.dumps(cases, indent=2))

    if args.smoke_only:
        smoke_cases = [c for c in cases if c["id"] == "blendfac_src_One"][:1] + \
                      [c for c in cases if c["id"] == "calldepth_1"][:1]
        results = []
        for c in smoke_cases:
            gated, res = BACKEND_FN[c["backend"]](bindir, workdir, c)
            results.append({"id": c["id"], "status": gated["status"], "ok": gated["status"] == "OK"})
        print(json.dumps({"smoke_results": results, "all_ok": all(r["ok"] for r in results)}))
        return

    fout = open(outdir / "04_results.jsonl", "a")
    n_ok = n_other = 0
    for i, c in enumerate(cases):
        t0 = time.time()
        started = datetime.datetime.now(datetime.UTC).isoformat()
        gated, res = BACKEND_FN[c["backend"]](bindir, workdir, c)
        check_no_nondet(gated)
        record = {
            "i": i, "id": c["id"], "family": c["family"], "gated": gated,
            "meta": {"duration_ms": int((time.time() - t0) * 1000), "started_utc": started,
                     "returncode": res["returncode"], "stderr_tail": res["stderr"][-500:],
                     "timed_out": res["timed_out"]},
        }
        fout.write(json.dumps(record) + "\n")
        fout.flush()
        os.fsync(fout.fileno())
        if gated["status"] == "OK":
            n_ok += 1
        else:
            n_other += 1
        print(f"[{i+1}/{len(cases)}] {c['id']}: {gated['status']}", file=sys.stderr)
    fout.close()

    summary = {"schema": 1, "run_id": args.run, "total": len(cases), "n_status_ok": n_ok,
               "n_status_other": n_other, "finished_utc": datetime.datetime.now(datetime.UTC).isoformat()}
    (outdir / "05_run_manifest.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
