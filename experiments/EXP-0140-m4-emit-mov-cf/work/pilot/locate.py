#!/usr/bin/env python3
"""Pilot: compile a carrier and disassemble its _agc.main, printing offsets."""
import subprocess, sys, os
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
sys.path.insert(0, str(REPO / "tools" / "shdump"))
import isadb, agxparse

BIN = EXP / "work" / "bin"

def compile_main(kernel, fn="k"):
    out = HERE / (Path(kernel).stem + ".bin")
    subprocess.run([str(BIN/"shdump"), "-o", str(out), "--no-fast-math", str(kernel), "-f", fn],
                   check=True, capture_output=True)
    buf = out.read_bytes()
    off, ln = agxparse.locate_region(buf, "_agc.main")
    _, pieces = agxparse.extract_agx(buf)
    return out, off, pieces["_agc.main"]

for k in sys.argv[1:]:
    path, region_off, main = compile_main(k)
    print("==", k, "archive", path.name, "region_off", region_off, "main_len", len(main))
    print("HEX", main.hex())
    off = 0
    while off < len(main):
        try:
            rec, L = isadb.decode_one(main, off)
        except ValueError as e:
            print("  +0x%03x  <undecodable> %s" % (off, e)); break
        print("  +0x%03x  %-18s %s  %s" % (off, rec["mnemonic"], rec["hex"],
              {k2: v for k2, v in rec["fields"].items()}))
        off += L
