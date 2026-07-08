#!/usr/bin/env python3
# EXP-M4-11 item 6 (reproduces RT-7 §6 / EXP-0031): vertex attribute fetch is IN-SHADER software.
# Vary each MTLVertexDescriptor knob (stride/offset/format/step); if fetch were fixed-function the
# compiled VS bytes would be invariant. Instead each knob moves specific VS bytes => the fetch
# (index*stride+offset load + format-convert ALU + get_sr vertex_id/instance_id) is compiled INTO
# the shader. CLEAN-ROOM: own MSL, own compiled bytes.
import subprocess, os
HERE = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(HERE, "harness")
SRC = os.path.join(HERE, "kernels", "attr_stagein.metal")
# MTLVertexFormat: float3=30 float4=31 uchar4Normalized=9 half4=27
BASE = dict(fmt0=30, off0=0, fmt1=31, off1=16, stride=32, nattr=2, step=0)

def vs_bytes(**kw):
    d = dict(BASE); d.update(kw)
    arch = os.path.join(HERE, "work", "attr.bin")
    cmd = [os.path.join(H, "attrdump"), "-o", arch, "--source", SRC,
           "--vertex", "v_main", "--fragment", "f_main",
           "--fmt0", str(d["fmt0"]), "--off0", str(d["off0"]),
           "--fmt1", str(d["fmt1"]), "--off1", str(d["off1"]),
           "--stride", str(d["stride"]), "--nattr", str(d["nattr"]), "--step", str(d["step"])]
    r = subprocess.run(cmd, capture_output=True, text=True)
    hx = subprocess.run(["python3", os.path.join(H, "agxparse.py"), arch, "--stage", "vertex",
                         "--extract-hex"], capture_output=True, text=True).stdout
    return bytes.fromhex("".join(hx.split()))

def diff(a, b):
    n = max(len(a), len(b)); out = []
    for i in range(n):
        x = a[i] if i < len(a) else None; y = b[i] if i < len(b) else None
        if x != y: out.append((i, x, y))
    return out

base = vs_bytes()
print("baseline VS len=%d" % len(base))
VARY = [("stride 32->64", dict(stride=64)),
        ("attr1 off 16->12", dict(off1=12)),
        ("fmt0 float3->uchar4Normalized", dict(fmt0=9)),
        ("fmt1 float4->half4", dict(fmt1=27)),
        ("step perVertex->perInstance", dict(step=1))]
for tag, kw in VARY:
    v = vs_bytes(**kw); d = diff(base, v)
    dd = ", ".join("@0x%x %s->%s" % (i, "%02x" % x if x is not None else "--",
                                     "%02x" % y if y is not None else "--") for i, x, y in d[:12])
    print("%-34s len=%-3d ndiff=%-3d %s" % (tag, len(v), len(d), dd if d else "IDENTICAL (fixed-function?)"))
