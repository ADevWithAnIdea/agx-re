#!/usr/bin/env python3
"""Opt-in capture runner for EXP-0133 (full-matrix format capability/conversion/
layout/sparse sweep). Each case is one fresh harness process. Unlike EXP-0079's
narrow single-path replay (where any nonzero case exit meant a harness bug and
stopped the run), THIS experiment's capability-sweep render axes (renderable/
blendable/msaa/resolve) are pre-registered to legitimately hard-abort() for every
format whose family is not color-renderable (confirmed during pre-registration
exploration: Metal's render-pipeline-descriptor validation is an unconditional
host-side assertion for a statically-non-renderable/non-blendable pixel format,
not a catchable NSException, and it is not affected by MTL_DEBUG_LAYER). Per
CODEX.md/SUBAGENT_BRIEF.md, "aborts are RESULTS": a case whose contract entry
carries expect_may_abort=true is allowed a nonzero/signal exit without stopping
the run; every OTHER case's nonzero exit is still an unexpected-failure STOP
(the harness fault class EXP-0079's design was built to catch). Every case
result -- success or crash -- is appended to raw/<run-id>/ as its own file,
fflush'd immediately, one process per case, matching the standing gates.
"""
import argparse, datetime, hashlib, json, platform, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
RUNS = ("m4-20260828-run07", "m4-20260828-run08")
AUTH = ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "kernels/capability.metal",
        "kernels/conversion.metal", "harness/probe.m", "run.py", "analysis.py",
        "make_manifest.py", "verify.py", "analysis/formats_generated.json",
        "analysis/gen_formats.py", "analysis/gen_contract.py")
BOUNDARY = "public Metal only; owned textures/buffers; no binary/archive/BO inspection"
SMOKE_CASE_ID = "cap_sampled_00070_RGBA8Unorm"
SMOKE_TIMEOUT = 60

def contract():
    return json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def provenance():
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, text=True, capture_output=True, check=True).stdout.strip()
    por = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=HERE, text=True, capture_output=True, check=True).stdout.splitlines()
    return {"git_revision": rev, "git_dirty": bool(por), "authored_sha256": {x: sha(HERE / x) for x in AUTH}}

def put(p, o):
    p.write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")
    with open(p, "r+") as f:
        f.flush()

def rec(argv, timeout):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p = subprocess.run([str(x) for x in argv], cwd=HERE, text=True, capture_output=True, timeout=timeout)
        return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr, "exception": None}
    except subprocess.TimeoutExpired as e:
        return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": True, "exit": None,
                "stdout": (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""),
                "stderr": (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or ""),
                "exception": "TimeoutExpired"}
    except OSError as e:
        return {"argv": [str(x) for x in argv], "cwd": str(HERE), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": None,
                "stdout": "", "stderr": "", "exception": type(e).__name__}

def env_record():
    return {"schema": 1, **provenance(),
            "sw_vers": rec(["sw_vers"], 5),
            "xcrun_version": rec(["xcrun", "--version"], 5),
            "device_model": rec(["sysctl", "-n", "hw.model"], 5),
            "machine": platform.machine(), "boundary": BOUNDARY}

def env_problems(env):
    bad = []
    for name in ("sw_vers", "xcrun_version", "device_model"):
        z = env[name]
        if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
            bad.append("environment command failed: " + name)
    return bad

def build_argv(work_dir):
    return ["xcrun", "clang", "-fobjc-arc", "-o", work_dir / "probe", HERE / "harness/probe.m",
            "-framework", "Metal", "-framework", "Foundation"]

def fmt_bpp_arg(f):
    return "none" if f.get("bpp") is None else str(f["bpp"])

