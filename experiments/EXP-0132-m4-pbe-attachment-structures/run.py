#!/usr/bin/env python3
"""EXP-0132 capture runner.

Schema constants here are the single authoritative source; verify.py and
analysis.py import them and never restate them.

Address-normalization policy: within harness/wtrace.c's `mrt-attachment-
descriptors` capture (0x10000018200, treated here as a sequence of 0x20-byte
records starting at absolute offset 0, spanning the arena's own two header
words at +0x000/+0x200 plus the k=0..7 LOAD array at +0x20+k*0x20 and
STORE array at +0x220+k*0x20 -- EXP-0048/EXP-M4-08/09/EXP-0108), each
record's relative +0x08..+0x0c (5 bytes, the low-40-bits-of-a-qword
surface-address subfield established by EXP-0048/EXP-M4-08) is masked to
zero in the gated record; the unmasked bytes go only in the ungated timing
side channel. Within `clear-color-arena`, two bytes at fixed absolute
offset 0x536/0x537 were found nondeterministic between two SAME-CASE dry
runs during this experiment's own pre-capture diagnostic (see
PRE_REGISTRATION.md section 6/PROGRESS.md M6) and are masked identically.
"""
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "harness"))
import casematrix as CM

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

RUNS = ("m4-20260828-run01", "m4-20260828-run02")
BOUNDARY = {
    "apple_binary_archive_bo_or_compiled_shader_byte_inspection":
        "only our own generated MSL (VS/FS compiled at runtime per case) and its own "
        "readback bytes; the interposer never inspects Metal/AGX*/IOGPU framework code",
    "private_api_or_trace": "NONE (public Metal + public IOKit user-client selectors only)",
    "other_machine": "NONE (A18 hands-off; never macvdmtool; local M4 only)",
}
TIMEOUTS = {"env_command": 15, "host_build": 120, "smoke_case": 60, "case": 60}

NAMED_ROLES = ("vdm-command-state", "fixed-function-render-state", "tiling-state",
               "mrt-attachment-descriptors", "clear-color-arena",
               "single-rt-color-descriptor", "attachment-slot-b",
               "sparse-tiler-param-header")
DEEP_ROLES = ("mrt-attachment-descriptors", "clear-color-arena")

MRT_WINDOW_BYTES = 0x500       # covers header@0x000, k=0..7 LOAD (0x20..0x220), header@0x200, k=0..7 STORE
MRT_RECORD_STRIDE = 0x20
ADDR_OFFSET, ADDR_LEN = 0x08, 5

CCA_WINDOW_BYTES = 0x600
CCA_FLAKY_OFFSETS = (0x536, 0x537)

REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit", "signal",
            "stdout", "stderr", "exception"}
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
               "authored_sha256", "sw_vers", "xcrun_version", "python", "machine",
               "boundary", "timeouts_seconds"}
BUILD_KEYS = {"schema", "harness_build"}
DISPATCH_KEYS = {"argv", "cwd", "started_utc", "finished_utc", "duration_seconds",
                  "n_cases", "status_counts", "results_sha256", "results_lines",
                  "timing_sha256", "timing_lines"}
NAMED_KEYS = {"present", "size", "content_captured"}
CASE_KEYS = {"i", "name", "axis", "boundary", "status", "cb_status", "cb_error", "rts", "named"}
TIMING_KEYS = {"i", "name", "duration_ms", "stdout_raw", "stderr_raw", "returncode",
               "inventory_full", "addresses"}
STATUS_ALLOWED = {"OK", "PIPELINE_FAIL", "COLOR_TEXTURE_CREATE_FAIL",
                   "DEPTH_TEXTURE_CREATE_FAIL", "STENCIL_TEXTURE_CREATE_FAIL",
                   "ENCODER_CREATE_FAIL", "CMDBUF_ERROR", "NSEXCEPTION_ENCODER",
                   "NSEXCEPTION_ENCODE", "HARNESS_TIMEOUT", "HARNESS_CRASH",
                   "PROCESS_ABORT", "NO_RESULT"}
