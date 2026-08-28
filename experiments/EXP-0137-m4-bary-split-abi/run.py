#!/usr/bin/env python3
"""EXP-0129 capture driver. One process per invocation; appends one JSON
line per case to raw/<run_id>/04_results.jsonl immediately after the case
completes (flushed + fsynced), so a kill costs at most the current case.
Every external tool invocation is our own binary (built fresh from
committed source, never a prebuilt artifact) or the unmodified
tools/shdump/{shdump.m,agxparse.py} and tools/agx-isa/isadb.py (read-only,
imported not copied). Architecture follows EXP-0109/EXP-0117's run.py (our
own prior authored code in this project).

Usage:
  python3 run.py --run <run_id> --out raw/<run_id> [--smoke-only]
"""
import argparse, hashlib, json, os, subprocess, sys, time, datetime, platform
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "analysis"))
import casematrix as CM
import isahelper

SHDUMP_SRC = REPO / "tools" / "shdump" / "shdump.m"
AGXPARSE = REPO / "tools" / "shdump" / "agxparse.py"

AUTHORED_FILES = [
    "PRE_REGISTRATION.md", "README.md", "casematrix.py", "run.py", "verify.py",
    "kernels/bary.metal", "kernels/bary_qual_persp.metal", "kernels/bary_qual_noperspective.metal",
    "kernels/split_negctrl.metal", "kernels/split_epilog.metal", "kernels/split_prolog.metal",
    "kernels/split_callret.metal",
    "harness/struct_extract.m", "harness/struct_extract_vonly.m", "harness/render.m",
    "harness/compute_callret.m",
    "analysis/isahelper.py",
]

TIMEOUT_CASE = 30
TIMEOUT_BUILD = 60

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
        "struct_extract": HERE / "harness" / "struct_extract.m",
        "struct_extract_vonly": HERE / "harness" / "struct_extract_vonly.m",
        "render": HERE / "harness" / "render.m",
        "compute_callret": HERE / "harness" / "compute_callret.m",
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
    gated = {"backend": backend}
    if extra_gated:
        gated.update(extra_gated)
    if res["timed_out"]:
        gated["status"] = "TIMEOUT"
        return gated
    rc = res["returncode"]
    if rc is not None and rc < 0:
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


# ---------------------------------------------------------------- backends --
def do_bary_struct(bindir, workdir, case):
    p = case["params"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "struct_extract"), "-o", str(out), "--source", str(HERE / case["source"]),
            "--vertex", p["vertex"], "--fragment", p["fragment"], "--natt", str(p["natt"])]
    res = run_cmd(argv)
    gated = {"backend": "bary_struct", "variant": p["variant"], "vertex": p["vertex"],
              "fragment": p["fragment"], "natt": p["natt"]}
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
    if stdout != "OK":
        gated["status"] = "FAIL"
        gated["error"] = stdout[-800:]
        return gated, res
    gated["status"] = "OK"
    hexstr, err = extract_hex(out, "fragment")
    gated["fragment_hex"] = hexstr
    gated["fragment_hex_len"] = len(hexstr) // 2 if hexstr else None
    gated["structure"] = struct_report(out)
    gated["disasm"] = isahelper.disasm_summary(hexstr or "")
    return gated, res


def do_bary_render(bindir, workdir, case):
    p = case["params"]
    argv = [str(bindir / "render"), "--source", str(HERE / case["source"]), "--mode", "bary",
            "--variant", p["variant"]]
    res = run_cmd(argv)
    gated = _abort_or_parse_json(res, "bary_render", {"variant": p["variant"]})
    return gated, res


def do_qual_struct(bindir, workdir, case):
    p = case["params"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "struct_extract"), "-o", str(out), "--source", str(HERE / case["source"]),
            "--vertex", p["vertex"], "--fragment", p["fragment"], "--natt", "1"]
    res = run_cmd(argv)
    gated = {"backend": "qual_struct", "vertex": p["vertex"], "fragment": p["fragment"]}
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
        gated["fragment_hex_len"] = len(hexstr) // 2 if hexstr else None
        gated["disasm"] = isahelper.disasm_summary(hexstr or "")
    else:
        gated["status"] = "REJECTED"
        gated["compiler_output"] = stdout[-1200:]
    return gated, res


def do_negctrl_struct(bindir, workdir, case):
    p = case["params"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "struct_extract"), "-o", str(out), "--source", str(HERE / case["source"]),
            "--vertex", p["vertex"], "--fragment", p["fragment"], "--natt", str(p["natt"])]
    res = run_cmd(argv)
    gated = {"backend": "negctrl_struct"}
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
        gated["structure"] = struct_report(out)
        hexstr, err = extract_hex(out, "fragment")
        gated["disasm"] = isahelper.disasm_summary(hexstr or "")
    else:
        gated["status"] = "REJECTED"
        gated["compiler_output"] = stdout[-1200:]
    return gated, res


