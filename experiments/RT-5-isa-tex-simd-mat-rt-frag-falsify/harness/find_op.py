#!/usr/bin/env python3
# find_op.py -- compile our MSL, extract _agc.main, tokenize it, and print each
# instruction with its BYTE OFFSET so we can pick a splice --pos. Runs on device.
# Usage: python3 find_op.py <src.metal> [function] [--stage compute|vertex|fragment] [--archive out.bin]
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isadb

def main():
    src = sys.argv[1]
    fn = "k"
    stage = "compute"
    archive = "loc.bin"
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--stage": stage = args[i+1]; i += 2
        elif args[i] == "--archive": archive = args[i+1]; i += 2
        elif args[i] == "--render": stage = "render"; i += 1
        else: fn = args[i]; i += 1

    if stage == "render":
        subprocess.check_call(["./shdump", "-o", archive, "--no-fast-math",
                               "--render", "--vertex", "v_main", "--fragment", "f_main", src])
        stage = "fragment"
    else:
        subprocess.check_call(["./shdump", "-o", archive, "--no-fast-math", "-f", fn, src])
    hx = subprocess.check_output(["python3", "agxparse.py", archive, "--stage", stage,
                                  "--extract-hex"], text=True).strip().split()[-1]
    buf = bytes.fromhex(hx)
    print(f"# archive={archive} stage={stage} main_len={len(buf)}")
    print(f"# HEX {buf.hex()}")
    recs, leftover = isadb.disassemble(buf)
    off = 0
    for r in recs:
        if r.get("error"):
            print(f"  +0x{off:03x}  <UNKNOWN>  {r['hex']}  ({r['error']})")
            break
        opn = f"[{r['op_mnemonic']}]" if r.get("op_mnemonic") else ""
        fields = " ".join(f"{k}={v:#x}" for k, v in r['fields'].items())
        print(f"  +0x{off:03x}  b0=0x{buf[off]:02x} {r['mnemonic']:16s}{opn:10s} len={r['length']:2d} {r['hex']:<34s} {fields}")
        off += r["length"]
    if leftover:
        print(f"LEFTOVER {len(leftover)} bytes @ +0x{off:03x}: {leftover.hex()}")

if __name__ == "__main__":
    main()