AUTH_DOC = ("README.md", "PRE_REGISTRATION.md")   # RESULTS.md/PROGRESS.md are living docs
AUTH_CODE = ("harness/wtrace.c", "harness/probe.m", "harness/build.sh",
             "harness/casematrix.py", "run.py", "analysis.py", "verify.py",
             "make_manifest.py")
AUTH_ALL = AUTH_DOC + AUTH_CODE


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def run_record(argv, cwd, timeout, **kw):
    z = {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
         "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "timed_out": False, "exit": None, "signal": None, "stdout": "", "stderr": "",
         "exception": None}
    try:
        p = subprocess.run([str(x) for x in argv], cwd=str(cwd), timeout=timeout,
                            capture_output=True, text=True, **kw)
        z["exit"] = p.returncode
        if p.returncode is not None and p.returncode < 0:
            z["signal"] = -p.returncode
        z["stdout"] = p.stdout
        z["stderr"] = p.stderr
    except subprocess.TimeoutExpired as e:
        z["timed_out"] = True
        z["stdout"] = e.stdout or ""
        z["stderr"] = e.stderr or ""
    except Exception as e:
        z["exception"] = repr(e)
    assert set(z) == REC_KEYS
    return z


def env_snapshot():
    rev = run_record(["git", "rev-parse", "HEAD"], REPO, TIMEOUTS["env_command"])
    dirty = run_record(["git", "status", "--porcelain"], REPO, TIMEOUTS["env_command"])
    dirty_entries = sorted(l for l in dirty["stdout"].splitlines() if l.strip())
    sw = run_record(["sw_vers", "-productVersion"], HERE, TIMEOUTS["env_command"])
    xc = run_record(["xcrun", "--version"], HERE, TIMEOUTS["env_command"])
    machine = run_record(["sysctl", "-n", "hw.model"], HERE, TIMEOUTS["env_command"])
    ah = {p: sha(HERE / p) for p in AUTH_ALL}
    z = {
        "schema": 1,
        "git_revision": rev["stdout"].strip(),
        "git_dirty": bool(dirty_entries),
        "experiment_tree_dirty_entries": [e for e in dirty_entries if "EXP-0132" in e],
        "authored_sha256": ah,
        "sw_vers": sw["stdout"].strip(),
        "xcrun_version": xc["stdout"].strip(),
        "python": sys.version,
        "machine": machine["stdout"].strip(),
        "boundary": BOUNDARY,
        "timeouts_seconds": TIMEOUTS,
    }
    assert set(z) == INPUTS_KEYS
    return z


def build_harness(bindir):
    bindir = Path(bindir)
    bindir.mkdir(parents=True, exist_ok=True)
    r = run_record(["sh", str(HERE / "harness" / "build.sh"), str(bindir)], HERE,
                    TIMEOUTS["host_build"])
    ok = (r["exit"] == 0 and (bindir / "wtrace.dylib").exists() and (bindir / "probe").exists())
    z = {"schema": 1, "harness_build": {"ok": ok, "record": r}}
    assert set(z) == BUILD_KEYS
    return z, ok


def read_inventory(dumpdir):
    """Return {(va_hex, role): (size, content_captured, sha256, tries)} for
    dump00/inventory.tsv under dumpdir, or {} if absent (no dump captured)."""
    p = Path(dumpdir) / "dump00" / "inventory.tsv"
    rows = {}
    if not p.exists():
        return rows
    with open(p) as f:
        header = f.readline()
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 7:
                continue
            va, size, handle, role, captured, sha256, tries = parts
            rows[(va, role)] = {"size": int(size, 16), "captured": captured == "1",
                                 "sha256": sha256, "tries": int(tries)}
    return rows


