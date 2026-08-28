#include <metal_stdlib>
using namespace metal;
// GLFS-A05 probe: e_early_discard
// Vertex shader emits a big screen-covering triangle whose z is a purely linear
// function of ndc.x (so rasterized/interpolated z is EXACTLY z=clamp((ndcx+1)/2,0,1)
// at every covered pixel -- a deterministic left(pass)/right(fail) depth gradient
// against a Less-compare, clear=0.5 depth attachment).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    float2 ndc = p * 2.0 - 1.0;
    float z = (ndc.x + 1.0) * 0.5;  // UNCLAMPED at vertices: the big-triangle trick
    // oversizes vertices beyond the visible NDC square on purpose; clamping the
    // per-vertex z here would distort the barycentric-interpolated in-triangle
    // gradient (verified empirically -- an earlier clamped version halved the
    // observed depth range). The offscreen part of the triangle where z>1 lies
    // entirely outside the visible x range and is clipped by the viewport, not by
    // this value.
    VOut o; o.pos = float4(ndc, z, 1.0); return o;
}
struct Rec { uint marker; uint ran; uint depth_bits; uint pad0; };
[[early_fragment_tests]]
fragment float4 f_main(float4 pos [[position]],
                        device atomic_uint *ctr [[buffer(0)]],
                        device Rec *out [[buffer(1)]],
                        constant uint2 &dims [[buffer(2)]])
{
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    atomic_fetch_add_explicit(&ctr[idx], 1u, memory_order_relaxed);
    out[idx].marker = idx + 1u;
    out[idx].ran = 1u;
    if (py < dims.y / 2u) { discard_fragment(); }
    
    out[idx].depth_bits = as_type<uint>(pos.z);
    return float4(0.75, 0.5, 0.25, 1.0);
}
