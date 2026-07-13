#!/usr/bin/env python3
# EXP-M5-20 device-side driver: build 8x8 matrix buffers, drive agxtest.py (splice
# optional), print the result matrix diagonal + full grid. CLEAN-ROOM: our own MSL
# only. Runs ON the M5 device (needs Metal via agxrun).
import subprocess, sys, struct, argparse, os

HERE = os.path.dirname(os.path.abspath(__file__))
AGXTEST = os.path.join(HERE, "agxtest.py")
TOOLS = os.path.expanduser("~/cleanroom_work/tools")

def ident(k):
    m = [0.0]*64
    for i in range(8):
        m[i*8+i] = float(k)
    return m

def diag(vals):
    m = [0.0]*64
    for i in range(8):
        m[i*8+i] = float(vals[i])
    return m

def full(seq):
    return [float(x) for x in seq]

def parse_mat(spec):
    # sI:k | diag:v0,..,v7 | seq:start,step | zero
    kind, _, rest = spec.partition(":")
    if kind == "sI":
        return ident(float(rest))
    if kind == "diag":
        return diag([float(x) for x in rest.split(",")])
    if kind == "seq":
        start, step = (float(x) for x in rest.split(","))
        return [start + step*i for i in range(64)]
    if kind == "zero":
        return [0.0]*64
    raise SystemExit("bad mat spec " + spec)

def csv(m):
    return ",".join(repr(x) for x in m)

def run(func, mats, out_idx, out_n, splices, grid=32, tg=32, timeout=15):
    cmd = ["python3", AGXTEST, "--source", os.path.join(HERE, "mac_probe.metal"),
           "--function", func, "--grid", str(grid), "--tg", str(tg),
           "--shdump", os.path.join(TOOLS, "shdump", "shdump"),
           "--agxrun", os.path.join(HERE, "agxrun"),
           "--agxparse", os.path.join(TOOLS, "shdump", "agxparse.py"),
           "--run-timeout", str(timeout), "--workdir", HERE]
    for idx, m in mats:
        cmd += ["--buf", f"{idx}={csv(m)}"]
    cmd += ["--out", f"{out_idx}={out_n}"]
    for sp in splices:
        cmd += ["--splice", sp]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout, r.stderr

def extract_result(stdout, idx):
    for line in stdout.splitlines():
        if line.startswith(f"RESULT {idx} "):
            return [float(x) for x in line.split()[2:]]
    return None

def matdiag(vals):
    if vals is None or len(vals) < 64:
        return None
    return [vals[i*8+i] for i in range(8)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--func", default="mad_f32")
    ap.add_argument("--mat", action="append", default=[], help="IDX=spec")
    ap.add_argument("--out", default="3")
    ap.add_argument("--outn", type=int, default=64)
    ap.add_argument("--splice", action="append", default=[])
    ap.add_argument("--grid", type=int, default=32)
    ap.add_argument("--tg", type=int, default=32)
    ap.add_argument("--full", action="store_true", help="print full 8x8 grid")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    mats = []
    for spec in args.mat:
        idx, _, s = spec.partition("=")
        mats.append((int(idx), parse_mat(s)))
    out_idx = int(args.out)
    stdout, stderr = run(args.func, mats, out_idx, args.outn, args.splice, args.grid, args.tg)
    res = extract_result(stdout, out_idx)
    status = "?"
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None,1)[1]
    d = matdiag(res)
    print(f"STATUS {status} DIAG {d}")
    if args.full and res is not None:
        for i in range(8):
            print("  " + " ".join(f"{res[i*8+j]:.3g}" for j in range(8)))
    if not args.quiet and (status != "OK" or res is None):
        sys.stderr.write(stdout[-1500:])
        sys.stderr.write("\n--STDERR--\n"+stderr[-800:])

if __name__ == "__main__":
    main()
