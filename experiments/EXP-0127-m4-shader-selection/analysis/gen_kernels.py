#!/usr/bin/env python3
"""EXP-0127 kernel generator (OWN-SHADER, authored by us).

Deterministically generates the two MSL sources used by harness/vstoken:

  kernels/vs_uniform.metal  -- N near-identical vertex functions (vs_u0000..)
                                differing only by a per-function integer
                                literal, so each is a genuinely distinct
                                named MTLFunction/compile target but with
                                (as close as the compiler allows) EQUAL
                                compiled code size. Isolates the pure-ordinal
                                hypothesis for the VS token.
  kernels/vs_varied.metal   -- 8 vertex functions of deliberately DIFFERENT
                                compiled sizes (increasing unrolled FMA
                                chains), used in an interleaved
                                tiny/huge/tiny/huge/... creation order to
                                test the size-dependent-offset hypothesis.

A single shared trivial fragment function (fs_flat, returns a per-draw
uniform colour) is reused for every vertex function in both files, so any
observed VDM token difference is attributable to the VS side only (mirrors
EXP-0042's SS/SF/LS/LF stage-matrix separation).

Deterministic: re-running this script with the same arguments reproduces
byte-identical output (checked by RESULTS.md / verify.py against the
frozen sha256 recorded in PRE_REGISTRATION.md).
"""
import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNELS = ROOT / "kernels"

HEADER = """#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 position [[position]];
};

// Shared trivial fragment: returns a host-provided uniform colour. Kept
// IDENTICAL across every pipeline in this file so any observed VDM/pool
// selector difference between pipelines is attributable only to the VS
// side (mirrors EXP-0042's stage-matrix separation of VS vs FS fields).
fragment float4 fs_flat(const device float4 *colour [[buffer(1)]])
{
    return colour[0];
}
"""


def uniform_source(n: int) -> str:
    parts = [HEADER]
    for i in range(n):
        # Each function has a distinct integer literal folded into the
        # position scale, so the compiled constant program differs per
        # function (forcing a genuinely distinct compiled entry, as
        # EXP-0042's fs_equal_a/fs_equal_b pair established is necessary
        # and sufficient) while the *shape* of the arithmetic -- and hence
        # the expected compiled code size -- stays constant across i.
        parts.append(f"""
vertex VOut vs_u{i:04d}(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{{
    VOut out;
    float2 p = positions[vertex_id] * float({i} % 97 + 1);
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}}
""")
    return "".join(parts)


# Sizes (unrolled FMA chain length) for the varied-size family, chosen to
# span roughly an order of magnitude in compiled instruction count while
# staying inside one MSL function each, interleaved tiny/huge/tiny/huge...
# tiny=0 unrolled ops (identity), huge=48 unrolled ops.
VARIED_SIZES = [0, 48, 4, 40, 12, 32, 20, 24]


def varied_source() -> str:
    parts = [HEADER]
    for idx, ops in enumerate(VARIED_SIZES):
        if ops == 0:
            parts.append(f"""
vertex VOut vs_v{idx:02d}_ops{ops:03d}(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{{
    VOut out;
    out.position = float4(positions[vertex_id], 0.0f, 1.0f);
    return out;
}}
""")
            continue
        body_lines = ["    float2 q = positions[vertex_id];"]
        for k in range(ops):
            body_lines.append(
                f"    q = fma(q, params[0].xy, params[1].xy * float({(k % 7) + 1}));"
            )
        parts.append(f"""
vertex VOut vs_v{idx:02d}_ops{ops:03d}(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]],
                        const device float4 *params [[buffer(1)]])
{{
{chr(10).join(body_lines)}
    VOut out;
    out.position = float4(q, 0.0f, 1.0f);
    return out;
}}
""")
    return "".join(parts)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-uniform", type=int, default=160)
    args = ap.parse_args()

    KERNELS.mkdir(exist_ok=True)
    u = uniform_source(args.n_uniform)
    v = varied_source()
    (KERNELS / "vs_uniform.metal").write_text(u)
    (KERNELS / "vs_varied.metal").write_text(v)
    print(f"vs_uniform.metal n={args.n_uniform} bytes={len(u)} sha256={sha(u)}")
    print(f"vs_varied.metal sizes={VARIED_SIZES} bytes={len(v)} sha256={sha(v)}")


if __name__ == "__main__":
    main()
