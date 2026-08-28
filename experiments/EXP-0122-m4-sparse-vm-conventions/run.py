#!/usr/bin/env python3
"""EXP-0122 frozen runner -- the single authoritative source for the case matrices,
raw-record schema, and capture procedure. verify.py, analysis.py and make_manifest.py all
import the constants from this module rather than restating them.

Usage:
  python3 -B run.py --build                       # build harness/probe from source
  python3 -B run.py --smoke                        # NON-RECORDED smoke check (work/, never raw/)
  python3 -B run.py --execute --run-id <id>         # full capture into raw/<id>/ (append+fflush)

Every case is dispatched as its own subprocess of harness/probe with a hard timeout (belt 1)
in addition to the harness's own in-process watchdogs (belt 2, exit 97 compile / 98 dispatch).
A case that fails to spawn, times out, or is killed is a RECORDED result, never silently
dropped, and is never retried in place.
"""
import argparse, datetime, hashlib, json, os, platform, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROBE_SRC = HERE / "harness" / "probe.m"
PROBE_BIN = HERE / "work" / "probe"
KERNEL_GUARD = HERE / "kernels" / "guard_access.metal"
KERNEL_SPARSE = HERE / "kernels" / "sparse_access.metal"

EXPERIMENT = "EXP-0122-m4-sparse-vm-conventions"
SCHEMA = 1

# ---------------------------------------------------------------------------
# Timeouts (seconds unless noted). Hard, non-negotiable per CODEX/CLAUDE.md safety rules.
# ---------------------------------------------------------------------------
TIMEOUTS = {
    "env_cmd": 10,
    "build": 60,
    "compile_watchdog_ms": 15000,   # in-process, exit 97
    "dispatch_watchdog_ms": 8000,   # in-process, exit 98
    "no_dispatch_proc": 30,         # outer subprocess timeout for caps/align/addrsurvey/maxlen/sparse_caps/sparse_miptail/timestamp
    "dispatch_proc": 20,            # outer subprocess timeout for any case that dispatches to the GPU
}

AUTH_CODE = ["harness/probe.m", "kernels/guard_access.metal", "kernels/sparse_access.metal",
             "run.py", "verify.py", "analysis.py", "make_manifest.py"]
AUTH_DOC = ["PRE_REGISTRATION.md", "README.md"]

# ---------------------------------------------------------------------------
# Case matrices (frozen). Each domain function returns a list of
# {"name":..., "params": {...}} dicts consumed uniformly by run_case().
# ---------------------------------------------------------------------------

def align_lengths():
    small = [1, 2, 3, 4, 7, 8, 15, 16, 17, 31, 32, 63, 64, 127, 128, 255, 256, 257,
             511, 512, 1023, 1024, 4095, 4096, 4097, 16383, 16384, 16385, 65535, 65536, 65537]
    return small


def align_cases():
    rows = []
    for length in align_lengths():
        for mode in ("shared", "private"):
            rows.append({"length": length, "mode": mode})
    return rows


def addrsurvey_seq():
    return [
        {"length": 64, "mode": "shared"}, {"length": 64, "mode": "shared"},
        {"length": 4096, "mode": "private"}, {"length": 4096, "mode": "private"},
        {"length": 1 << 20, "mode": "shared"}, {"length": 1 << 20, "mode": "private"},
    ]


# Guard offset ladder: (name, off_u64) pairs, frozen. Values chosen from documented
# exploratory probing (see PRE_REGISTRATION.md "exploratory design phase"): the
# neighbourhood of 16384 (one sparse tile / a plausible page granule) and the bisected
# wraparound boundary at 2**43 are load-bearing, not arbitrary round numbers.
def guard_offsets():
    M42, M43, M44, M45 = 1 << 42, 1 << 43, 1 << 44, 1 << 45
    U64 = 1 << 64
    positive = [
        ("ctrl32", 32), ("oob64", 64), ("last60", 60), ("far1088", 1088),
        ("p4096", 4096),
        ("p16128", 16384 - 256), ("p16380", 16384 - 4), ("p16384", 16384),
        ("p16388", 16384 + 4), ("p16640", 16384 + 256),
        ("p32768", 32768), ("p49152", 49152), ("p65536", 65536),
        ("p1048576", 1 << 20), ("p16777216", 1 << 24), ("p268435456", 1 << 28),
        ("p4294967296", 1 << 32), ("p68719476736", 1 << 36), ("p1099511627776", 1 << 40),
        ("p2199023255552", 1 << 41), ("p4398046511104", M42),
        ("p43_minus_4096", M43 - 4096), ("p43_minus_4", M43 - 4), ("p43_exact", M43),
        ("p43_plus_4", M43 + 4), ("p43_plus_60", M43 + 60), ("p43_plus_64", M43 + 64),
        ("p43x1p5", 3 * M42), ("p43x5_plus_4", 5 * M43 + 4), ("p44", M44),
        ("p45_plus_32", M45 + 32),
    ]
    negative = [
        ("neg32", U64 - 32), ("neg256", U64 - 256), ("neg257", U64 - 257),
        ("neg1mb", U64 - (1 << 20)), ("neg1gb", U64 - (1 << 30)),
        ("neg2p43", U64 - M43),
    ]
    return positive, negative


