#include <metal_stdlib>
using namespace metal;
// D7: even-x lanes discard, then (after discard) compute a distinctive per-lane
// marker value (px*1000+py) and store it into their OWN local register. Every lane
// (including the discarded one) then attempts quad_shuffle to read its
// quad-x-neighbor's marker. Odd-x survivors write the shuffled-in value they
// received from their (even-x, discarded) neighbor -- revealing whether a quad op
// sourced from a demoted lane returns that lane's live post-discard-computed value,
// a frozen pre-discard value, or an undefined/garbage/zero result.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct Rec { uint marker; uint shuffled_from_neighbor; uint own_marker; uint pad0; };
fragment float4 f_main(float4 pos [[position]],
                        device Rec *out [[buffer(0)]],
                        constant uint2 &dims [[buffer(1)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    bool killme = (px & 1u) == 0u;
    if (killme) discard_fragment();
    uint own = px * 1000u + py + 7777u;   // distinctive post-discard-computed value
    // quad_shuffle_xor(v,1) swaps within the 2x2 quad's x-pair.
    uint neighbor = quad_shuffle_xor(own, 1);
    out[idx].marker = idx + 1u;
    out[idx].shuffled_from_neighbor = neighbor;
    out[idx].own_marker = own;
    out[idx].pad0 = 0u;
    return float4(0.75, 0.5, 0.25, 1.0);
}
