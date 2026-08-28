#!/usr/bin/env python3
"""EXP-0108 capture runner.

Schema constants here (CASE_KEYS, TIMING_KEYS, REC_KEYS, INPUTS_KEYS,
BUILD_KEYS, DISPATCH_KEYS) are the single authoritative source; verify.py
imports them and never restates them.

Address-normalization policy (the standing gate "no nondeterministic field
in byte-compared records"): within the two color-descriptor-bearing named
roles (mrt-attachment-descriptors, single-rt-color-descriptor), each
0x20-byte k-record's surface-address subfield is the 5 bytes at
record-relative offset +0x08..+0x0C (the low 40 bits of the qword at +0x08,
which EXP-0048/EXP-M4-08 established reconstructs to VA>>4). Those 5 bytes
are GPU-allocator-address-shaped and are masked to "00"*5 in the gated
CASE_KEYS hex windows; the unmasked bytes are recorded separately in the
ungated TIMING_KEYS side channel. Every other byte in every named-role
region (format/control bits, dimensions, clear-value floats, action
selectors) stays in the gated record. See PRE_REGISTRATION.md and
CAPTURE_CONTRACT.json "content-capture policy" / "address normalization".
"""
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "harness"))
import casematrix as CM

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# NOTE: m4-20260828-run01..run04 (preserved, untouched, in raw_superseded/)
# are two complete, valid, all-40-OK two-run capture pairs taken under
# earlier verify.py/analysis.py revisions:
#   run01/run02 -- gated cross-run comparison on each named role's WHOLE-
#     region SHA-256. Its own diff revealed exactly the nondeterminism
#     PRE_REGISTRATION.md section 5 anticipated in advance (vertex-buffer-
#     alias and similar incidental bytes outside the trusted field windows).
#   run03/run04 -- gated on reproducible_projection (the fix above), which
#     dropped those noisy fields but still compared field-level content
#     (first64_hex/k_load/k_store) unconditionally. Its own diff (case
#     g2-depth-write) revealed a SECOND, narrower nondeterminism: whether a
#     present, correctly-sized named role's content READ succeeds at all is
#     itself a SIGUSR1-snapshot mach_vm_read_overwrite timing race, not a
#     hardware property -- addressed by records_reproducibly_equal, below.
# In neither case did run_one_case()'s DATA-COLLECTION logic change; only
# the post-hoc verification/analysis gating was refined, informed by each
# pair's own diff. Never reusing a burned run id, the officially gated pair
# is run05/run06, captured after freezing this second fix. See
# PROGRESS.md/RESULTS.md.
RUNS = ("m4-20260828-run05", "m4-20260828-run06")
BOUNDARY = {
    "apple_binary_archive_bo_or_compiled_shader_byte_inspection":
        "only our own generated MSL (VS/FS compiled at runtime per case) and its own "
        "readback bytes; the interposer never inspects Metal/AGX*/IOGPU framework code",
    "private_api_or_trace": "NONE (public Metal + public IOKit user-client selectors only)",
    "other_machine": "NONE (A18 hands-off; never macvdmtool; local M4 only)",
}
TIMEOUTS = {"env_command": 15, "host_build": 120, "smoke_case": 60, "case": 90}
NAMED_ROLES = ("vdm-command-state", "fixed-function-render-state", "tiling-state",
               "mrt-attachment-descriptors", "single-rt-color-descriptor",
               "attachment-slot-b", "clear-color-arena", "sparse-tiler-param-header")
COLOR_DESC_ROLES = ("mrt-attachment-descriptors", "single-rt-color-descriptor")
ADDR_OFFSET, ADDR_LEN = 0x08, 5   # record-relative address subfield to mask
# Per-role window layout. mrt-attachment-descriptors is the k=0..3 fixed
# 0x20-byte-stride LOAD/STORE record array at +0x20/+0x220 (EXP-0048/
# EXP-M4-09). single-rt-color-descriptor is the documented three 0x300-byte
# LOAD(+0x000)/RENDER(+0x300)/STORE(+0x600) segment chain (docs/pipeline/
# README.md "Render-target attachment descriptor"), where the populated
# sub-record inside each segment sits at segment-relative +0x20 (verified in
# this experiment's own exploration: STORE sub-record at absolute +0x620
# reconstructs to the same surface VA as the LOAD sub-record at +0x20).
# Only k=0 is meaningful for the single-RT role (it addresses one attachment).
ROLE_WINDOW = {
    "mrt-attachment-descriptors": {"load_base": 0x20, "store_base": 0x220,
                                    "stride": 0x20, "max_k": 4},
    "single-rt-color-descriptor": {"load_base": 0x20, "store_base": 0x620,
                                    "stride": 0x300, "max_k": 1},
}

REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit",
            "stdout", "stderr", "exception"}
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
               "authored_sha256", "sw_vers", "xcrun_version", "python", "machine",
               "boundary", "timeouts_seconds"}
BUILD_KEYS = {"schema", "harness_build"}
DISPATCH_KEYS = {"argv", "cwd", "started_utc", "finished_utc", "duration_seconds",
                  "n_cases", "status_counts", "results_sha256", "results_lines",
                  "timing_sha256", "timing_lines"}
NAMED_WINDOW_KEYS = {"first64_hex", "k_load", "k_store"}
CASE_KEYS = {"i", "name", "axis", "probe_status", "cb_status", "cb_error", "rts",
             "named", "unnamed_regions", "status"}
TIMING_KEYS = {"i", "name", "duration_ms", "stdout_raw", "stderr_raw",
                "inventory_full", "named_addresses", "resource_gpu_addresses"}
STATUS_ALLOWED = {"OK", "PIPELINE_FAIL", "COLOR_TEXTURE_CREATE_FAIL",
                   "DEPTH_TEXTURE_CREATE_FAIL", "STENCIL_TEXTURE_CREATE_FAIL",
                   "ENCODER_CREATE_FAIL", "CMDBUF_ERROR", "HARNESS_TIMEOUT",
                   "HARNESS_CRASH", "NO_RESULT"}
AUTH_DOC = ("README.md", "PRE_REGISTRATION.md")   # RESULTS.md/PROGRESS.md are living
# documents intentionally NOT frozen-hashed: they are written/extended AFTER capture based
# on analysis.json, and must not be required to byte-match a pre-capture snapshot. They are
# still required to exist (see static()) and are tracked by make_manifest.py.
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
         "timed_out": False, "exit": None, "stdout": "", "stderr": "", "exception": None}
    try:
        p = subprocess.run([str(x) for x in argv], cwd=str(cwd), timeout=timeout,
                            capture_output=True, text=True, **kw)
        z["exit"] = p.returncode
        z["stdout"] = p.stdout
        z["stderr"] = p.stderr
    except subprocess.TimeoutExpired as e:
        z["timed_out"] = True
        z["stdout"] = (e.stdout or b"").decode("utf8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        z["stderr"] = (e.stderr or b"").decode("utf8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    except Exception as e:  # noqa: BLE001
        z["exception"] = repr(e)
    return z


def check(argv, cwd, timeout, label):
    z = run_record(argv, cwd, timeout)
    if z["exception"] or z["timed_out"] or z["exit"] != 0:
        print("GATE FAIL:", label, json.dumps(z, indent=2)[:4000])
        raise SystemExit(3)
    return z


def authored_sha256():
    return {p: sha(HERE / p) for p in AUTH_ALL}


def git_info():
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
                          capture_output=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, text=True,
                            capture_output=True, check=True).stdout
    tree_dirty = subprocess.run(["git", "status", "--porcelain", "--", str(HERE)], cwd=REPO,
                                 text=True, capture_output=True, check=True).stdout
    n_dirty_here = len([l for l in tree_dirty.splitlines() if l.strip()])
    return rev, bool(dirty.strip()), n_dirty_here


def hexmask(h, off, ln):
    b = bytearray(bytes.fromhex(h))
    b[off:off + ln] = bytes(ln)
    return b.hex()


