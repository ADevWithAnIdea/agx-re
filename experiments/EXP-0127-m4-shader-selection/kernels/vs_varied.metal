#include <metal_stdlib>
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

vertex VOut vs_v00_ops000(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]])
{
    VOut out;
    out.position = float4(positions[vertex_id], 0.0f, 1.0f);
    return out;
}

vertex VOut vs_v01_ops048(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]],
                        const device float4 *params [[buffer(1)]])
{
    float2 q = positions[vertex_id];
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    VOut out;
    out.position = float4(q, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_v02_ops004(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]],
                        const device float4 *params [[buffer(1)]])
{
    float2 q = positions[vertex_id];
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    VOut out;
    out.position = float4(q, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_v03_ops040(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]],
                        const device float4 *params [[buffer(1)]])
{
    float2 q = positions[vertex_id];
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    VOut out;
    out.position = float4(q, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_v04_ops012(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]],
                        const device float4 *params [[buffer(1)]])
{
    float2 q = positions[vertex_id];
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    VOut out;
    out.position = float4(q, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_v05_ops032(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]],
                        const device float4 *params [[buffer(1)]])
{
    float2 q = positions[vertex_id];
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    VOut out;
    out.position = float4(q, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_v06_ops020(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]],
                        const device float4 *params [[buffer(1)]])
{
    float2 q = positions[vertex_id];
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    VOut out;
    out.position = float4(q, 0.0f, 1.0f);
    return out;
}

vertex VOut vs_v07_ops024(uint vertex_id [[vertex_id]],
                        const device float2 *positions [[buffer(0)]],
                        const device float4 *params [[buffer(1)]])
{
    float2 q = positions[vertex_id];
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    q = fma(q, params[0].xy, params[1].xy * float(4));
    q = fma(q, params[0].xy, params[1].xy * float(5));
    q = fma(q, params[0].xy, params[1].xy * float(6));
    q = fma(q, params[0].xy, params[1].xy * float(7));
    q = fma(q, params[0].xy, params[1].xy * float(1));
    q = fma(q, params[0].xy, params[1].xy * float(2));
    q = fma(q, params[0].xy, params[1].xy * float(3));
    VOut out;
    out.position = float4(q, 0.0f, 1.0f);
    return out;
}
