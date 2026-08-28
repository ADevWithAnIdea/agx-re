#include <metal_stdlib>
using namespace metal;
// GLFS-A07 + GLFS-A03 cross-check: per-sample-shaded invocation; odd sample_id
// invocations call discard_fragment() (killing only THAT sample, not the whole
// pixel), all others survive. Records per-(pixel,sample) is_helper (pre/post) and
// an atomic ran-count, matching the general demote-probe schema, letting us confirm
// per-sample kill granularity and per-sample helper-status independently.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(float4 pos [[position]], uint sid [[sample_id]],
                        device atomic_uint *ctr [[buffer(0)]],
                        device uint *helperbuf [[buffer(1)]],
                        constant uint3 &dims [[buffer(2)]]) { // dims=(W,H,MAXS)
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = (py * dims.x + px) * dims.z + sid;
    bool pre = simd_is_helper_thread();
    if ((sid & 1u) == 1u) discard_fragment();
    bool post = simd_is_helper_thread();
    atomic_fetch_add_explicit(&ctr[idx], 1u, memory_order_relaxed);
    helperbuf[idx] = (pre ? 1u : 0u) | ((post ? 1u : 0u) << 1);
    return float4(1, 1, 1, 1);
}
