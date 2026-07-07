#!/usr/bin/env python3
# opsweep.py -- EXP-0005 float-ALU op-select sweep (runs ON THE DEVICE).
#
# Sweeps a byte-field of the canonical 2-source compute kernel
#   out[gid] = a[gid] + b[gid]     (_agc.main float ALU instruction)
# through all 256 values, dispatching each with several known (a,b) probe
# vectors on the real A18 Pro GPU, and identifies the resulting operation by
# matching outputs against a candidate library. Every probe is classified
# valid-op / accepted-unknown / fault and logged to raw/opmap.txt.
#
# CLEAN-ROOM: the only bytes spliced/executed are the compiled form of OUR OWN
# MSL (add.metal). Uses our own persistent runner (agxrun_persist) via
# persistrun.py. No Apple binary is disassembled or introspected.
#
# Usage (on device, in ~/cleanroom_work/exp0005):
#   python3 opsweep.py --offset 0x22 [--rebuild] [--timeout 6]

import argparse
import os
import struct
import subprocess
import sys
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---- probe vectors: chosen so candidate ops give distinct outputs ----------
A = [2.0, 3.0, 8.0, 7.0]
B = [4.0, 6.0, 2.0, 5.0]
GRID = len(A)


def candidates(a, b):
    """name -> expected output list for each candidate 2-source float op."""
    out = {
        "fadd":  [x + y for x, y in zip(a, b)],
        "fsub":  [x - y for x, y in zip(a, b)],
        "frsub": [y - x for x, y in zip(a, b)],
        "fmul":  [x * y for x, y in zip(a, b)],
        "fdiv":  [x / y for x, y in zip(a, b)],
        "frdiv": [y / x for x, y in zip(a, b)],
        "fmax":  [max(x, y) for x, y in zip(a, b)],
        "fmin":  [min(x, y) for x, y in zip(a, b)],
        "fmov_a": list(a),
        "fmov_b": list(b),
    }
    return out


def floats_from(raw):
    return [struct.unpack_from("<f", raw, i)[0] for i in range(0, len(raw) - 3, 4)]


def approx(xs, ys, tol=1e-3):
    if len(xs) != len(ys):
        return False
    for x, y in zip(xs, ys):
        if x != x or y != y:      # NaN
            if (x != x) != (y != y):
                return False
            continue
        if abs(x - y) > tol * max(1.0, abs(y)):
            return False
    return True


def classify(vals):
    cand = candidates(A, B)
    for name, exp in cand.items():
        if approx(vals, exp):
            return name
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offset", default="0x22", help="byte offset within _agc.main to sweep")
    ap.add_argument("--source", default="kernels/add.metal")
    ap.add_argument("--function", default="k")
    ap.add_argument("--no-fast-math", action="store_true", default=True)
    ap.add_argument("--shdump", default="./shdump")
    ap.add_argument("--agxrun-persist", default="./agxrun_persist")
    ap.add_argument("--agxparse", default="./agxparse.py")
    ap.add_argument("--persistrun", default="./persistrun.py")
    ap.add_argument("--timeout", type=float, default=6.0)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--out", default="raw/opmap.txt")
    ap.add_argument("--workdir", default="sweepwork")
    args = ap.parse_args()

    offset = int(args.offset, 0)
    os.makedirs(args.workdir, exist_ok=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    agxparse = load_mod("agxparse", args.agxparse)
    PersistRunner = load_mod("persistrun", args.persistrun).PersistRunner

    # 1. Compile base archive from OUR source.
    base = os.path.join(args.workdir, "base.bin")
    if args.rebuild or not os.path.exists(base):
        cmd = [args.shdump, "-o", base, "-f", args.function]
        if args.no_fast_math:
            cmd.append("--no-fast-math")
        cmd.append(args.source)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(base):
            print("shdump failed:", r.stderr); sys.exit(1)

    with open(base, "rb") as f:
        basebuf = f.read()
    loc = agxparse.locate_region(basebuf, "_agc.main")
    if loc is None:
        print("could not locate _agc.main"); sys.exit(1)
    region_off, region_len = loc
    _, pieces = agxparse.extract_agx(basebuf)
    main_bytes = pieces["_agc.main"]
    orig_op = main_bytes[offset]
    print(f"# _agc.main len={region_len} region_off={region_off} "
          f"op-byte@{offset:#04x}=orig {orig_op:#04x}")

    # 2. Write input files once.
    in0 = os.path.join(args.workdir, "in0.bin")
    in1 = os.path.join(args.workdir, "in1.bin")
    with open(in0, "wb") as f:
        f.write(b"".join(struct.pack("<f", x) for x in A))
    with open(in1, "wb") as f:
        f.write(b"".join(struct.pack("<f", x) for x in B))

    # 3. Persistent runner.
    runner = PersistRunner(source=args.source, function=args.function,
                           fast_math=not args.no_fast_math,
                           agxrun_persist=args.agxrun_persist)
    print(f"# runner READY on {runner.device}")

    log = open(args.out, "w")
    log.write("# EXP-0005 float-ALU op-select sweep\n")
    log.write(f"# canonical kernel: out[gid]=a[gid]+b[gid]; sweep _agc.main byte @ {offset:#04x}\n")
    log.write(f"# inputs A={A} B={B} grid={GRID}\n")
    log.write("# columns: opbyte  status  op-identified  outputs\n")

    summary = {}
    for val in range(256):
        spliced = bytearray(basebuf)
        spliced[region_off + offset] = val
        arch = os.path.join(args.workdir, "sp.bin")
        with open(arch, "wb") as f:
            f.write(spliced)
        resp = runner.request(archive=arch, grid=GRID, tg=GRID,
                              ins={0: in0, 1: in1}, outs={2: GRID * 4},
                              timeout=args.timeout)
        if resp["status"] == "OK":
            vals = floats_from(resp["outs"].get(2, b""))
            op = classify(vals)
            tag = op if op else "ACCEPTED-UNKNOWN"
            vstr = " ".join(f"{x:g}" for x in vals)
            line = f"{val:#04x}  OK    {tag:16s}  [{vstr}]"
        else:
            tag = "FAULT:" + resp["status"]
            line = f"{val:#04x}  {resp['status']:12s}  {resp.get('error','')}"
        summary[tag] = summary.get(tag, 0) + 1
        log.write(line + "\n")
        log.flush()
        if val % 16 == 0 or resp["status"] != "OK" or (resp["status"] == "OK" and classify(floats_from(resp["outs"].get(2, b""))) not in (None,)):
            print(line)

    runner.close()
    log.write("\n# SUMMARY\n")
    for k in sorted(summary):
        log.write(f"#   {k}: {summary[k]}\n")
    log.close()
    print("\n# SUMMARY")
    for k in sorted(summary):
        print(f"#   {k}: {summary[k]}")
    print(f"# wrote {args.out}")


if __name__ == "__main__":
    main()