def guard_case_list():
    """Returns ordered list of {name, off, direction, op} for both load and store."""
    pos, neg = guard_offsets()
    out = []
    for direction, offsets in (("pos", pos), ("neg", neg)):
        for name, off in offsets:
            for op in ("guard_read", "guard_store"):
                out.append({"name": name, "off": off, "direction": direction, "op": op})
    return out


def sparse_caps_combos():
    combos = []
    for fmt in ("r8unorm", "rg8unorm", "rgba8unorm", "bgra8unorm", "rgba16float", "rgba32float", "r32float"):
        combos.append({"type": "2d", "format": fmt, "samples": 1})
    for samples in (2, 4):
        combos.append({"type": "2d", "format": "rgba8unorm", "samples": samples})
    combos.append({"type": "3d", "format": "rgba8unorm", "samples": 1})
    combos.append({"type": "2darray", "format": "rgba8unorm", "samples": 1})
    combos.append({"type": "cube", "format": "rgba8unorm", "samples": 1})
    return combos


def sparse_miptail_cases():
    return [
        {"width": 256, "height": 256, "mips": 9, "page": "16"},
        {"width": 1024, "height": 1024, "mips": 11, "page": "16"},
        {"width": 64, "height": 64, "mips": 7, "page": "16"},
        {"width": 63, "height": 63, "mips": 6, "page": "16"},
        {"width": 4096, "height": 4096, "mips": 13, "page": "16"},
        {"width": 128, "height": 128, "mips": 8, "page": "64"},
        {"width": 128, "height": 128, "mips": 8, "page": "256"},
        {"width": 32, "height": 32, "mips": 6, "page": "256"},
        {"width": 200, "height": 150, "mips": 8, "page": "16"},
    ]


def sparse_unmapped_read_cases():
    return [
        {"name": "single_tile_page16", "width": 64, "height": 64, "page": "16",
         "coords": [[0, 0], [10, 10], [63, 63]]},
        {"name": "multi_tile_page16", "width": 256, "height": 256, "page": "16",
         "coords": [[0, 0], [65, 65], [130, 130], [200, 30], [255, 255]]},
        {"name": "single_tile_page64", "width": 128, "height": 128, "page": "64",
         "coords": [[0, 0], [64, 64], [127, 127]]},
        {"name": "tile_larger_than_tex_page256", "width": 128, "height": 128, "page": "256",
         "coords": [[0, 0], [64, 64], [127, 127]]},
    ]


def sparse_partial_map_cases():
    return [
        {"name": "single_tile", "width": 64, "height": 64, "tile_w": 64, "tile_h": 64, "page": "16",
         "mapped_tiles": [[0, 0]], "write_coord": [5, 5], "pattern_rgba": [0.25, 0.5, 0.75, 1.0],
         "read_coords": [[5, 5], [40, 40]]},
        {"name": "one_of_four_tiles", "width": 128, "height": 128, "tile_w": 64, "tile_h": 64, "page": "16",
         "mapped_tiles": [[0, 0]], "write_coord": [10, 10], "pattern_rgba": [0.25, 0.5, 0.75, 1.0],
         "read_coords": [[10, 10], [70, 10], [10, 70], [100, 100]]},
    ]


def sparse_remap_cases():
    return [
        {"name": "single_tile_remap", "width": 64, "height": 64, "tile_w": 64, "tile_h": 64, "page": "16",
         "tile": [0, 0], "coord": [5, 5], "pattern_rgba": [0.25, 0.5, 0.75, 1.0]},
    ]


def timestamp_sleeps():
    return [1, 5, 10, 50, 100, 500]


