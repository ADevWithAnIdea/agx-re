#!/usr/bin/env python3
"""Generator for kernels/b07_65.metal (EXP-0106, TEX-14 boundary-pair
extension). Deterministic: run with no arguments, writes the .metal file
next to this script. Committed alongside its generated output (both are
hash-pinned in CAPTURE_CONTRACT.json), matching EXP-0095's
gen_direct128.py/direct128.metal precedent (independently re-authored here,
not copied).

A single 65-argument [[texture(0..64)]] compute kernel, all 65 slots bound
simultaneously (so "simultaneously and independently selectable" is
actually exercised, not just each index in isolation), reading the 9
boundary indices the gap doc names as insufficiently tested by the prior
128-argument probe (EXP-0095 only tried 0/63/127): 0, 7, 8, 15, 16, 31, 32,
63, 64.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
N = 65
BOUNDARY = [0, 7, 8, 15, 16, 31, 32, 63, 64]

def main():
    lines = []
    lines.append("// EXP-0106 generated file -- DO NOT HAND-EDIT. Regenerate with")
    lines.append("// `python3 gen_b07.py` (deterministic, no arguments). OWN-SHADER:")
    lines.append("// authored by our own generator, compiled at runtime via")
    lines.append("// -[MTLDevice newLibraryWithSource:options:], no Apple binary involved.")
    lines.append("#include <metal_stdlib>")
    lines.append("using namespace metal;")
    lines.append("")
    params = ", ".join(f"texture2d<uint> t{i} [[texture({i})]]" for i in range(N))
    lines.append(f"kernel void k_b07_tex65(device uint* out [[buffer(0)]], {params}) {{")
    for word, idx in enumerate(BOUNDARY):
        lines.append(f"  out[{word}] = t{idx}.read(uint2(0, 0)).x;")
    lines.append("}")
    lines.append("")
    (HERE / "b07_65.metal").write_text("\n".join(lines) + "\n")
    print("wrote", HERE / "b07_65.metal", "N=", N, "boundary=", BOUNDARY)

if __name__ == "__main__":
    main()