def build_cases(c):
    """Pure function: CAPTURE_CONTRACT.json -> ordered list of case descriptors.
    Shared by run.py and verify.py (verify.py imports this module for --selftest/
    --seqtest so the two never drift)."""
    cases = []
    timeout = c["timeouts_seconds"]["case_process"]
    render_ineligible = set(c["family_render_ineligible"])
    linear_ineligible = set(c["family_linear_ineligible"])
    device_unsupported = set(c.get("device_unsupported_format_ids", []))
    blendable_ineligible_kinds = set(c.get("blendable_ineligible_kinds", []))
    ds_direct_ineligible = set(c.get("depth_stencil_direct_attach_ineligible_families", []))
    ds_family = {"depth", "stencil", "depthstencil", "stencil_view"}
    for f in c["formats"]:
        for axis in c["capability_axes"]:
            # device_unsupported only implies an abort for axes that actually reach a
            # real newTextureWithDescriptor:/Metal API call for this (kind,family);
            # the harness itself short-circuits atomic (non-integer kind) and linear
            # (family in family_linear_ineligible) to a graceful not_applicable
            # BEFORE ever touching Metal, so those two axes must NOT inherit
            # device_unsupported's abort expectation unconditionally.
            unsupported_reaches_metal = f["id"] in device_unsupported and {
                "sampled": True, "filtered": True, "storage_read": True, "storage_write": True,
                "atomic": f["kind"] in ("uint", "int"),
                "linear": f["family"] not in linear_ineligible,
                "renderable": True, "blendable": True, "msaa": True, "resolve": True,
                "depth_stencil": f["family"] in ds_family,
            }[axis]
            may_abort = unsupported_reaches_metal
            if axis in ("renderable", "msaa", "resolve"):
                may_abort = may_abort or f["family"] in render_ineligible
            elif axis == "blendable":
                may_abort = may_abort or f["family"] in render_ineligible or f["kind"] in blendable_ineligible_kinds
            elif axis == "depth_stencil":
                may_abort = may_abort or f["family"] in ds_direct_ineligible
            cid = "cap_%s_%05d_%s" % (axis, f["id"], f["name"])
            cases.append({"id": cid, "kind": "capability", "expect_may_abort": may_abort, "timeout": timeout,
                          "argv_tail": ["--mode", "capability", "--source", "kernels/capability.metal",
                                        "--id", str(f["id"]), "--name", f["name"], "--kind", f["kind"],
                                        "--family", f["family"], "--bpp", fmt_bpp_arg(f), "--axis", axis]})
    for cs in c["conversion_cases"]:
        cases.append({"id": "conv_%s" % cs, "kind": "conversion", "expect_may_abort": False, "timeout": timeout,
                      "argv_tail": ["--mode", "conversion", "--source", "kernels/conversion.metal", "--case", cs]})
    for f in c["layout_formats"]:
        cid = "layout_%05d_%s" % (f["id"], f["name"])
        cases.append({"id": cid, "kind": "layout", "expect_may_abort": False, "timeout": timeout,
                      "argv_tail": ["--mode", "layout", "--id", str(f["id"]), "--name", f["name"],
                                    "--family", f["family"], "--bpp", fmt_bpp_arg(f)]})
    bf = c["layout_below_minimum_format"]
    cases.append({"id": "layout_below_minimum_%05d_%s" % (bf["id"], bf["name"]), "kind": "layout_below_min",
                  "expect_may_abort": True, "timeout": c["timeouts_seconds"]["case_process"],
                  "argv_tail": ["--mode", "layout", "--id", str(bf["id"]), "--name", bf["name"],
                                "--family", bf["family"], "--bpp", fmt_bpp_arg(bf), "--below-minimum"]})
    for f in c["sparse_formats"]:
        cid = "sparse_%05d_%s" % (f["id"], f["name"])
        cases.append({"id": cid, "kind": "sparse", "expect_may_abort": False, "timeout": timeout,
                      "argv_tail": ["--mode", "sparse", "--id", str(f["id"]), "--name", f["name"]]})
    return cases

def case_argv(work_dir, case):
    return [work_dir / "probe"] + case["argv_tail"]

def run_manifest_record(run_id, case_ids):
    return {"schema": 1, "run_id": run_id, "case_count": len(case_ids), "cases": list(case_ids),
            "fresh_process_per_case": True,
            "runner_sha256": sha(HERE / "run.py"),
            "harness_sha256": sha(HERE / "harness/probe.m"),
            "capability_kernel_sha256": sha(HERE / "kernels/capability.metal"),
            "conversion_kernel_sha256": sha(HERE / "kernels/conversion.metal"),
            "contract_sha256": sha(HERE / "CAPTURE_CONTRACT.json")}

def smoke_gate(work_root, cs):
    c = next(x for x in cs if x["id"] == SMOKE_CASE_ID)
    d = work_root / "smoke"
    d.mkdir(parents=True)
    z = rec(case_argv(work_root, c), SMOKE_TIMEOUT)
    put(d / "smoke.json", z)
    problems = []
    if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
        problems.append("smoke case did not exit 0 cleanly: exit=%r exception=%r timed_out=%r" % (z["exit"], z["exception"], z["timed_out"]))
        return problems
    try:
        p = json.loads(z["stdout"])
    except ValueError:
        return ["smoke stdout is not exactly one JSON object (%d bytes)" % len(z["stdout"])]
    if p.get("id") != 70 or p.get("name") != "RGBA8Unorm" or p.get("status") != "ok" or "axes" not in p:
        problems.append("smoke payload identity/shape mismatch: %r" % ({k: p.get(k) for k in ("id", "name", "status")},))
    axes = p.get("axes", {})
    if "sampled" not in axes:
        problems.append("smoke payload missing axis 'sampled'")
    return problems

