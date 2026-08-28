#include <metal_stdlib>
using namespace metal;
// FS-02: are pixel coordinates stable across samples in a per-sample-shaded MSAA
// fragment shader? Full-coverage geometry, [[sample_id]] declared (forces per-sample
// invocation, EXP-0091 GLFS-A07), each of the N invocations for a pixel records its own
// [[position]].xy raw bits into a (pixel,sample)-indexed buffer slot. Oracle: identical
// pos.xy across all N samples of the same pixel (position is defined as the pixel
// center regardless of which sample is being shaded).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(float4 pos [[position]], uint sid [[sample_id]],
                        device uint *buf [[buffer(0)]],
                        constant uint3 &dims [[buffer(1)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = (py * dims.x + px) * dims.z + sid;
    buf[idx*2+0] = as_type<uint>(pos.x);
    buf[idx*2+1] = as_type<uint>(pos.y);
    return float4(0,0,0,1);
}
