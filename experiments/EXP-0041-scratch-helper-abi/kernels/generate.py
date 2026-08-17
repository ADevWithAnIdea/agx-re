#!/usr/bin/env python3
"""Generate and retain minimal-pair OWN-MSL pressure probes for EXP-0041."""

from pathlib import Path

HERE = Path(__file__).resolve().parent


def pressure_body(k, source, index, out_expr):
    lines = [f"    float a{i} = {source}[({index}) * {k}u + {i}u];" for i in range(k)]
    lines.append("    for (uint pass = 1; pass < n; ++pass) {")
    lines.append(f"        float t = {source}[pass];")
    for i in range(k):
        lines.append(f"        a{i} = fma(a{i}, t, a{(i + 1) % k});")
    lines.append("    }")
    lines.append("    float sum = 0.0f;")
    for i in range(k):
        lines.append(f"    sum += a{i};")
    lines.append(f"    {out_expr}")
    return "\n".join(lines)


def compute(k):
    return f'''#include <metal_stdlib>
using namespace metal;

kernel void k_main(device float *out [[buffer(0)]],
                   device const float *input [[buffer(1)]],
                   constant uint &n [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {{
{pressure_body(k, "input", "gid", "out[gid] = sum;")}
}}
'''


def vertex(k):
    return f'''#include <metal_stdlib>
using namespace metal;

struct VOut {{ float4 position [[position]]; float4 color; }};

vertex VOut v_main(device const float *input [[buffer(0)]],
                   constant uint &n [[buffer(1)]],
                   uint vid [[vertex_id]]) {{
    VOut out;
{pressure_body(k, "input", "vid", "out.color = float4(sum * 0x1p-16f, 0.25f, 0.5f, 1.0f);")}
    float2 p = (vid == 0u) ? float2(-1.0f, -1.0f) :
               ((vid == 1u) ? float2(3.0f, -1.0f) : float2(-1.0f, 3.0f));
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}}

fragment float4 f_main(VOut in [[stage_in]]) {{ return in.color; }}
'''


def fragment(k):
    return f'''#include <metal_stdlib>
using namespace metal;

struct VOut {{ float4 position [[position]]; }};

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
{pressure_body(k, "input", "pixel", "return float4(sum * 0x1p-16f, 0.25f, 0.5f, 1.0f);")}
}}
'''


def main():
    cases = {
        "cs_nospill_k72.metal": compute(72),
        "cs_spill_k80.metal": compute(80),
        "cs_spill_k96.metal": compute(96),
        "cs_spill_k112.metal": compute(112),
        "cs_spill_k160.metal": compute(160),
        "vs_nospill_k72.metal": vertex(72),
        "vs_spill_k112.metal": vertex(112),
        "fs_nospill_k72.metal": fragment(72),
        "fs_spill_k112.metal": fragment(112),
    }
    for name, source in cases.items():
        (HERE / name).write_text(source)
        print(f"wrote {name} ({len(source)} bytes)")


if __name__ == "__main__":
    main()
