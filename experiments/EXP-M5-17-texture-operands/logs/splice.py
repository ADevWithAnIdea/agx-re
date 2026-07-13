#!/usr/bin/env python3
# splice.py ARCH.bin SRC.metal VERT FRAG STAGE "off=hex,off=hex,..." [render-args...]
# Splices bytes at fragment _agc.main-relative offsets, runs agxrender2, prints PIXEL.
import sys, subprocess, os, shutil
AP=os.path.expanduser("~/cleanroom_work/tools/shdump/agxparse.py")
REND=os.path.expanduser("~/cleanroom_work/EXP-M5-17/agxrender2")

arch, src, vert, frag, stage, splicespec = sys.argv[1:7]
extra = sys.argv[7:]

# locate absolute offset of _agc.main in the chosen stage
out = subprocess.check_output(["python3", AP, arch, "--stage", stage, "--locate", "_agc.main"]).decode().split()
absoff, length = int(out[0]), int(out[1])

with open(arch, "rb") as f: data = bytearray(f.read())
applied=[]
if splicespec.strip():
    for item in splicespec.split(","):
        off_s, hx = item.split("=")
        off = int(off_s, 0)
        b = bytes.fromhex(hx)
        for i,byte in enumerate(b):
            data[absoff+off+i] = byte
        applied.append((off, hx))

spath = arch + ".spliced"
with open(spath, "wb") as f: f.write(data)

cmd = [REND, "--archive", spath, "--source", src, "--vertex", vert, "--fragment", frag] + extra
r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
pix = [l for l in r.stdout.splitlines() if l.startswith("PIXEL") or l.startswith("STATUS")]
print(f"splice {applied}: " + " | ".join(pix))