def mask_stride(data, stride, addr_off, addr_len):
    b = bytearray(data)
    for base in range(0, len(b) - addr_off, stride) if stride else []:
        lo = base + addr_off
        hi = min(lo + addr_len, len(b))
        if lo < len(b):
            for i in range(lo, hi):
                b[i] = 0
    return bytes(b)


def extract_named(dumpdir, inv, addresses_out):
    """Build the gated `named` dict and populate addresses_out (ungated)."""
    named = {}
    dump_sub = Path(dumpdir) / "dump00"
    for role in NAMED_ROLES:
        matches = [(va, r) for (va, r) in inv if r == role]
        if not matches:
            named[role] = {"present": False, "size": None, "content_captured": False}
            continue
        va, _ = matches[0]
        meta = inv[(va, role)]
        entry = {"present": True, "size": meta["size"], "content_captured": meta["captured"]}
        if role in DEEP_ROLES and meta["captured"]:
            binp = dump_sub / f"va_{va[2:]}.bin"
            if binp.exists():
                raw = binp.read_bytes()
                addresses_out[role] = raw[:0x40].hex()  # small unmasked excerpt, ungated only
                if role == "mrt-attachment-descriptors":
                    window = raw[:MRT_WINDOW_BYTES]
                    masked = mask_stride(window, MRT_RECORD_STRIDE, ADDR_OFFSET, ADDR_LEN)
                    entry["window_hex"] = masked.hex()
                elif role == "clear-color-arena":
                    window = bytearray(raw[:CCA_WINDOW_BYTES])
                    for off in CCA_FLAKY_OFFSETS:
                        if off < len(window):
                            window[off] = 0
                    entry["window_hex"] = bytes(window).hex()
        named[role] = entry
    assert all(set(v) <= (NAMED_KEYS | {"window_hex"}) for v in named.values())
    return named


def run_one_case(c, i, probe_bin, wtrace_dylib, casedir, timeout):
    casedir = Path(casedir)
    casedir.mkdir(parents=True, exist_ok=True)
    cfgp = casedir / "case.json"
    resp = casedir / "result.json"
    dumpdir = casedir / "dumps"
    tracelog = casedir / "trace.log"
    with open(cfgp, "w") as f:
        json.dump(c, f)
    env = dict(os.environ)
    env["DYLD_INSERT_LIBRARIES"] = str(wtrace_dylib)
    env["WTRACE_LOG"] = str(tracelog)
    env["WTRACE_DUMP_DIR"] = str(dumpdir)
    t0 = time.time()
    rec = run_record([probe_bin, str(cfgp), str(resp), "--dump"], casedir, timeout, env=env)
    duration_ms = int((time.time() - t0) * 1000)

    gated = {"i": i, "name": c["name"], "axis": c["axis"], "boundary": c["boundary"]}
    timing = {"i": i, "name": c["name"], "duration_ms": duration_ms,
              "stdout_raw": rec["stdout"], "stderr_raw": rec["stderr"],
              "returncode": rec["exit"], "inventory_full": [], "addresses": {}}

    if rec["timed_out"]:
        gated.update({"status": "HARNESS_TIMEOUT", "cb_status": None, "cb_error": None, "rts": None})
    elif rec["signal"]:
        gated.update({"status": "PROCESS_ABORT", "cb_status": None, "cb_error": None, "rts": None})
    elif rec["exit"] != 0 or not resp.exists():
        gated.update({"status": "HARNESS_CRASH" if rec["exit"] not in (0,) else "NO_RESULT",
                      "cb_status": None, "cb_error": None, "rts": None})
    else:
        try:
            result = json.loads(resp.read_text())
        except Exception:
            result = {}
        st = result.get("status", "NO_RESULT")
        gated.update({"status": st if st in STATUS_ALLOWED else "NO_RESULT",
                      "cb_status": result.get("cb_status"),
                      "cb_error": result.get("cb_error"),
                      "rts": result.get("rts")})

    inv = read_inventory(dumpdir)
    timing["inventory_full"] = [
        {"va": va, "role": role, **meta} for (va, role), meta in sorted(inv.items())
    ]
    gated["named"] = extract_named(dumpdir, inv, timing["addresses"])

    assert set(gated) == CASE_KEYS, sorted(set(gated) ^ CASE_KEYS)
    assert set(timing) == TIMING_KEYS, sorted(set(timing) ^ TIMING_KEYS)
    return gated, timing


