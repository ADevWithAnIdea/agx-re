#!/usr/bin/env python3
"""EXP-0109 capture driver. One process per invocation; appends one JSON line
per case to raw/<run_id>/04_results.jsonl immediately after the case
completes (fflush'd), so a kill costs at most the current case. Every
external tool invocation is our own binary (built fresh from committed
source, never a prebuilt artifact) or the unmodified tools/shdump/shdump.m.

Usage:
  python3 run.py --run <run_id> --out raw/<run_id> [--smoke-only]
"""
import argparse, hashlib, json, os, subprocess, sys, time, datetime, platform
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
    "kernels/vfetch.metal", "kernels/mrt_interp.metal", "kernels/cs_probe.metal",
    "harness/vfetch_extract.m", "harness/mrt_extract.m", "harness/render_probe.m",
    "harness/compute_probe.m",
]

TIMEOUT_CASE = 30
TIMEOUT_BUILD = 60

# Fields that must NEVER appear inside a case's "gated" dict (cross-run
# byte-compared record) -- the no-nondeterminism gate.
NONDET_FORBIDDEN = {"duration_ms", "pid", "timestamp", "started_utc", "address", "elapsed"}


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
        "vfetch_extract": HERE / "harness" / "vfetch_extract.m",
        "mrt_extract": HERE / "harness" / "mrt_extract.m",
        "render_probe": HERE / "harness" / "render_probe.m",
        "compute_probe": HERE / "harness" / "compute_probe.m",
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


def extract_hex(archive: Path, stage: str):
    r = subprocess.run(["python3", str(AGXPARSE), str(archive), "--stage", stage, "--extract-hex"],
                        capture_output=True, text=True, timeout=20)
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


def do_vfetch_extract(bindir, workdir, case):
    p = case["params"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "vfetch_extract"), "-o", str(out), "--source", str(HERE / "kernels" / "vfetch.metal"),
            "--vertex", p["vertex"], "--fragment", p["fragment"], "--format", str(p["format"]),
            "--offset", str(p["offset"]), "--stride", str(p["stride"]), "--step", p["step"],
            "--rate", str(p["rate"])]
    res = run_cmd(argv)
    gated = {"backend": "vfetch_extract", "case": case["id"], "params": p}
    if res["timed_out"]:
        gated["status"] = "TIMEOUT"
    elif res["returncode"] != 0 or not out.exists():
        gated["status"] = "FAIL"
        gated["error"] = res["stderr"][-1000:]
    else:
        gated["status"] = "OK"
        hexstr, err = extract_hex(out, "vertex")
        gated["vertex_hex"] = hexstr
        gated["vertex_hex_len"] = len(hexstr) // 2 if hexstr else None
        gated["structure"] = struct_report(out)
    return gated, res


def do_mrt_extract(bindir, workdir, case):
    p = case["params"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "mrt_extract"), "-o", str(out), "--source", str(HERE / "kernels" / "mrt_interp.metal"),
            "--vertex", p["vertex"], "--fragment", p["fragment"], "--natt", str(p["natt"])]
    if "depthfmt" in p:
        argv += ["--depthfmt", str(p["depthfmt"])]
    if p.get("dualsource"):
        argv += ["--dualsource"]
    for d in p.get("defines", []):
        argv += ["--define", d]
    res = run_cmd(argv)
    gated = {"backend": "mrt_extract", "case": case["id"], "params": {k: v for k, v in p.items()}}
    if res["timed_out"]:
        gated["status"] = "TIMEOUT"
    else:
        stdout = res["stdout"].strip()
        if stdout.startswith("OK"):
            gated["status"] = "OK"
            hexstr, err = extract_hex(out, "fragment")
            gated["fragment_hex"] = hexstr
            gated["fragment_hex_len"] = len(hexstr) // 2 if hexstr else None
            gated["structure"] = struct_report(out)
        elif stdout.startswith("FAIL:"):
            gated["status"] = "FAIL"
            gated["error"] = stdout[len("FAIL:"):].strip()
        else:
            gated["status"] = "UNKNOWN"
            gated["stdout"] = stdout[-1000:]
            gated["stderr"] = res["stderr"][-1000:]
    return gated, res


