#!/usr/bin/env python3
# Generic splice-sweep harness for RT-1a falsification.
# Sweeps one byte position inside _agc.main across a value set, runs each spliced
# archive on the real GPU via agxrun_persist, and prints value -> outputs.
import sys, os, subprocess, argparse, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

def locate_main(archive, agxparse="agxparse.py"):
    out = subprocess.check_output(["python3", agxparse, archive, "--locate", "_agc.main"], text=True)
    off, ln = out.split()
    return int(off), int(ln)

def u32le(vals):
    return b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in vals)

def f32le(vals):
    return b"".join(struct.pack("<f", float(v)) for v in vals)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--function", default="k")
    ap.add_argument("--archive", required=True)     # base archive
    ap.add_argument("--main-off", type=lambda x:int(x,0), default=None)  # abs offset of _agc.main
    ap.add_argument("--pos", type=lambda x:int(x,0), required=True)   # byte offset within _agc.main
    ap.add_argument("--values", default="0-255")        # e.g. "0-255" or "0,2,4"
    ap.add_argument("--grid", type=int, default=1)
    ap.add_argument("--tg", type=int, default=1)
    ap.add_argument("--in", dest="ins", action="append", default=[])  # IDX=csv (int) or IDX=fcsv:...
    ap.add_argument("--out", dest="outs", action="append", default=[])  # IDX=NELEM
    ap.add_argument("--fast-math", action="store_true")
    ap.add_argument("--decode", default="u32")          # how to print outputs: u32|f32
    ap.add_argument("--timeout", type=float, default=6.0)
    args = ap.parse_args()

    if args.main_off is None:
        args.main_off, _ = locate_main(args.archive)

    # write input files
    ins = {}
    for spec in args.ins:
        idx, val = spec.split("=", 1)
        idx = int(idx)
        if val.startswith("@"):
            ins[idx] = val[1:]
            continue
        if val.startswith("f:"):
            data = f32le([float(x) for x in val[2:].split(",")])
        else:
            data = u32le([int(x, 0) for x in val.split(",")])
        p = f"in_{idx}.bin"
        open(p, "wb").write(data)
        ins[idx] = p
    outs = {}
    for spec in args.outs:
        idx, n = spec.split("=")
        outs[int(idx)] = int(n) * 4

    # value set
    if "-" in args.values and "," not in args.values:
        a, b = args.values.split("-")
        valset = list(range(int(a), int(b) + 1))
    else:
        valset = [int(x, 0) for x in args.values.split(",")]

    base = open(args.archive, "rb").read()
    abspos = args.main_off + args.pos
    orig = base[abspos]
    print(f"# main_off={args.main_off} pos=+0x{args.pos:02x} abspos={abspos} orig=0x{orig:02x}")
    print(f"# sweeping {len(valset)} values")

    runner = PersistRunner(source=args.source, function=args.function,
                           fast_math=args.fast_math, agxrun_persist="./agxrun_persist")
    def decode(b):
        if not b: return "-"
        if args.decode == "f32":
            return ",".join(f"{struct.unpack('<f', b[i:i+4])[0]:g}" for i in range(0, len(b), 4))
        return ",".join(str(struct.unpack('<I', b[i:i+4])[0]) for i in range(0, len(b), 4))
    try:
        for v in valset:
            spliced = bytearray(base)
            spliced[abspos] = v
            sp = "spliced.bin"
            open(sp, "wb").write(spliced)
            resp = runner.request(archive=sp, grid=args.grid, tg=args.tg,
                                  ins=ins, outs=outs, timeout=args.timeout)
            od = " ".join(f"o{idx}={decode(resp['outs'].get(idx, b''))}" for idx in sorted(outs))
            tag = "" if v != orig else "  <== ORIG"
            print(f"0x{v:02x} {resp['status']:12s} {od}{tag}")
    finally:
        runner.close()

if __name__ == "__main__":
    main()