# ---------------------------------------------------------------------------
# Environment / provenance recording
# ---------------------------------------------------------------------------

def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_cmd(argv, timeout, cwd=None):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        r = subprocess.run(argv, cwd=str(cwd) if cwd else None, capture_output=True,
                            text=True, timeout=timeout)
        return {"argv": [str(x) for x in argv], "cwd": str(cwd) if cwd else str(HERE),
                "timeout_seconds": timeout, "started_utc": started, "timed_out": False,
                "exit": r.returncode, "exception": None, "stdout": r.stdout, "stderr": r.stderr}
    except subprocess.TimeoutExpired as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd) if cwd else str(HERE),
                "timeout_seconds": timeout, "started_utc": started, "timed_out": True,
                "exit": None, "exception": None, "stdout": e.stdout or "", "stderr": e.stderr or ""}
    except Exception as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd) if cwd else str(HERE),
                "timeout_seconds": timeout, "started_utc": started, "timed_out": False,
                "exit": None, "exception": repr(e), "stdout": "", "stderr": ""}


def git_info():
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=REPO, capture_output=True, text=True).stdout
    dirty = len(status.strip()) > 0
    tree_dirty = [l for l in status.splitlines() if "EXP-0122-m4-sparse-vm-conventions" in l]
    return rev, dirty, tree_dirty


def authored_hashes():
    out = {}
    for rel in AUTH_CODE + AUTH_DOC:
        p = HERE / rel
        if p.exists():
            out[rel] = sha256_file(p)
    return out


def env_record():
    sw_vers = run_cmd(["sw_vers"], TIMEOUTS["env_cmd"])
    xcrun_v = run_cmd(["xcrun", "--version"], TIMEOUTS["env_cmd"])
    rev, dirty, tree_dirty = git_info()
    return {
        "schema": SCHEMA, "git_revision": rev, "git_dirty": dirty,
        "experiment_tree_dirty_entries": tree_dirty,
        "authored_sha256": authored_hashes(),
        "sw_vers": sw_vers["stdout"], "xcrun_version": xcrun_v["stdout"],
        "python": sys.version, "machine": platform.machine(),
        "timeouts_seconds": TIMEOUTS,
    }


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build():
    PROBE_BIN.parent.mkdir(parents=True, exist_ok=True)
    argv = ["xcrun", "clang", "-fobjc-arc", "-O1", "-framework", "Metal", "-framework", "Foundation",
            "-o", str(PROBE_BIN), str(PROBE_SRC)]
    rec = run_cmd(argv, TIMEOUTS["build"])
    ok = (not rec["timed_out"]) and rec["exit"] == 0 and PROBE_BIN.exists()
    return ok, rec


# ---------------------------------------------------------------------------
# Case execution: one process per case, hard outer timeout, JSON-line stdout.
# ---------------------------------------------------------------------------

def exec_case(case_name, params, timeout, out_dir=None):
    argv = [str(PROBE_BIN), case_name, json.dumps(params)]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.time()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        dt = time.time() - t0
        status = "proc_fail"
        rec = None
        if r.returncode == 0:
            try:
                lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
                rec = json.loads(lines[-1]) if lines else None
                status = "ok" if rec is not None else "proc_fail"
            except Exception:
                status = "proc_fail"
        elif r.returncode == 97:
            status = "watchdog_compile"
        elif r.returncode == 98:
            status = "watchdog_dispatch"
        else:
            status = "proc_fail"
        return {
            "status": status, "exit": r.returncode, "timed_out": False, "duration_s": dt,
            "record": rec, "stderr_tail": r.stderr[-2000:] if r.stderr else "",
            "started_utc": started,
        }
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        return {"status": "proc_timeout", "exit": None, "timed_out": True, "duration_s": dt,
                "record": None, "stderr_tail": "", "started_utc": started}
    except Exception as e:
        dt = time.time() - t0
        return {"status": "proc_exception", "exit": None, "timed_out": False, "duration_s": dt,
                "record": None, "stderr_tail": repr(e), "started_utc": started}


class Sink:
    """Append-only JSONL writer: one open handle per file, fflush after every record."""
    def __init__(self, path):
        self.path = path
        self.fh = open(path, "a", buffering=1)

    def write(self, obj):
        self.fh.write(json.dumps(obj, sort_keys=True) + "\n")
        self.fh.flush()
        os.fsync(self.fh.fileno())

    def close(self):
        self.fh.close()