def smoke_gate(bindir):
    """One scratch case into work/, never raw/. Returns True/(status,err)."""
    c = CM.CASES[0]
    workdir = HERE / "work" / "smoke_gate"
    if workdir.exists():
        shutil.rmtree(workdir)
    gated, timing = run_one_case(c, 0, bindir / "probe", bindir / "wtrace.dylib",
                                  workdir, TIMEOUTS["smoke_case"])
    ok = gated["status"] == "OK"
    return ok, gated


def execute(run_id):
    rawdir = HERE / "raw" / run_id
    if rawdir.exists():
        print(f"REFUSING: raw/{run_id} already exists (never reuse a run id)", file=sys.stderr)
        return 3

    inputs = env_snapshot()
    bindir = HERE / "work" / f"bin_{run_id}"
    if bindir.exists():
        shutil.rmtree(bindir)
    build, build_ok = build_harness(bindir)
    if not build_ok:
        print("BUILD FAILED", json.dumps(build, indent=2)[:4000], file=sys.stderr)
        return 3

    ok, smoke = smoke_gate(bindir)
    if not ok:
        print("SMOKE GATE FAILED", json.dumps(smoke, indent=2)[:4000], file=sys.stderr)
        return 3

    rawdir.mkdir(parents=True)
    (rawdir / "00_inputs.json").write_text(json.dumps(inputs, indent=2))
    (rawdir / "01_cases.json").write_text(json.dumps(CM.CASES, indent=2))
    (rawdir / "02_build.json").write_text(json.dumps(build, indent=2))

    results_path = rawdir / "03_results.jsonl"
    timing_path = rawdir / "03_timing.jsonl"
    status_counts = {}
    t0 = datetime.datetime.now(datetime.timezone.utc)
    with open(results_path, "a") as rf, open(timing_path, "a") as tf:
        for i, c in enumerate(CM.CASES):
            casedir = HERE / "work" / f"cases_{run_id}" / c["name"]
            gated, timing = run_one_case(c, i, bindir / "probe", bindir / "wtrace.dylib",
                                          casedir, TIMEOUTS["case"])
            status_counts[gated["status"]] = status_counts.get(gated["status"], 0) + 1
            rf.write(json.dumps(gated, sort_keys=True) + "\n"); rf.flush(); os.fsync(rf.fileno())
            tf.write(json.dumps(timing, sort_keys=True) + "\n"); tf.flush(); os.fsync(tf.fileno())
            print(f"[{run_id}] {i+1}/{len(CM.CASES)} {c['name']}: {gated['status']}")
    t1 = datetime.datetime.now(datetime.timezone.utc)

    dispatch = {
        "argv": sys.argv, "cwd": str(HERE),
        "started_utc": t0.isoformat(), "finished_utc": t1.isoformat(),
        "duration_seconds": (t1 - t0).total_seconds(),
        "n_cases": len(CM.CASES), "status_counts": status_counts,
        "results_sha256": sha(results_path), "results_lines": sum(1 for _ in open(results_path)),
        "timing_sha256": sha(timing_path), "timing_lines": sum(1 for _ in open(timing_path)),
    }
    assert set(dispatch) == DISPATCH_KEYS
    (rawdir / "04_dispatch.json").write_text(json.dumps(dispatch, indent=2))
    print(json.dumps(dispatch, indent=2))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if args.execute:
        sys.exit(execute(args.run_id))
    else:
        print("nothing to do without --execute", file=sys.stderr)
        sys.exit(2)
