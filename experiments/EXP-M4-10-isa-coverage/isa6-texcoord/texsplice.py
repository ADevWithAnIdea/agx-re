#!/usr/bin/env python3
# Splice bytes into _agc.main of a compute archive and run it under texrun with a
# multi-slice input texture; decode the read-back float. OWN-SHADER only.
import os, sys, subprocess, struct, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
AGXPARSE = os.path.join(ROOT, "tools", "agxtest", "agxparse.py")
SHDUMP = os.path.join(ROOT, "tools", "agxtest", "shdump")
TEXRUN = os.path.join(HERE, "texrun")

spec = importlib.util.spec_from_file_location("agxparse", AGXPARSE)
agxparse = importlib.util.module_from_spec(spec); spec.loader.exec_module(agxparse)

def build(src, func, out):
    r = subprocess.run([SHDUMP, "-o", out, "-f", func, src],
                       capture_output=True, text=True)
    if not os.path.exists(out):
        raise RuntimeError("shdump failed: " + r.stderr)

def splice_archive(inpath, outpath, splices):
    with open(inpath, "rb") as f:
        b = bytearray(f.read())
    loc = agxparse.locate_region(bytes(b), "_agc.main")
    base, length = loc
    notes = []
    for off, hexbytes in splices:
        nb = bytes.fromhex(hexbytes)
        old = bytes(b[base+off:base+off+len(nb)])
        b[base+off:base+off+len(nb)] = nb
        notes.append(f"@0x{off:02x}: {old.hex()}->{nb.hex()}")
    with open(outpath, "wb") as f:
        f.write(bytes(b))
    return notes

def run(archive, src, func, texkind, nslices, size=1):
    cmd = [TEXRUN, "--archive", archive, "--source", src, "--function", func,
           "--texkind", texkind, "--nslices", str(nslices), "--size", str(size),
           "--out", "0=4"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    status = "?"; val = None; outhex=None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS "): status = line.split(None,1)[1]
        elif line.startswith("OUT 0"):
            outhex = line.split(None,2)[2]
            try: val = struct.unpack("<f", bytes.fromhex(outhex)[:4])[0]
            except: val = None
    return status, val, outhex, r.stdout + r.stderr

if __name__ == "__main__":
    # args: src func texkind nslices size off=hex [off=hex ...]
    src, func, texkind, nslices, size = sys.argv[1:6]
    nslices = int(nslices); size = int(size)
    splices = []
    for a in sys.argv[6:]:
        off, _, hx = a.partition("=")
        splices.append((int(off, 0), hx))
    base = os.path.join(HERE, "work", f"_sp_{func}_{texkind}.bin")
    build(src, func, base)
    sp = base + ".spliced"
    notes = splice_archive(base, sp, splices) if splices else []
    runarch = sp if splices else base
    st, val, outhex, log = run(runarch, src, func, texkind, nslices, size)
    print(f"splice {notes} -> STATUS {st} val={val} rawhex={outhex}")
    if st != "OK":
        sys.stderr.write(log)