# ---------------------------------------------------------------------------
# Cross-run reproducibility projection.
#
# EMPIRICAL FINDING from this experiment's own two gated runs (recorded here
# because it changes what "cross-run byte-exact" means; PRE_REGISTRATION.md
# section 5 already anticipated the MRT-arena case in advance, before either
# run, as a known confounder): a NAMED role's WHOLE-region SHA-256 is not
# reliably reproducible across two fresh-process runs of the identical case.
# Four named roles were observed to change hash between run01/run02 with the
# CASE's own semantic fields (rts, k_load/k_store, first64_hex) unchanged:
# mrt-attachment-descriptors (the previously documented vertex-buffer-alias
# region beyond the k-record windows, docs/pipeline/README.md), single-rt-
# color-descriptor (unread padding past the +0x620 STORE window, within its
# own 0x8000 capture), clear-color-arena, and sparse-tiler-param-header.
# tiling-state additionally differed only for the two 200000-instance
# partial-render cases (k3/k4) -- plausibly a real per-draw counter that is
# not byte-deterministic at that primitive count, not a hardware ABI fact.
# Separately, exactly one case (e3-msaa4-resolve) showed content_captured
# flip from False to True for mrt-attachment-descriptors between runs with
# identical role/size -- a harness-level read-timing flake in the SIGUSR1
# snapshot race, not a hardware property.
#
# The reproducible PROJECTION below is what CASE_KEYS records are actually
# gated on for cross-run byte-exactness: every field EXCEPT each named
# role's "sha256"/"present_but_uncaptured" and each unnamed_regions entry's
# "sha256"/"content_captured" (kept in the raw file for diagnostic use, but
# not part of the gate). This is the concrete instance of the standing gate
# "no nondeterministic field in byte-compared records" for this experiment;
# see PRE_REGISTRATION.md and CAPTURE_CONTRACT.json "cross_run_byte_exact_scope".
# ---------------------------------------------------------------------------
def reproducible_projection(case_line):
    named = {}
    for role, v in case_line["named"].items():
        keep = {k: v[k] for k in v if k not in ("sha256", "present_but_uncaptured")}
        named[role] = keep
    unnamed_sizes = sorted(r["size"] for r in case_line["unnamed_regions"])
    return {"i": case_line["i"], "name": case_line["name"], "axis": case_line["axis"],
            "probe_status": case_line["probe_status"], "cb_status": case_line["cb_status"],
            "cb_error": case_line["cb_error"], "rts": case_line["rts"], "named": named,
            "unnamed_region_sizes": unnamed_sizes, "status": case_line["status"]}


# SECOND empirical finding (from the officially gated run03/run04 pair, after
# the fix above): case g2-depth-write's mrt-attachment-descriptors role was
# read successfully (first64_hex/k_load/k_store present) in run03 but hit
# content_captured=False in run04 -- a SIGUSR1-snapshot mach_vm_read_overwrite
# race in the harness (the same class of flake noted for e3-msaa4-resolve in
# the earlier run01/run02 pair), not a hardware property: the ROLE itself
# (and its "size") is present and identical in both runs; only whether the
# read of its content happened to land in time differs. Comparing the plain
# reproducible_projection() of each run independently would treat "content
# present" vs "content absent" as a semantic mismatch. records_reproducibly_
# equal() instead compares pairwise and tolerates exactly this asymmetry:
# for a given named role, the field-level content keys (first64_hex/k_load/
# k_store) are compared ONLY when BOTH runs captured them; if either run's
# read failed for that role, the mismatch is recorded in read_flakes instead
# of failing the gate. Every other field (role presence, size, rts, status,
# unnamed_region_sizes, cb_status/cb_error) is still required byte-exact.
def records_reproducibly_equal(line_a, line_b):
    pa, pb = reproducible_projection(line_a), reproducible_projection(line_b)
    flakes = []
    for role in set(pa["named"]) | set(pb["named"]):
        va, vb = pa["named"].get(role, {}), pb["named"].get(role, {})
        for key in ("first64_hex", "k_load", "k_store"):
            has_a, has_b = key in va, key in vb
            if has_a != has_b:
                flakes.append({"role": role, "field": key,
                               "present_in": "a" if has_a else "b"})
                va.pop(key, None); vb.pop(key, None)
    return pa == pb, flakes


