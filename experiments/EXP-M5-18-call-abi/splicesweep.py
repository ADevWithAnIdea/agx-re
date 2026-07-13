#!/usr/bin/env python3
# splicesweep.py (EXP-M5-18) — single-byte splice sweep over a region of _agc.main
# for a LINKED (visible_function_table) kernel, run via agxrunlink with a bound table.
# For each offset it sets the byte to a chosen value, runs, and reports the output
# delta vs baseline (or HANG/ERROR). Load-bearing bytes -> output change / fault;
# inert bytes -> identical output.
#
# CLEAN-ROOM: operates only on OUR OWN compiled+linked archive bytes.
import argparse, os, subprocess, sys, importlib.util

def load_agxparse(p):
    spec = importlib.util.spec_from_file_location("agxparse", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def run(cmd, timeout):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "HANG", None
    out = None; status = "UNKNOWN"
    for line in r.stdout.splitlines():
        if line.startswith("STATUS "): status = line.split(None,1)[1]
        elif line.startswith("OUT 0 "): out = line.split(None,2)[2]
    return status, out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--function", default="k")
    ap.add_argument("--grid", default="8"); ap.add_argument("--tg", default="8")
    ap.add_argument("--buf", action="append", default=[])
    ap.add_argument("--out", default="0=32")
    ap.add_argument("--vft", required=True)
    ap.add_argument("--agxrunlink", default="./agxrunlink")
    ap.add_argument("--agxparse", default="./agxparse.py")
    ap.add_argument("--symbol", default="_agc.main")
    ap.add_argument("--start", type=lambda x:int(x,0), required=True)
    ap.add_argument("--end", type=lambda x:int(x,0), required=True)
    ap.add_argument("--set", type=lambda x:int(x,0), default=0x00, help="value to write (default 0x00)")
    ap.add_argument("--timeout", type=float, default=12.0)
    args = ap.parse_args()

    agxparse = load_agxparse(args.agxparse)
    with open(args.archive,"rb") as f: base = f.read()
    loc = agxparse.locate_region(base, args.symbol)
    if loc is None: print("could not locate", args.symbol); sys.exit(2)
    reg_off, reg_len = loc
    print(f"region {args.symbol}: file_off={reg_off} len={reg_len}")

    def do_run(buf):
        with open("_sweep.bin","wb") as f: f.write(buf)
        cmd = [args.agxrunlink, "--archive","_sweep.bin","--source",args.source,
               "--function",args.function,"--grid",args.grid,"--tg",args.tg,
               "--out",args.out,"--vft",args.vft]
        for b in args.buf: cmd += ["--buf", b]
        return run(cmd, args.timeout)

    st0, out0 = do_run(bytearray(base))
    print(f"BASELINE status={st0} out={out0}")
    if st0 != "OK":
        print("baseline not OK; abort"); sys.exit(1)

    for off in range(args.start, args.end):
        b = bytearray(base)
        abs_off = reg_off + off
        old = b[abs_off]
        if old == args.set:
            print(f"  +0x{off:02x}: old=0x{old:02x} (== set, skip)")
            continue
        b[abs_off] = args.set
        st, out = do_run(b)
        tag = "SAME" if (out == out0 and st=="OK") else ("*** CHANGE" if st=="OK" else f"*** {st}")
        print(f"  +0x{off:02x}: 0x{old:02x}->0x{args.set:02x}  status={st}  {tag}"
              + (f"  out={out}" if (st=='OK' and out!=out0) else ""))

if __name__ == "__main__":
    main()