def do_shdump_struct(bindir, workdir, case):
    p = case["params"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "shdump"), "-o", str(out), "-f", p["function"], str(HERE / "kernels" / "cs_probe.metal")]
    res = run_cmd(argv)
    gated = {"backend": "shdump_struct", "case": case["id"], "params": p}
    if res["timed_out"]:
        gated["status"] = "TIMEOUT"
    elif res["returncode"] != 0 or not out.exists():
        gated["status"] = "FAIL"
        gated["error"] = res["stderr"][-1000:]
    else:
        gated["status"] = "OK"
        hexstr, err = extract_hex(out, "compute")
        gated["compute_hex"] = hexstr
        gated["compute_hex_len"] = len(hexstr) // 2 if hexstr else None
        gated["structure"] = struct_report(out)
    return gated, res


def do_render_probe(bindir, workdir, case):
    p = dict(case["params"])
    mode = p.pop("mode")
    argv = [str(bindir / "render_probe"), "--source", str(HERE / "kernels" / "mrt_interp.metal"),
            "--mode", mode, "--case", case["id"]]
    for k, v in p.items():
        argv += [f"--{k}", str(v)]
    res = run_cmd(argv)
    gated = {"backend": "render_probe", "case": case["id"], "mode": mode, "params": p}
    if res["timed_out"]:
        gated["status"] = "TIMEOUT"
    else:
        try:
            j = json.loads(res["stdout"].strip())
            gated["status"] = j.get("status", "UNKNOWN")
            gated["result"] = j
        except Exception:
            gated["status"] = "PARSE_FAIL"
            gated["stdout"] = res["stdout"][-1000:]
            gated["stderr"] = res["stderr"][-1000:]
    return gated, res


def do_compute_probe(bindir, workdir, case):
    p = case["params"]
    sizes = ",".join(str(x) for x in p["sizes"])
    argv = [str(bindir / "compute_probe"), "--source", str(HERE / "kernels" / "cs_probe.metal"),
            "--sizes", sizes]
    res = run_cmd(argv)
    gated = {"backend": "compute_probe", "case": case["id"], "sizes": p["sizes"]}
    if res["timed_out"]:
        gated["status"] = "TIMEOUT"
    else:
        try:
            j = json.loads(res["stdout"].strip())
            gated["status"] = "OK" if all(x.get("status") == "OK" for x in j) else "PARTIAL_FAIL"
            gated["result"] = j
        except Exception:
            gated["status"] = "PARSE_FAIL"
            gated["stdout"] = res["stdout"][-1000:]
    return gated, res


BACKEND_FN = {
    "vfetch_extract": do_vfetch_extract,
    "mrt_extract": do_mrt_extract,
    "shdump_struct": do_shdump_struct,
    "render_probe": do_render_probe,
    "compute_probe": do_compute_probe,
}


def check_no_nondet(gated: dict, path=""):
    for k, v in (gated.items() if isinstance(gated, dict) else []):
        if k in NONDET_FORBIDDEN:
            raise SystemExit(f"NONDET_FORBIDDEN key '{k}' found in gated record at {path}.{k}")
        if isinstance(v, dict):
            check_no_nondet(v, f"{path}.{k}")


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
        # ONE structural + ONE HW-PROBE case, non-recorded (caller writes to work/, not raw/).
        smoke_cases = [c for c in cases if c["id"] == "vsfetch_format_float4"][:1] + \
                      [c for c in cases if c["id"] == "vsfetch_hw_inrange"][:1]
        results = []
        for c in smoke_cases:
            gated, res = BACKEND_FN[c["backend"]](bindir, workdir, c)
            results.append({"id": c["id"], "status": gated["status"], "ok": gated["status"] == "OK"})
        print(json.dumps({"smoke_results": results, "all_ok": all(r["ok"] for r in results)}))
        return

    fout = open(outdir / "04_results.jsonl", "a")
    n_ok = n_fail = 0
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
            n_fail += 1
        print(f"[{i+1}/{len(cases)}] {c['id']}: {gated['status']}", file=sys.stderr)
    fout.close()

    summary = {"schema": 1, "run_id": args.run, "total": len(cases), "n_status_ok": n_ok,
               "n_status_other": n_fail, "finished_utc": datetime.datetime.now(datetime.UTC).isoformat()}
    (outdir / "05_run_manifest.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