def do_negctrl_render(bindir, workdir, case):
    argv = [str(bindir / "render"), "--source", str(HERE / case["source"]), "--mode", "negctrl"]
    res = run_cmd(argv)
    gated = _abort_or_parse_json(res, "negctrl_render")
    return gated, res


def do_epilog_struct(bindir, workdir, case):
    p = case["params"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "struct_extract"), "-o", str(out), "--source", str(HERE / case["source"]),
            "--vertex", p["vertex"], "--fragment", p["fragment"], "--natt", str(p["natt"])]
    res = run_cmd(argv)
    gated = {"backend": "epilog_struct"}
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
        gated["structure"] = struct_report(out)
        hexstr, err = extract_hex(out, "fragment")
        gated["disasm"] = isahelper.disasm_summary(hexstr or "")
    else:
        gated["status"] = "FAIL"
        gated["error"] = stdout[-800:]
    return gated, res


def do_epilog_render(bindir, workdir, case):
    p = case["params"]
    argv = [str(bindir / "render"), "--source", str(HERE / case["source"]), "--mode", "splitepilog",
            "--blendmode", str(p["blendmode"])]
    res = run_cmd(argv)
    gated = _abort_or_parse_json(res, "epilog_render", {"blendmode": p["blendmode"]})
    return gated, res


def do_prolog_struct(bindir, workdir, case):
    p = case["params"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "struct_extract_vonly"), "-o", str(out), "--source", str(HERE / case["source"]),
            "--vertex", p["vertex"]]
    res = run_cmd(argv)
    gated = {"backend": "prolog_struct"}
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
        gated["structure"] = struct_report(out)
        hexstr, err = extract_hex(out, "vertex")
        gated["disasm"] = isahelper.disasm_summary(hexstr or "")
    else:
        gated["status"] = "FAIL"
        gated["error"] = stdout[-800:]
    return gated, res


def do_prolog_render(bindir, workdir, case):
    argv = [str(bindir / "render"), "--source", str(HERE / case["source"]), "--mode", "splitprolog"]
    res = run_cmd(argv)
    gated = _abort_or_parse_json(res, "prolog_render")
    return gated, res


def do_callret_struct(bindir, workdir, case):
    p = case["params"]
    fn = p["function"]
    out = workdir / f"{case['id']}.bin"
    argv = [str(bindir / "shdump"), "-o", str(out), "-f", fn, str(HERE / case["source"])]
    res = run_cmd(argv)
    gated = {"backend": "callret_struct", "function": fn}
    if res["timed_out"]:
        gated["status"] = "TIMEOUT"
        return gated, res
    if res["returncode"] != 0 or not out.exists():
        gated["status"] = "FAIL"
        gated["error"] = res["stderr"][-1000:]
        return gated, res
    gated["structure"] = struct_report(out)
    hexstr, err = extract_hex(out, "compute", symbol="_agc.main")
    gated["status"] = "OK" if hexstr else "EXTRACT_FAIL"
    gated["caller_hex_len"] = len(hexstr) // 2 if hexstr else None
    gated["caller_disasm"] = isahelper.disasm_summary(hexstr or "")
    callee_name = None
    for rn in gated["structure"].get("region_names", []):
        if rn not in ("_agc.main.constant_program", "_agc.main"):
            callee_name = rn
            break
    gated["callee_symbol"] = callee_name
    if callee_name:
        chex, cerr = extract_hex(out, "compute", symbol=callee_name)
        gated["callee_disasm"] = isahelper.disasm_summary(chex or "")
    return gated, res


def do_callret_render(bindir, workdir, case):
    p = case["params"]
    argv = [str(bindir / "compute_callret"), "--source", str(HERE / case["source"]), "--n", str(p["n"])]
    res = run_cmd(argv)
    gated = _abort_or_parse_json(res, "callret_render", {"n": p["n"]})
    return gated, res


BACKEND_FN = {
    "bary_struct": do_bary_struct,
    "bary_render": do_bary_render,
    "qual_struct": do_qual_struct,
    "negctrl_struct": do_negctrl_struct,
    "negctrl_render": do_negctrl_render,
    "epilog_struct": do_epilog_struct,
    "epilog_render": do_epilog_render,
    "prolog_struct": do_prolog_struct,
    "prolog_render": do_prolog_render,
    "callret_struct": do_callret_struct,
    "callret_render": do_callret_render,
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
        smoke_cases = [c for c in cases if c["id"] == "barystruct_base"][:1] + \
                      [c for c in cases if c["id"] == "baryrender_base"][:1]
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
