#include <metal_stdlib>
using namespace metal;
// GLFS-A06 suppression matrix (single kernel, several channels probed together):
// even-x lanes discard_fragment() at top of shader; ALL lanes (including the
// discarded one) then unconditionally execute, in program order AFTER the
// discard/merge point:
//   1. a per-lane-UNIQUE device buffer store (buf[idx] -- no cross-lane race)
//   2. a global atomic increment (ctr[0])
//   3. a color output write
//   4. an explicit [[depth(any)]] output write
// Each lane's buffer slot is pre-poisoned by the harness with a fixed sentinel
// before the draw. Post-draw readback of buf[] directly shows, per lane, whether
// step 1's store reached memory (sentinel replaced) regardless of whether that
// lane's color/depth made it to the attachments. ctr[0] (compared against a
// no-discard control) shows whether the atomic increment executed for demoted
// lanes. depth/color readback (via the harness) show the classic write-suppressed
// channels for cross-reference.
struct FDOut { float4 color [[color(0)]]; float d [[depth(any)]]; };
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment FDOut f_main(float4 pos [[position]],
                       device uint *buf [[buffer(0)]],
                       device atomic_uint *ctr [[buffer(1)]],
                       constant uint2 &dims [[buffer(2)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    bool killme = (px & 1u) == 0u;
    if (killme) discard_fragment();
    buf[idx] = 0xC0FFEEu + idx;                       // 1. buffer store
    atomic_fetch_add_explicit(&ctr[0], 1u, memory_order_relaxed); // 2. atomic
    FDOut o;
    o.color = float4(0.75, 0.5, 0.25, 1.0);            // 3. color
    o.d = 0.1;                                         // 4. depth
    return o;
}