def do_capture(run_id, execute=False, smoke_only=False):
    raw_dir = HERE / "raw" / run_id
    work_dir = HERE / "work" / run_id
    work_dir.mkdir(parents=True, exist_ok=True)

    ok, buildrec = build()
    if not ok:
        stop = {"stage": "build", "record": buildrec}
        (work_dir / "STOP.json").write_text(json.dumps(stop, indent=2))
        print("BUILD FAILED, see", work_dir / "STOP.json")
        return 3

    # NON-RECORDED smoke gate: one scratch guard case + one scratch sparse_caps case into
    # work/, never promoted into raw/.
    smoke_guard = exec_case("guard_read", {"name": "smoke", "base_len": 64, "mode": "shared",
                                            "off_dec": "32", "compile_watchdog_ms": TIMEOUTS["compile_watchdog_ms"],
                                            "dispatch_watchdog_ms": TIMEOUTS["dispatch_watchdog_ms"],
                                            "kernel_path": str(KERNEL_GUARD)},
                             TIMEOUTS["dispatch_proc"])
    smoke_caps = exec_case("caps", {}, TIMEOUTS["no_dispatch_proc"])
    smoke_ok = (smoke_guard["status"] == "ok" and smoke_guard["record"] is not None
                and smoke_guard["record"]["gated"]["status"] == "ok"
                and smoke_caps["status"] == "ok" and smoke_caps["record"] is not None)
    (work_dir / "smoke.json").write_text(json.dumps(
        {"smoke_guard": smoke_guard, "smoke_caps": smoke_caps, "smoke_ok": smoke_ok}, indent=2))
    if not smoke_ok:
        stop = {"stage": "smoke", "smoke_guard": smoke_guard, "smoke_caps": smoke_caps}
        (work_dir / "STOP.json").write_text(json.dumps(stop, indent=2))
        print("SMOKE GATE FAILED, see", work_dir / "STOP.json")
        return 3
    print("smoke gate OK")
    if smoke_only:
        return 0
    if not execute:
        print("dry run only (pass --execute to capture); smoke gate passed")
        return 0

    if raw_dir.exists():
        print("REFUSING: raw dir already exists (never reuse a run id):", raw_dir)
        return 4
    raw_dir.mkdir(parents=True)

    inputs = env_record()
    (raw_dir / "00_inputs.json").write_text(json.dumps(inputs, indent=2, sort_keys=True))
    (raw_dir / "00_build.json").write_text(json.dumps(buildrec, indent=2))

    sinks = {}
    def sink(name):
        if name not in sinks:
            sinks[name] = Sink(raw_dir / (name + ".jsonl"))
        return sinks[name]

    consecutive_fail = 0
    MAX_CONSEC = 3

    def note(domain, name, params, exec_result):
        nonlocal consecutive_fail
        row = {"domain": domain, "name": name, "params": params,
               "exec_status": exec_result["status"], "exit": exec_result["exit"],
               "duration_s": exec_result["duration_s"], "started_utc": exec_result["started_utc"],
               "record": exec_result["record"], "stderr_tail": exec_result["stderr_tail"]}
        sink(domain).write(row)
        if exec_result["status"] in ("proc_fail", "proc_exception"):
            consecutive_fail += 1
        else:
            consecutive_fail = 0
        return consecutive_fail < MAX_CONSEC

    # --- VM domain: align, addrsurvey, maxlen_boundary, caps ---
    r = exec_case("caps", {}, TIMEOUTS["no_dispatch_proc"])
    note("caps", "caps", {}, r)

    r = exec_case("align", {"cases": align_cases()}, TIMEOUTS["no_dispatch_proc"])
    note("align", "align_sweep", {"n": len(align_cases())}, r)

    r = exec_case("addrsurvey", {"seq": addrsurvey_seq(), "passes": 3}, TIMEOUTS["no_dispatch_proc"])
    note("addrsurvey", "addrsurvey", {"n": len(addrsurvey_seq()), "passes": 3}, r)

    r = exec_case("maxlen_boundary", {}, TIMEOUTS["no_dispatch_proc"])
    note("maxlen_boundary", "maxlen_boundary", {}, r)

    # --- Guard/zero-page domain ---
    abort_dir = {"pos": False, "neg": False}
    for c in guard_case_list():
        d = c["direction"]
        if abort_dir[d]:
            note("guard", c["op"] + "_" + c["name"], {"skipped_after_hang_in_direction": d}, {
                "status": "skipped_stop_on_hang", "exit": None, "timed_out": False,
                "duration_s": 0.0, "record": None, "stderr_tail": "", "started_utc":
                datetime.datetime.now(datetime.timezone.utc).isoformat()})
            continue
        params = {"name": c["name"], "base_len": 64, "mode": "shared", "off_dec": str(c["off"]),
                  "compile_watchdog_ms": TIMEOUTS["compile_watchdog_ms"],
                  "dispatch_watchdog_ms": TIMEOUTS["dispatch_watchdog_ms"], "kernel_path": str(KERNEL_GUARD)}
        r = exec_case(c["op"], params, TIMEOUTS["dispatch_proc"])
        ok_ = note("guard", c["op"] + "_" + c["name"], params, r)
        if r["status"] in ("watchdog_dispatch", "watchdog_compile", "proc_timeout"):
            abort_dir[d] = True
        if not ok_:
            print("STOP: 3 consecutive infra failures during guard domain")
            for s in sinks.values(): s.close()
            (raw_dir / "STOP.json").write_text(json.dumps({"stage": "guard", "reason": "consecutive_fail"}))
            return 5

    # --- Sparse domain ---
    r = exec_case("sparse_caps", {"combos": sparse_caps_combos()}, TIMEOUTS["no_dispatch_proc"])
    note("sparse_caps", "sparse_caps", {"n": len(sparse_caps_combos())}, r)

    r = exec_case("sparse_miptail", {"cases": sparse_miptail_cases()}, TIMEOUTS["no_dispatch_proc"])
    note("sparse_miptail", "sparse_miptail", {"n": len(sparse_miptail_cases())}, r)

    for c in sparse_unmapped_read_cases():
        params = dict(c); params.pop("name")
        params["compile_watchdog_ms"] = TIMEOUTS["compile_watchdog_ms"]
        params["dispatch_watchdog_ms"] = TIMEOUTS["dispatch_watchdog_ms"]
        params["kernel_path"] = str(KERNEL_SPARSE)
        r = exec_case("sparse_unmapped_read", params, TIMEOUTS["dispatch_proc"])
        note("sparse_unmapped_read", c["name"], params, r)

    for c in sparse_partial_map_cases():
        params = dict(c); params.pop("name")
        params["compile_watchdog_ms"] = TIMEOUTS["compile_watchdog_ms"]
        params["dispatch_watchdog_ms"] = TIMEOUTS["dispatch_watchdog_ms"]
        params["kernel_path"] = str(KERNEL_SPARSE)
        r = exec_case("sparse_partial_map", params, TIMEOUTS["dispatch_proc"])
        note("sparse_partial_map", c["name"], params, r)

    for c in sparse_remap_cases():
        params = dict(c); params.pop("name")
        params["compile_watchdog_ms"] = TIMEOUTS["compile_watchdog_ms"]
        params["dispatch_watchdog_ms"] = TIMEOUTS["dispatch_watchdog_ms"]
        params["kernel_path"] = str(KERNEL_SPARSE)
        r = exec_case("sparse_remap", params, TIMEOUTS["dispatch_proc"])
        note("sparse_remap", c["name"], params, r)

    # --- Timestamp domain ---
    r = exec_case("timestamp_ladder", {"sleeps_ms": timestamp_sleeps()}, TIMEOUTS["no_dispatch_proc"] + 5)
    note("timestamp_ladder", "timestamp_ladder", {"sleeps_ms": timestamp_sleeps()}, r)

    for s in sinks.values():
        s.close()

    envelope = {
        "schema": SCHEMA, "run_id": run_id,
        "domains": sorted(sinks.keys()),
        "guard_case_count": len(guard_case_list()),
        "closed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    (raw_dir / "99_envelope.json").write_text(json.dumps(envelope, indent=2, sort_keys=True))
    print("capture complete:", raw_dir)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--run-id")
    args = ap.parse_args()

    if args.build:
        ok, rec = build()
        print("build ok" if ok else "build FAILED")
        print(rec["stderr"][-2000:] if rec.get("stderr") else "")
        return 0 if ok else 1

    if args.smoke:
        return do_capture("smoke-only", execute=False, smoke_only=True)

    if args.execute:
        if not args.run_id:
            print("--execute requires --run-id")
            return 2
        return do_capture(args.run_id, execute=True)

    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
