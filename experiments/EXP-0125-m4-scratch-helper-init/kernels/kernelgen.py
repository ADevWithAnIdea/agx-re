#!/usr/bin/env python3
"""Generate authored MSL sources for EXP-0125.

Reuses the array-loop design validated by EXP-0041/EXP-0107 (a runtime-
bounded loop over a `thread float a[K]` array so the compiler cannot prove a
smaller live set and cannot promote the array to registers once K exceeds
the GPR file), rewritten fresh for this experiment's own needs:

  - a TRIVIAL kernel (K=0, no array, no spill at all) for the I-family
    "never spills" control variant and as the B-family / smoke known-good
    floor.
  - a K-parametrized array-loop kernel per stage (CS/VS/FS), identical in
    shape to EXP-0107's, used by the I-family SPILL variant, the B-family
    ceiling bisection, and the C-family concurrent-pressure kernel.

Clean-room: 100% authored here; no Apple code, header, or template is
copied. The recurrence design note (bounded contraction, not unbounded
growth, for n>1 passes) is carried over unchanged from EXP-0107's own
authored generator (our own prior work, not Apple's).
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRELUDE = "#include <metal_stdlib>\nusing namespace metal;\n\n"


def array_body(k, index_expr, out_stmt, indent="    "):
    lines = [
        f"float a[{k}];",
        f"for (uint i = 0u; i < {k}u; ++i) a[i] = input[(({index_expr}) * {k}u + i) % 4096u];",
        "for (uint pass = 1u; pass < n; ++pass) {",
        "    float t = input[pass % 4096u];",
        f"    for (uint i = 0u; i < {k}u; ++i) "
        f"a[i] = 0.5f * a[i] + 0.5f * a[(i + 1u) % {k}u] + t * 1e-6f;",
        "}",
        "float sum = 0.0f;",
        f"for (uint i = 0u; i < {k}u; ++i) sum += a[i];",
        out_stmt,
    ]
    return "\n".join(indent + l for l in lines)


def compute_source(k):
    body = array_body(k, "gid", "out[gid] = sum;")
    return PRELUDE + f'''kernel void k_main(device float *out [[buffer(0)]],
                   device const float *input [[buffer(1)]],
                   constant uint &n [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {{
{body}
}}
'''


def compute_trivial_source():
    return PRELUDE + '''kernel void k_main(device float *out [[buffer(0)]],
                   device const float *input [[buffer(1)]],
                   constant uint &n [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {
    float sum = input[gid % 4096u];
    for (uint pass = 1u; pass < n; ++pass) sum = 0.5f * sum + 0.5f * input[pass % 4096u];
    out[gid] = sum;
}
'''


def vertex_source(k):
    body = array_body(k, "vid", "out.color = float4(sum * 0x1p-16f, 0.25f, 0.5f, 1.0f);")
    return PRELUDE + f'''struct VOut {{ float4 position [[position]]; float4 color; }};

vertex VOut v_main(device const float *input [[buffer(0)]],
                   constant uint &n [[buffer(1)]],
                   uint vid [[vertex_id]]) {{
    VOut out;
{body}
    float2 p = (vid == 0u) ? float2(-1.0f, -1.0f) :
               ((vid == 1u) ? float2(3.0f, -1.0f) : float2(-1.0f, 3.0f));
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}}

fragment float4 f_main(VOut in [[stage_in]]) {{ return in.color; }}
'''


def fragment_source(k):
    body = array_body(k, "pixel", "return float4(sum * 0x1p-16f, 0.25f, 0.5f, 1.0f);")
    return PRELUDE + f'''struct VOut {{ float4 position [[position]]; }};

vertex VOut v_main(uint vid [[vertex_id]]) {{
    VOut out;
    float2 p = (vid == 0u) ? float2(-1.0f, -1.0f) :
               ((vid == 1u) ? float2(3.0f, -1.0f) : float2(-1.0f, 3.0f));
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}}

fragment float4 f_main(VOut in [[stage_in]],
                       device const float *input [[buffer(0)]],
                       constant uint &n [[buffer(1)]]) {{
    uint pixel = uint(in.position.y) * 8u + uint(in.position.x);
{body}
}}
'''


# Fixed K levels used by the I family (init-time checkpoint) and C family
# (concurrent pressure): one "clearly spilling but well inside EXP-0107's
# validated-safe range" level, reused everywhere so only one .metal file per
# stage is needed for those two families.
FIXED_K = 24576

# B family (ceiling bisection) writes its own trial .metal files at runtime
# via harness/ceiling.m calling this module directly (see --emit mode
# below), one per trial K, because the search range is only known once the
# first coarse probe runs.


def write_fixed(k=FIXED_K):
    written = []
    (HERE / "cs_trivial.metal").write_text(compute_trivial_source())
    written.append("cs_trivial.metal")
    for stage, fn in (("cs", compute_source), ("vs", vertex_source), ("fs", fragment_source)):
        name = f"{stage}_k{k}.metal"
        (HERE / name).write_text(fn(k))
        written.append(name)
    return written


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", choices=("cs", "vs", "fs"), help="print one trial source to stdout")
    ap.add_argument("--k", type=int, default=0)
    a = ap.parse_args()
    if a.emit:
        fn = {"cs": compute_source, "vs": vertex_source, "fs": fragment_source}[a.emit]
        print(fn(a.k))
        return
    written = write_fixed()
    for name in written:
        print(f"wrote {name} ({(HERE / name).stat().st_size} bytes)")


if __name__ == "__main__":
    main()
