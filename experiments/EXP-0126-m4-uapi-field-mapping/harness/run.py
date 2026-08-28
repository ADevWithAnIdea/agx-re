#!/usr/bin/env python3
"""EXP-0126 runner.

Builds the authored harness binaries (+ the unmodified tools/iotrace interposer) into
work/bin/, runs a NON-RECORDED smoke case first (work/<run_id>_smoke.json; if it fails,
no raw/ directory is created at all -- standing gate (c)), then executes the full frozen
case matrix (casematrix.py) one case per fresh process, appending one JSON record per
case to raw/<run_id>/records.jsonl immediately (append+fflush; never buffered in memory
for a bulk write at the end).

For 'sampos' cases this drives tools/iotrace/iotrace.c (read-only, unmodified, built
from source into work/bin/ -- never edited) as a DYLD interposer around
harness/sampos126.m, and parses ONLY the one pre-classified BO (the documented
sample-position array at 0x100000e8000 for 4x samples / 0x100000e0000 for 2x, offset
+0x40) out of the resulting per-case dump directory. No other BO in that directory is
opened, scanned, or referenced. The retained hex snapshot for that one BO is copied into
raw/<run_id>/hex/<case_id>.hex as immutable evidence; the rest of the transient per-case
dump directory (dozens of unclassified BOs, not evidence for this experiment) is removed.

Usage:
  python3 run.py --run m4_<date>_run01 --out raw/m4_<date>_run01
  python3 run.py --list
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import casematrix as CM
import hexparse as HP

REPO = EXP.parent.parent
IOTRACE_SRC = REPO / "tools" / "iotrace" / "iotrace.c"
BIN = EXP / "work" / "bin"
CASE_TIMEOUT_S = 30
SMOKE_TIMEOUT_S = 20


def sh(cmd, timeout, env=None):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(EXP), env=env)
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return -9, (e.stdout or ""), (e.stderr or "") + "\nTIMEOUT", time.time() - t0


def build():
    BIN.mkdir(parents=True, exist_ok=True)
    steps = [
        (["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
          "-o", str(BIN / "sampos126"), str(HERE / "sampos126.m")]),
        (["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
          "-o", str(BIN / "sampcount"), str(HERE / "sampcount.m")]),
        (["clang", "-dynamiclib", "-o", str(BIN / "iotrace.dylib"), str(IOTRACE_SRC),
          "-framework", "IOKit", "-framework", "CoreFoundation"]),
    ]
    for cmd in steps:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            print("BUILD FAIL:", " ".join(cmd), file=sys.stderr)
            print(p.stderr, file=sys.stderr)
            sys.exit(1)
    print("build ok")


def parse_sampos_stdout(stdout):
    d = {"device": None, "case": None, "status": None, "posapply": None,
         "va_vtxbuf": None, "va_resbuf": None, "samples": None, "p0x": None, "p0y": None}
    for line in stdout.splitlines():
        if line.startswith("DEVICE "):
            d["device"] = line[len("DEVICE "):].strip()
        elif line.startswith("CASE "):
            d["case"] = line[len("CASE "):].strip()
        elif line.startswith("CONFIG "):
            # CONFIG samples=4 p0=(0.375000,0.125000)
            parts = line.split()
            for tok in parts[1:]:
                if tok.startswith("samples="):
                    d["samples"] = int(tok.split("=", 1)[1])
                elif tok.startswith("p0=("):
                    xy = tok[len("p0=("):-1].split(",")
                    d["p0x"] = float(xy[0]); d["p0y"] = float(xy[1])
        elif line.startswith("POSAPPLY "):
            d["posapply"] = line[len("POSAPPLY "):].strip()
        elif line.startswith("SUBMIT "):
            for tok in line.split():
                if tok.startswith("status="):
                    d["status"] = int(tok.split("=", 1)[1])
        elif line.startswith("VA vtxBuf"):
            d["va_vtxbuf"] = line.split("=", 1)[1].strip()
        elif line.startswith("VA resBuf"):
            d["va_resbuf"] = line.split("=", 1)[1].strip()
    return d


def parse_sampcount_stdout(stdout):
    d = {"device": None, "count": None, "capquery": None, "texture": None,
         "pipeline": None, "draw": None, "pixel": None}
    for line in stdout.splitlines():
        if line.startswith("DEVICE "):
            d["device"] = line[len("DEVICE "):].strip()
        elif line.startswith("CONFIG "):
            d["count"] = int(line.split("count=")[1].strip())
        elif line.startswith("CAPQUERY "):
            d["capquery"] = line[len("CAPQUERY "):].strip()
        elif line.startswith("TEXTURE "):
            d["texture"] = line[len("TEXTURE "):].strip()
        elif line.startswith("PIPELINE "):
            d["pipeline"] = line[len("PIPELINE "):].strip()
        elif line.startswith("DRAW "):
            d["draw"] = line[len("DRAW "):].strip()
        elif line.startswith("PIXEL "):
            d["pixel"] = line[len("PIXEL "):].strip()
    return d


def run_sampos_case(case, out_hex_dir, keep_hex_as):
    dumpdir = EXP / "work" / "dumps" / case["case_id"]
    if dumpdir.exists():
        shutil.rmtree(dumpdir)
    dumpdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["IOTRACE_LOG"] = str(dumpdir / "trace.log")
    env["IOTRACE_DUMP_DIR"] = str(dumpdir)
    env["DYLD_INSERT_LIBRARIES"] = str(BIN / "iotrace.dylib")
    args = ["--samples", str(case["params"]["samples"]),
            "--p0x", repr(case["params"]["p0x"]),
            "--p0y", repr(case["params"]["p0y"]),
            "--case", case["case_id"]]
    rc, out, err, wall = sh([str(BIN / "sampos126")] + args, CASE_TIMEOUT_S, env=env)
    parsed = parse_sampos_stdout(out)

    n = case["params"]["samples"]
    va = CM.SAMPOS_VA_4X if n == 4 else CM.SAMPOS_VA_2X
    va_hex = va[2:]  # strip 0x
    hexfile = None
    for f in dumpdir.iterdir():
        if f.name.startswith(f"bo_sigusr1_h0_va{va_hex}_"):
            hexfile = f
            break

    observed = {"x0": None, "y0": None, "va_found": va if hexfile else None}
    if parsed["posapply"] == "ok" and hexfile is not None:
        x0, _ = HP.read_f32(str(hexfile), CM.SAMPOS_OFFSET_X0)
        y0, _ = HP.read_f32(str(hexfile), CM.SAMPOS_OFFSET_Y0)
        observed["x0"] = x0
        observed["y0"] = y0

    hex_path_rel = None
    if hexfile is not None:
        out_hex_dir.mkdir(parents=True, exist_ok=True)
        dest = out_hex_dir / f"{keep_hex_as}.hex"
        shutil.copyfile(hexfile, dest)
        hex_path_rel = str(dest.relative_to(EXP))

    if rc == 0 and parsed["status"] == 4:
        status = "OK"
    elif rc < 0:
        status = f"ABORT_sig{-rc}"
    else:
        status = f"FAIL_rc{rc}"
    if parsed["posapply"] not in (None, "ok"):
        status = "REJECTED"

    shutil.rmtree(dumpdir, ignore_errors=True)

    record = {
        "case_id": case["case_id"],
        "family": case["family"],
        "kind": case["kind"],
        "params": case["params"],
        "status": status,
        "observed": {
            "posapply": parsed["posapply"],
            "submit_status": parsed["status"],
            "x0": observed["x0"],
            "y0": observed["y0"],
        },
        "va_vtxbuf": parsed["va_vtxbuf"],
        "va_resbuf": parsed["va_resbuf"],
        "hex_path": hex_path_rel,
        "raw_stdout": out,
        "raw_stderr": err,
        "wall_ms": round(wall * 1000, 1),
        "rc": rc,
    }
    return record


def run_sampcount_case(case):
    args = ["--count", str(case["params"]["count"])]
    rc, out, err, wall = sh([str(BIN / "sampcount")] + args, CASE_TIMEOUT_S)
    parsed = parse_sampcount_stdout(out)
    if rc == 0:
        status = "OK"
    elif rc < 0:
        status = f"ABORT_sig{-rc}"
    else:
        status = f"FAIL_rc{rc}"
    record = {
        "case_id": case["case_id"],
        "family": case["family"],
        "kind": case["kind"],
        "params": case["params"],
        "status": status,
        "observed": {
            "capquery": parsed["capquery"],
            "texture": parsed["texture"],
            "pipeline": parsed["pipeline"],
            "draw": parsed["draw"],
            "pixel": parsed["pixel"],
        },
        "va_vtxbuf": None,
        "va_resbuf": None,
        "hex_path": None,
        "raw_stdout": out,
        "raw_stderr": err,
        "wall_ms": round(wall * 1000, 1),
        "rc": rc,
    }
    return record


def run_one(case, out_hex_dir):
    if case["kind"] == "sampos":
        return run_sampos_case(case, out_hex_dir, case["case_id"])
    elif case["kind"] == "sampcount":
        return run_sampcount_case(case)
    raise ValueError(case["kind"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=False)
    ap.add_argument("--out", required=False)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    build()

    if args.list:
        for c in CM.all_cases():
            print(c["case_id"], c["family"], c["params"])
        return

    if not args.run or not args.out:
        print("need --run and --out", file=sys.stderr)
        sys.exit(2)

    work = EXP / "work"
    work.mkdir(exist_ok=True)

    # --- gate (c): non-recorded smoke case BEFORE any raw/ directory is created ---
    smoke = CM.smoke_case()
    smoke_hex_dir = work / f"{args.run}_smoke_hex"
    rec = run_one(smoke, smoke_hex_dir)
    smoke_path = work / f"{args.run}_smoke.json"
    with open(smoke_path, "w") as f:
        json.dump(rec, f, indent=2)
        f.flush()
    shutil.rmtree(smoke_hex_dir, ignore_errors=True)
    if rec["status"] != "OK":
        print(f"SMOKE FAILED: {rec}", file=sys.stderr)
        sys.exit(1)
    print(f"smoke ok: {smoke_path}")

    out_dir = EXP / args.out
    if out_dir.exists():
        print(f"REFUSING to reuse existing run dir {out_dir}", file=sys.stderr)
        sys.exit(1)
    out_dir.mkdir(parents=True)
    hex_dir = out_dir / "hex"
    records_path = out_dir / "records.jsonl"

    with open(records_path, "a") as rf:
        for case in CM.all_cases():
            rec = run_one(case, hex_dir)
            rf.write(json.dumps(rec, sort_keys=True) + "\n")
            rf.flush()
            os.fsync(rf.fileno())
            print(case["case_id"], rec["status"])

    manifest = {
        "run_id": args.run,
        "n_cases": len(CM.all_cases()),
        "smoke": str(smoke_path.relative_to(EXP)),
    }
    with open(out_dir / "run_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print("done:", out_dir)


if __name__ == "__main__":
    main()
