#include <metal_stdlib>
using namespace metal;
// Anomaly (a) second method: EXP-0091 GLFS-A03 found helper_pre (helper status read
// BEFORE a lane's own discard_fragment() call) spatially non-uniform in a single-run
// supplementary probe (2 of 8 relayed lanes read TRUE instead of the expected FALSE),
// relayed via quad_shuffle_xor because the discarding lane's OWN write is suppressed
// (GLFS-A06) -- flagged as possibly a quad_shuffle-relay artifact, not necessarily a
// real pre-discard helper-status fact.
//
// Second, INDEPENDENT method: write helper_pre DIRECTLY (no shuffle relay at all) to a
// per-lane-unique buffer slot BEFORE the discard_fragment() call in program order. Per
// GLFS-A06, suppression applies to writes issued AFTER a lane's own discard; a write
// issued strictly BEFORE it (in program order, same lane) is not yet subject to that
// lane's own kill state and should reach memory normally regardless of whether this
// SAME lane goes on to discard immediately afterward. This eliminates quad_shuffle_xor
// (and its lane-pairing/scheduling assumptions) from the measurement entirely.
// Every lane (both those that will and won't discard) writes its own helper_pre.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(float4 pos [[position]], device uint *buf [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    bool helper_pre = simd_is_helper_thread();
    buf[idx] = helper_pre ? 1u : 0u;     // written BEFORE any discard, every lane
    bool killme = (px & 1u) == 0u;
    if (killme) discard_fragment();
    return float4(0,0,0,1);
}
