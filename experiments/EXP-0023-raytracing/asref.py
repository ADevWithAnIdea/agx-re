#!/usr/bin/env python3
# EXP-0023: how is the acceleration structure referenced through userspace?
# Parses iotrace BO dumps and locates the AS GPU VA in the Tier-2 argument buffer
# and the residency/resource tables. CLEAN-ROOM: DATA-TRACE of our own process.
import glob, struct, re, sys

def load(pat):
    f = glob.glob(pat)[0]; buf = bytearray()
    for ln in open(f):
        ln = ln.strip()
        if ln.startswith("#") or ":" not in ln: continue
        for w in ln.split(":", 1)[1].split():
            if re.fullmatch(r"[0-9a-fA-F]{8}", w): buf += int(w, 16).to_bytes(4, "little")
            elif re.fullmatch(r"[0-9a-fA-F]{2}", w): buf += bytes([int(w, 16)])
    return f, buf

AS_VA = 0x1000005c000
TAGS = {0x1000001dc00: "out buf(1)", 0x1000001dd00: "org buf(2)",
        0x1000001de00: "dir buf(3)", AS_VA: "ACCEL_STRUCT VA",
        0x1000001c500: "vbuf(geometry)"}

f, ab = load("maps/*va100000e0000_*.hex")
print("ARG BUFFER", f.split("/")[-1])
for off in range(0x1548, 0x1630, 8):   # 8-aligned; buffer VAs live at 0x1550/58/60
    if off + 8 > len(ab): break
    v = struct.unpack_from("<Q", ab, off)[0]
    print(f"  @0x{off:04x}: 0x{v:016x}  {TAGS.get(v,'')}")

print()
f2, asb = load("maps/*va1000005c000_*.hex")
print("ACCEL STRUCT BO", f2.split("/")[-1], "-- first 128 bytes (GPU/firmware-built BVH):")
for r in range(0, 128, 32):
    print("  +%03x " % r, asb[r:r+32].hex())
