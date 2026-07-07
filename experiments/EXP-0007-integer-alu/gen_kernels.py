#!/usr/bin/env python3
# gen_kernels.py -- generate the EXP-0007 integer-ALU provocation kernels.
# Each kernel is minimal: out[gid] = a[gid] OP b[gid] (or an immediate form),
# forcing the compiler to emit a single integer-ALU instruction (byte0 0x9f).
# CLEAN-ROOM: all of these are OUR OWN MSL.
import os
HERE = os.path.dirname(os.path.abspath(__file__))
KD = os.path.join(HERE, "kernels")
os.makedirs(KD, exist_ok=True)

HDR = "#include <metal_stdlib>\nusing namespace metal;\n\n"

# binary op kernels: (name, type, expr) where expr uses a,b
BIN = [
    # signed int
    ("iadd",  "int",  "a[gid] + b[gid]"),
    ("isub",  "int",  "a[gid] - b[gid]"),
    ("imul",  "int",  "a[gid] * b[gid]"),
    ("iand",  "int",  "a[gid] & b[gid]"),
    ("ior",   "int",  "a[gid] | b[gid]"),
    ("ixor",  "int",  "a[gid] ^ b[gid]"),
    ("ishl",  "int",  "a[gid] << b[gid]"),
    ("iashr", "int",  "a[gid] >> b[gid]"),          # arithmetic (signed) shift right
    ("imin",  "int",  "min(a[gid], b[gid])"),
    ("imax",  "int",  "max(a[gid], b[gid])"),
    # unsigned int
    ("uadd",  "uint", "a[gid] + b[gid]"),
    ("usub",  "uint", "a[gid] - b[gid]"),
    ("umul",  "uint", "a[gid] * b[gid]"),
    ("uand",  "uint", "a[gid] & b[gid]"),
    ("uor",   "uint", "a[gid] | b[gid]"),
    ("uxor",  "uint", "a[gid] ^ b[gid]"),
    ("ushr",  "uint", "a[gid] >> b[gid]"),          # logical (unsigned) shift right
    ("umin",  "uint", "min(a[gid], b[gid])"),
    ("umax",  "uint", "max(a[gid], b[gid])"),
]

def bin_kernel(ty, expr):
    return (HDR +
        f"kernel void k(device const {ty} *a [[buffer(0)]],\n"
        f"              device const {ty} *b [[buffer(1)]],\n"
        f"              device {ty} *out [[buffer(2)]],\n"
        f"              uint gid [[thread_position_in_grid]]) {{\n"
        f"    out[gid] = {expr};\n"
        f"}}\n")

for name, ty, expr in BIN:
    with open(os.path.join(KD, f"{name}.metal"), "w") as f:
        f.write(bin_kernel(ty, expr))

# comparison-producing kernels -> integer 0/1
CMP = [
    ("icmp_lt", "int",  "a[gid] < b[gid]"),
    ("icmp_eq", "int",  "a[gid] == b[gid]"),
    ("icmp_gt", "int",  "a[gid] > b[gid]"),
    ("ucmp_lt", "uint", "a[gid] < b[gid]"),
]
for name, ty, expr in CMP:
    with open(os.path.join(KD, f"{name}.metal"), "w") as f:
        f.write(HDR +
            f"kernel void k(device const {ty} *a [[buffer(0)]],\n"
            f"              device const {ty} *b [[buffer(1)]],\n"
            f"              device int *out [[buffer(2)]],\n"
            f"              uint gid [[thread_position_in_grid]]) {{\n"
            f"    out[gid] = ({expr}) ? 1 : 0;\n"
            f"}}\n")

# immediate-form kernels: out = a OP <constant>. Sweep constants to reverse the
# integer immediate encoding.
def imm_kernel(ty, expr):
    return (HDR +
        f"kernel void k(device const {ty} *a [[buffer(0)]],\n"
        f"              device {ty} *out [[buffer(1)]],\n"
        f"              uint gid [[thread_position_in_grid]]) {{\n"
        f"    out[gid] = {expr};\n"
        f"}}\n")

IMM = [
    ("addimm1",   "int",  "a[gid] + 1"),
    ("addimm5",   "int",  "a[gid] + 5"),
    ("addimm255", "int",  "a[gid] + 255"),
    ("addimm256", "int",  "a[gid] + 256"),
    ("addimmbig", "int",  "a[gid] + 0x12345"),
    ("andimm",    "uint", "a[gid] & 0xff"),
    ("orimm",     "uint", "a[gid] | 0x100"),
    ("xorimm",    "uint", "a[gid] ^ 0x7"),
    ("shlimm3",   "int",  "a[gid] << 3"),
    ("shrimm2",   "int",  "a[gid] >> 2"),
]
for name, ty, expr in IMM:
    with open(os.path.join(KD, f"{name}.metal"), "w") as f:
        f.write(imm_kernel(ty, expr))

# dst-relocation kernel (like float dstc): three live outputs so dst is a fresh
# register we can steer. out = a+b, o2 = a, o3 = b (all used -> kept live).
with open(os.path.join(KD, "dstc.metal"), "w") as f:
    f.write(HDR +
        "kernel void k(device const int *a [[buffer(0)]],\n"
        "              device const int *b [[buffer(1)]],\n"
        "              device int *out [[buffer(2)]],\n"
        "              device int *o2  [[buffer(3)]],\n"
        "              device int *o3  [[buffer(4)]],\n"
        "              uint gid [[thread_position_in_grid]]) {\n"
        "    int va = a[gid]; int vb = b[gid];\n"
        "    out[gid] = va + vb; o2[gid] = va; o3[gid] = vb;\n"
        "}\n")

# 3-source / fused candidates (noted, not fully solved)
with open(os.path.join(KD, "imad.metal"), "w") as f:
    f.write(HDR +
        "kernel void k(device const int *a [[buffer(0)]],\n"
        "              device const int *b [[buffer(1)]],\n"
        "              device const int *c [[buffer(2)]],\n"
        "              device int *out [[buffer(3)]],\n"
        "              uint gid [[thread_position_in_grid]]) {\n"
        "    out[gid] = a[gid] * b[gid] + c[gid];\n"
        "}\n")
with open(os.path.join(KD, "ibfi.metal"), "w") as f:
    f.write(HDR +
        "kernel void k(device const uint *a [[buffer(0)]],\n"
        "              device const uint *b [[buffer(1)]],\n"
        "              device uint *out [[buffer(2)]],\n"
        "              uint gid [[thread_position_in_grid]]) {\n"
        "    out[gid] = insert_bits(a[gid], b[gid], 3u, 5u);\n"
        "}\n")
with open(os.path.join(KD, "ibfe.metal"), "w") as f:
    f.write(HDR +
        "kernel void k(device const uint *a [[buffer(0)]],\n"
        "              device uint *out [[buffer(1)]],\n"
        "              uint gid [[thread_position_in_grid]]) {\n"
        "    out[gid] = extract_bits(a[gid], 4u, 8u);\n"
        "}\n")
with open(os.path.join(KD, "ipopcount.metal"), "w") as f:
    f.write(HDR +
        "kernel void k(device const uint *a [[buffer(0)]],\n"
        "              device uint *out [[buffer(1)]],\n"
        "              uint gid [[thread_position_in_grid]]) {\n"
        "    out[gid] = popcount(a[gid]);\n"
        "}\n")

names = sorted(os.listdir(KD))
print(f"wrote {len(names)} kernels to {KD}:")
for n in names:
    print("  ", n)