GATE_TIMEOUT = 900

def run_gate(args):
    try:
        r = subprocess.run(["python3", "-B"] + args, cwd=HERE, timeout=GATE_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SystemExit("run gate timed out after %ds: %s" % (GATE_TIMEOUT, " ".join(args)))
    if r.returncode:
        raise SystemExit("run gate failed: " + " ".join(args))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved pre-GPU review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ",".join(RUNS))
    run_gate(["verify.py", "--selftest"])
    run_gate(["verify.py", "--seqtest"])
    run_gate(["make_manifest.py", "--check"])
    run_gate(["verify.py", "--preflight" if a.run_id == RUNS[0] else "--between-runs"])
    current = provenance()
    if a.run_id == RUNS[1]:
        # Gate on authored_sha256 ONLY, never git_revision: this repo's sibling
        # experiments commit continuously, and a live-HEAD gate here would abort
        # a correctly-paired second run through no fault of this experiment's own
        # files (the exact EXP-0082 landmine; see SUBAGENT_BRIEF.md "Pin the
        # revision at pre-registration; do not gate on live HEAD" and
        # provenance/quarantined_attempt3/NOTE.md, which hit this once already).
        # git_revision/git_dirty are still recorded per run (env_record() below)
        # for audit, just not compared for equality.
        first = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        if first.get("authored_sha256") != current["authored_sha256"]:
            raise SystemExit("run02 authored source differs from closed run01")
    raw = HERE / "raw" / a.run_id
    work_root = HERE / "work" / a.run_id
    if raw.exists():
        raise SystemExit("append-only raw path already exists")
    work_parent = HERE / "work"
    if work_root.exists() or (work_parent.exists() and any(work_parent.iterdir())):
        raise SystemExit("scratch path already exists or work is not empty; remove a retained pre-capture stop first")
    work_root.mkdir(parents=True)
    try:
        c = contract()
        cs = build_cases(c)
        env = env_record()
        if env_problems(env):
            put(work_root / "STOP.json", {"schema": 1, "phase": "environment", "problems": env_problems(env),
                                          "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: environment")
        build = rec(build_argv(work_root), c["timeouts_seconds"]["host_build"])
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None:
            put(work_root / "STOP.json", {"schema": 1, "phase": "host_build", "problems": ["host build failed"],
                                          "receipt": build, "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: host build")
        problems = smoke_gate(work_root, cs)
        if problems:
            put(work_root / "STOP.json", {"schema": 1, "phase": "pre_capture_smoke", "case": SMOKE_CASE_ID,
                                          "problems": problems, "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: smoke gate (raw tree not created; pre-capture repair authorized)")
        raw.mkdir(parents=True)
        put(raw / "00_inputs.json", env)
        put(raw / "01_host_build.json", build)
        cases_dir = raw / "cases"
        cases_dir.mkdir()
        unexpected_failures = []
        for i, case in enumerate(cs):
            z = rec(case_argv(work_root, case), case["timeout"])
            put(cases_dir / (case["id"] + ".json"), z)
            bad = z["timed_out"] or z["exception"] is not None or (z["exit"] not in (0,) and not case["expect_may_abort"])
            if bad:
                unexpected_failures.append({"case": case["id"], "exit": z["exit"], "exception": z["exception"], "timed_out": z["timed_out"]})
                put(raw / "STOP.json", {"schema": 1, "phase": "case", "case": case["id"],
                                        "detail": unexpected_failures[-1], "automatic_retry": False})
                print("STOP at case %d/%d: %s" % (i + 1, len(cs), case["id"]), file=sys.stderr)
                return
            if (i + 1) % 50 == 0:
                print("progress: %d/%d cases (%s)" % (i + 1, len(cs), case["id"]), file=sys.stderr)
        put(raw / "run_manifest.json", run_manifest_record(a.run_id, [x["id"] for x in cs]))
        print("run %s complete: %d cases" % (a.run_id, len(cs)), file=sys.stderr)
    finally:
        if not (work_root / "STOP.json").exists():
            shutil.rmtree(work_root, ignore_errors=True)

if __name__ == "__main__":
    main()
