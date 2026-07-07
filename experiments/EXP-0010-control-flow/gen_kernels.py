#!/usr/bin/env python3
# gen_kernels.py -- EXP-0010. Emit OUR OWN control-flow MSL kernels covering
# if/else, for/while, break/continue, early return, select/ternary, and
# data-dependent divergence (branch on thread_position_in_grid), plus a few
# structure/uniform-loading probes. Each kernel function is named `k` so the
# existing shdump `-f k` path just works.
#
# CLEAN-ROOM: this is OUR OWN MSL source. No Apple code is read or copied.

import os

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.join(HERE, "kernels")

# Standard signatures reused across kernels.
SIG1 = ("device int* out [[buffer(0)]], device const int* a [[buffer(1)]], "
        "uint gid [[thread_position_in_grid]]")
SIG2 = ("device int* out [[buffer(0)]], device const int* a [[buffer(1)]], "
        "device const int* b [[buffer(2)]], uint gid [[thread_position_in_grid]]")
SIGU = ("device int* out [[buffer(0)]], device const int* a [[buffer(1)]], "
        "constant int& n [[buffer(2)]], uint gid [[thread_position_in_grid]]")

KERNELS = {
    # ---- structure / uniform-and-pointer-load probes ---------------------
    "copy1":   (SIG1, "out[gid] = a[gid];"),
    "add2":    (SIG2, "out[gid] = a[gid] + b[gid];"),
    "scalaradd": (SIGU, "out[gid] = a[gid] + n;"),           # scalar uniform n
    "gidonly": ("device int* out [[buffer(0)]], uint gid [[thread_position_in_grid]]",
                "out[gid] = int(gid);"),                       # only the grid index

    # ---- forward branches: if/else, early return, ternary ----------------
    "if_data": (SIG1, "if (a[gid] > 5) out[gid] = 100; else out[gid] = 200;"),
    "if_grid": (SIG1, "if (gid < 4) out[gid] = 111; else out[gid] = 222;"),
    "early_ret": (SIG1, "if (gid >= 4) return; out[gid] = 7;"),
    "ternary": (SIG1, "out[gid] = a[gid] > 5 ? 100 : 200;"),
    "select_v": (SIG1, "out[gid] = (a[gid] & 1) ? (a[gid]*2) : (a[gid]+1);"),
    "if_noelse": (SIG1, "int v = a[gid]; if (v > 10) v = v - 10; out[gid] = v;"),

    # ---- backward branches: loops (data-dependent trip counts) -----------
    "for_dyn": (SIG1, "int s = 0; for (uint i = 0; i < uint(a[gid]); i++) s += int(i); out[gid] = s;"),
    "while_dyn": (SIG1, "int s = 0; int i = a[gid]; while (i > 0) { s += i; i--; } out[gid] = s;"),
    "for_fixed": (SIG1, "int s = 0; for (int i = 0; i < 10; i++) s += a[gid]; out[gid] = s;"),

    # ---- break / continue ------------------------------------------------
    "brk": (SIG1, "int s = 0; for (uint i = 0; i < 100u; i++) { if (i >= uint(a[gid])) break; s += int(i); } out[gid] = s;"),
    "cont": (SIG1, "int s = 0; for (uint i = 0; i < uint(a[gid]); i++) { if (i & 1u) continue; s += int(i); } out[gid] = s;"),

    # ---- nested / reconvergence ------------------------------------------
    "nested": (SIG1, "int s = 0; for (uint i = 0; i < uint(a[gid]); i++) { for (uint j = 0; j < i; j++) { s += 1; } } out[gid] = s;"),
    "divloop": (SIG1, "int s = a[gid]; if (gid & 1u) { for (uint i = 0; i < 3u; i++) s += 10; } else { s -= 1; } out[gid] = s;"),
}

TEMPLATE = """#include <metal_stdlib>
using namespace metal;
kernel void k({sig}) {{
    {body}
}}
"""

def main():
    os.makedirs(KDIR, exist_ok=True)
    for name, (sig, body) in KERNELS.items():
        path = os.path.join(KDIR, name + ".metal")
        with open(path, "w") as f:
            f.write(TEMPLATE.format(sig=sig, body=body))
    print(f"wrote {len(KERNELS)} kernels to {KDIR}")
    for name in KERNELS:
        print("  " + name)

if __name__ == "__main__":
    main()