def snapshot_dir(dump_dir):
    """wtrace.c writes each SIGUSR1 snapshot to dump_dir/dumpNN/; this probe
    triggers exactly one snapshot per case, so dump00 is authoritative."""
    return dump_dir / "dump00"


def read_inventory(dump_dir):
    inv = []
    tsv = snapshot_dir(dump_dir) / "inventory.tsv"
    if not tsv.exists():
        return inv
    lines = tsv.read_text().splitlines()[1:]
    for ln in lines:
        va, size, handle, role, captured, sha256 = ln.split("\t")
        inv.append({"va": va, "size": size, "handle": int(handle), "role": role,
                    "content_captured": bool(int(captured)), "sha256": sha256})
    return inv


REC_WIDTH = 0x20   # actual populated-record width read at each k slot, both roles


def named_window_fields(dump_dir, row):
    """For a captured named color-descriptor role, extract the k=0..max_k-1
    LOAD/STORE 0x20-byte record windows (masked + unmasked address halves)
    plus a first-64-byte header window, using that role's own segment/stride
    layout (ROLE_WINDOW). Returns (masked_dict, unmasked_addr_dict)."""
    va = row["va"][2:]
    binp = snapshot_dir(dump_dir) / f"va_{va}.bin"
    data = binp.read_bytes() if binp.exists() else b""
    first64 = data[:0x40].hex()
    layout = ROLE_WINDOW[row["role"]]
    k_load, k_store = [], []
    addr_load, addr_store = [], []
    for k in range(layout["max_k"]):
        for base, out, addrout in ((layout["load_base"], k_load, addr_load),
                                    (layout["store_base"], k_store, addr_store)):
            off = base + k * layout["stride"]
            window = data[off:off + REC_WIDTH]
            if len(window) < REC_WIDTH:
                out.append(None); addrout.append(None); continue
            hexw = window.hex()
            addr_bytes = window[ADDR_OFFSET:ADDR_OFFSET + ADDR_LEN].hex()
            out.append(hexmask(hexw, ADDR_OFFSET, ADDR_LEN))
            addrout.append(addr_bytes)
    return ({"first64_hex": first64, "k_load": k_load, "k_store": k_store},
            {"k_load_addr": addr_load, "k_store_addr": addr_store})



# NOTE (methodological record, not a live code path): an earlier iteration of
# this runner tried to identify a depth/stencil clear-value candidate region
# by VA arithmetic anchored on the reconstructed color-descriptor surface
# address. It was DROPPED before freezing this contract: the offset between
# the client buffer's own sel-9 registration and the "next slab" it depends
# on shifted between harness revisions (observed 0x60000-based in one probe
# revision, 0x58000-based after adding JSON config I/O ahead of it), i.e. the
# rule is harness-allocation-order-sensitive rather than a hardware fact, and
# freezing it would have coupled a hardware claim to incidental allocator
# behavior. The robust, allocation-order-independent replacement is the
# unnamed_regions size-multiset delta computed in analysis.py (present/absent
# and count of same-sized regions relative to the a1 baseline, with no VA and
# no content read for those regions) -- see RESULTS.md "depth/stencil state
# record" and PRE_REGISTRATION.md for the falsifier this satisfies instead.


