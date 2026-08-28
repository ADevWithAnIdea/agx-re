#!/usr/bin/env python3
"""EXP-0146 pilot: compile each authored kernel and disassemble _agc.main with
tools/agx-isa (read-only). Prints the instruction sequence with byte offsets."""
import subprocess, sys, importlib.util
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
agxparse = load("agxparse", REPO/"tools"/"shdump"/"agxparse.py")
BIN = EXP/"work"/"bin"
for src in sorted((EXP/"kernels").glob("*.metal")):
    out = HERE/(src.stem + ".bin")
    r = subprocess.run([str(BIN/"shdump"), "-o", str(out), "-f", "k", "--no-fast-math", str(src)],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"### {src.stem}: SHDUMP FAIL {r.stderr[-300:]}"); continue
    buf = out.read_bytes()
    _, pieces = agxparse.extract_agx(buf)
    mb = pieces["_agc.main"]
    recs, leftover = isadb.disassemble(mb)
    print(f"### {src.stem}: main={len(mb)}B leftover={len(leftover)}")
    off = 0
    for rec in recs:
        L = rec.get('length') or 0
        print(f"   +0x{off:03x} {rec['mnemonic']:<18} {mb[off:off+L].hex() if L else '?'}")
        if not L:
            print("   (record with no length -- stopping walk)"); break
        off += L
    if leftover:
        print("   LEFTOVER", leftover.hex())
