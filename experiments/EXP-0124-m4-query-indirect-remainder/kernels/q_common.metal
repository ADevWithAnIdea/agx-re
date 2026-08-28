// EXP-0124 Group Q (P1.6 counter heap / occlusion / pipeline-statistics) kernels.
// Authored MSL, our own source, compiled via the public newLibraryWithSource: runtime
// path. Apple binary introspection: NONE.

#include <metal_stdlib>
using namespace metal;

// A fullscreen triangle covering the entire viewport with no vertex buffer needed
// (standard "big triangle" trick: clip-space vertices far outside [-1,1] on two axes
// still rasterize the full [-1,1]x[-1,1] region after clipping).
struct VOut { float4 pos [[position]]; float4 color; };

vertex VOut v_fullscreen(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    VOut o; o.pos = float4(p[vid], 0, 1); o.color = float4(1,1,1,1);
    return o;
}

fragment float4 f_white(VOut in [[stage_in]]) {
    return in.color;
}

// A degenerate triangle placed entirely outside clip space on all three vertices, so
// it is clipped away completely (zero coverage control for q_occ_zero_coverage).
vertex VOut v_offscreen(uint vid [[vertex_id]]) {
    float2 p[3] = { float2(5,5), float2(6,5), float2(5,6) };
    VOut o; o.pos = float4(p[vid], 0, 1); o.color = float4(1,1,1,1);
    return o;
}

fragment float4 f_noop_out(VOut in [[stage_in]]) {
    return float4(0,0,0,0);
}

// Spin kernel used to keep a command buffer demonstrably not-yet-completed for the
// q_avail "post_commit_unwaited" case: a per-thread sequential dependency chain (each
// iteration depends on the previous via a data-dependent multiply/xor) that the
// compiler cannot hoist or eliminate, calibrated in the harness by iteration count.
kernel void k_spin(device atomic_uint *out [[buffer(0)]],
                    constant uint &iters [[buffer(1)]],
                    uint tid [[thread_position_in_grid]])
{
    uint acc = tid + 1;
    for (uint i = 0; i < iters; i++) {
        acc = (acc * 2654435761u) ^ (acc >> 13);
    }
    atomic_store_explicit(out, acc, memory_order_relaxed);
}

// Trivial marker kernel for the smoke gate and q_caps' sanity dispatch.
kernel void k_marker(device atomic_uint *out [[buffer(0)]]) {
    atomic_fetch_add_explicit(out, 1, memory_order_relaxed);
}