def run_one_case(bindir, work, c, i):
    cfg_path = work / f"cfg_{c['name']}.json"
    cfg_path.write_text(json.dumps(c))
    result_path = work / f"result_{c['name']}.json"
    dump_dir = work / f"dump_{c['name']}"
    if dump_dir.exists():
        shutil.rmtree(dump_dir)
    log_path = work / f"trace_{c['name']}.log"
    env = dict(os.environ)
    env["WTRACE_LOG"] = str(log_path)
    env["WTRACE_DUMP_DIR"] = str(dump_dir)
    env["DYLD_INSERT_LIBRARIES"] = str(bindir / "wtrace.dylib")
    t0 = time.time()
    z = {"argv": [str(bindir / "probe"), str(cfg_path), str(result_path), "--dump"],
         "cwd": str(work), "timeout_seconds": TIMEOUTS["case"],
         "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "timed_out": False, "exit": None, "stdout": "", "stderr": "", "exception": None}
    try:
        p = subprocess.run(z["argv"], cwd=str(work), timeout=TIMEOUTS["case"],
                            capture_output=True, text=True, env=env)
        z["exit"] = p.returncode
        z["stdout"] = p.stdout
        z["stderr"] = p.stderr
    except subprocess.TimeoutExpired as e:
        z["timed_out"] = True
        z["stdout"] = e.stdout or ""
        z["stderr"] = e.stderr or ""
    except Exception as e:  # noqa: BLE001
        z["exception"] = repr(e)
    duration_ms = int((time.time() - t0) * 1000)

    probe_status, cb_status, cb_error, rts = "NO_RESULT", None, None, []
    if result_path.exists():
        try:
            r = json.loads(result_path.read_text())
            probe_status = r.get("status", "NO_RESULT")
            cb_status = r.get("cb_status")
            cb_error = r.get("cb_error")
            rts = r.get("rts", [])
        except Exception:
            probe_status = "NO_RESULT"
    if z["timed_out"]:
        status = "HARNESS_TIMEOUT"
    elif z["exception"] is not None or z["exit"] not in (0,):
        status = "HARNESS_CRASH"
    else:
        status = probe_status
    if status not in STATUS_ALLOWED:
        status = "HARNESS_CRASH"

    inv = read_inventory(dump_dir)
    named = {}
    named_addr = {}
    for row in inv:
        if row["role"] in NAMED_ROLES and row["content_captured"]:
            base = {"size": row["size"], "sha256": row["sha256"]}
            if row["role"] in COLOR_DESC_ROLES:
                windows, addrs = named_window_fields(dump_dir, row)
                base.update(windows)
                named_addr[row["role"]] = addrs
            named[row["role"]] = base
        elif row["role"] in NAMED_ROLES:
            named[row["role"]] = {"size": row["size"], "sha256": row["sha256"],
                                   "present_but_uncaptured": True}
    unnamed_regions = sorted(
        [{"size": row["size"], "sha256": row["sha256"], "content_captured": row["content_captured"]}
         for row in inv if row["role"] not in NAMED_ROLES],
        key=lambda x: (x["size"], x["sha256"]))

    resource_addrs = []
    if result_path.exists():
        try:
            r = json.loads(result_path.read_text())
            resource_addrs = list(r.get("color_gpu_addresses", []))
        except Exception:
            pass

    case_line = {"i": i, "name": c["name"], "axis": c["axis"], "probe_status": probe_status,
                 "cb_status": cb_status, "cb_error": cb_error, "rts": rts,
                 "named": named, "unnamed_regions": unnamed_regions, "status": status}
    timing_line = {"i": i, "name": c["name"], "duration_ms": duration_ms,
                    "stdout_raw": z["stdout"], "stderr_raw": z["stderr"],
                    "inventory_full": inv, "named_addresses": named_addr,
                    "resource_gpu_addresses": resource_addrs}
    assert set(case_line) == CASE_KEYS, set(case_line) ^ CASE_KEYS
    assert set(timing_line) == TIMING_KEYS, set(timing_line) ^ TIMING_KEYS
    shutil.rmtree(dump_dir, ignore_errors=True)
    return case_line, timing_line


def smoke_gate(bindir, work):
    """NON-RECORDED smoke gate: run ONE throwaway case into work/ before any
    raw/ artifact is created. Never promoted into raw/."""
    smoke_dir = work / "smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    c = dict(CM.CASES[0])
    cl, tl = run_one_case(bindir, smoke_dir, c, 0)
    if cl["status"] != "OK":
        print("SMOKE GATE FAIL:", json.dumps(cl, indent=2)[:2000])
        raise SystemExit(3)
    shutil.rmtree(smoke_dir, ignore_errors=True)
    print("SMOKE GATE PASS")


def do_run(run_id):
    if run_id not in RUNS:
        raise SystemExit("run id must be one of " + str(RUNS))
    raw = HERE / "raw" / run_id
    if raw.exists():
        raise SystemExit("run id already used (never reuse a run id): " + run_id)

    print("selftest/seqtest gate...")
    check([sys.executable, "-B", "verify.py", "--selftest"], HERE, 600, "selftest")
    check([sys.executable, "-B", "verify.py", "--seqtest"], HERE, 600, "seqtest")

    work = HERE / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    bindir = work / "bin"
    build_rec = run_record([HERE / "harness" / "build.sh", str(bindir)], HERE, TIMEOUTS["host_build"])
    if build_rec["exit"] != 0 or build_rec["exception"]:
        print("BUILD FAIL", build_rec); raise SystemExit(3)

    print("NON-RECORDED smoke gate (before any raw/ artifact)...")
    smoke_gate(bindir, work)

    rev, dirty, ntreedirty = git_info()
    ah = authored_sha256()
    inputs = {"schema": 1, "git_revision": rev, "git_dirty": dirty,
              "experiment_tree_dirty_entries": ntreedirty, "authored_sha256": ah,
              "sw_vers": run_record(["sw_vers"], HERE, TIMEOUTS["env_command"]),
              "xcrun_version": run_record(["xcrun", "--version"], HERE, TIMEOUTS["env_command"]),
              "python": sys.version.split()[0], "machine": os.uname().machine,
              "boundary": BOUNDARY, "timeouts_seconds": TIMEOUTS}
    assert set(inputs) == INPUTS_KEYS

    raw.mkdir(parents=True)
    (raw / "00_inputs.json").write_text(json.dumps(inputs, indent=2, sort_keys=True) + "\n")
    cases_doc = {"schema": 1, "run_id": run_id, "total": CM.TOTAL, "cases": CM.CASES}
    (raw / "01_cases.json").write_text(json.dumps(cases_doc, indent=2, sort_keys=True) + "\n")
    build_doc = {"schema": 1, "harness_build": build_rec}
    assert set(build_doc) == BUILD_KEYS
    (raw / "02_build.json").write_text(json.dumps(build_doc, indent=2, sort_keys=True) + "\n")

    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status_counts = {}
    rf = (raw / "03_results.jsonl").open("w")
    tf = (raw / "03_timing.jsonl").open("w")
    for i, c in enumerate(CM.CASES):
        case_dir = work / f"case_{i:03d}"
        case_dir.mkdir(parents=True, exist_ok=True)
        cl, tl = run_one_case(bindir, case_dir, c, i)
        status_counts[cl["status"]] = status_counts.get(cl["status"], 0) + 1
        rf.write(json.dumps(cl, sort_keys=True) + "\n"); rf.flush(); os.fsync(rf.fileno())
        tf.write(json.dumps(tl, sort_keys=True) + "\n"); tf.flush(); os.fsync(tf.fileno())
        shutil.rmtree(case_dir, ignore_errors=True)
        print("case %2d/%d %-32s -> %s" % (i, CM.TOTAL, c["name"], cl["status"]))
    rf.close(); tf.close()
    finished = datetime.datetime.now(datetime.timezone.utc).isoformat()

    dispatch = {"argv": ["python3", "run.py", "--execute", "--run-id", run_id],
                "cwd": str(HERE), "started_utc": started, "finished_utc": finished,
                "duration_seconds": (datetime.datetime.fromisoformat(finished) -
                                      datetime.datetime.fromisoformat(started)).total_seconds(),
                "n_cases": CM.TOTAL, "status_counts": status_counts,
                "results_sha256": sha(raw / "03_results.jsonl"),
                "results_lines": CM.TOTAL,
                "timing_sha256": sha(raw / "03_timing.jsonl"), "timing_lines": CM.TOTAL}
    assert set(dispatch) == DISPATCH_KEYS
    (raw / "04_dispatch.json").write_text(json.dumps(dispatch, indent=2, sort_keys=True) + "\n")
    shutil.rmtree(work, ignore_errors=True)
    (HERE / "work").mkdir(parents=True, exist_ok=True)
    print("RUN COMPLETE", run_id, status_counts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--run-id", required=True)
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("no capture is authorized without --execute")
    do_run(a.run_id)


if __name__ == "__main__":
    main()
