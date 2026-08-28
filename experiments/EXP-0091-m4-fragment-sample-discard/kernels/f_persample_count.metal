#include <metal_stdlib>
using namespace metal;
// GLFS-A07: [[sample_id]] forces per-sample shading. Each invocation atomically
// increments ctr[pixel*MAXS + sample_id]. Full-coverage triangle. Compared across
// sampleCount in {1,2,4}: expect exactly one increment per (pixel,sample) pair if
// the hardware truly launches one invocation per covered sample.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(float4 pos [[position]],
                        uint sid [[sample_id]],
                        device atomic_uint *ctr [[buffer(0)]],
                        constant uint3 &dims [[buffer(1)]]) { // dims=(W,H,MAXS)
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = (py * dims.x + px) * dims.z + sid;
    atomic_fetch_add_explicit(&ctr[idx], 1u, memory_order_relaxed);
    return float4(0.75, 0.5, 0.25, 1.0);
}
