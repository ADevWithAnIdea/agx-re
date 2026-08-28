#!/usr/bin/env python3
"""EXP-0084 frozen generator for the direct-slot boundary kernels.

Deterministic, no randomness, no environment dependence: run once, commit the
output (`cap_kernels.metal`) as a frozen authored artifact, and re-run any
time to prove the committed file is exactly this script's output (byte-for-
byte -- `verify.py --selftest` checks this). Mirrors the mechanical style of
`experiments/EXP-0078-m4-base-slot-census/kernels/capacity.metal` (one
directly-bound `device uint*` per buffer index, one output element per
input), extended one buffer past its 31-argument (indices 0..30) kernel to
probe the MSL compile-time direct-argument boundary (MEM-22).

Usage: python3 gen_cap_kernels.py > cap_kernels.metal
"""
import sys


def kernel(name, n_data):
    """name: kernel identifier. n_data: number of device uint* data buffers
    (b1..b{n_data}), bound at buffer indices 1..n_data. buffer(0) is the
    output array (n_data elements: out[k-1] = bk[0]). Total buffer argument
    count = n_data + 1 (indices 0..n_data)."""
    lines = []
    lines.append("kernel void %s(" % name)
    lines.append("    device uint* out [[buffer(0)]],")
    for k in range(1, n_data + 1):
        comma = "," if k < n_data else ""
        lines.append("    const device uint* b%d [[buffer(%d)]]%s" % (k, k, comma))
    lines.append(") {")
    for k in range(1, n_data + 1):
        lines.append("    out[%d] = b%d[0];" % (k - 1, k))
    lines.append("}")
    return "\n".join(lines)


def main():
    out = []
    out.append("#include <metal_stdlib>")
    out.append("using namespace metal;")
    out.append("// EXP-0084 generated (frozen; authored generator: gen_cap_kernels.py).")
    out.append("// MEM-22 direct-slot-count boundary probe: cap31 = the known-working 31-")
    out.append("// buffer-argument configuration (indices 0..30, replicating the shape of")
    out.append("// EXP-0078's non-promoted capacity.metal hypothesis, independently re-")
    out.append("// established here); cap32 extends by exactly one buffer argument (indices")
    out.append("// 0..31) to test the MSL compile-time direct-argument-count boundary. Each")
    out.append("// output element is one directly-bound buffer's own tag word -- no cross-")
    out.append("// buffer aliasing is possible if every out[k-1] independently equals bk[0].")
    out.append("")
    out.append(kernel("cap31", 30))
    out.append("")
    out.append(kernel("cap32", 31))
    out.append("")
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
