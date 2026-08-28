#include <metal_stdlib>
using namespace metal;
// FS-04: is the derivative computed over the hardware 2x2 quad specifically (not some
// other pixel grouping)? A step function of screen position (threshold via a uniform)
// is differenced with dfdx/dfdy. axis=0 tests X (dfdx), axis=1 tests Y (dfdy).
// threshold=1.0 splits the FIRST quad-pair (rows/cols 0|1) internally (a genuine local
// step inside one quad -> derivative must be nonzero there); threshold=2.0 splits
// EXACTLY at the boundary BETWEEN quad-pair 0 (0,1) and quad-pair 1 (2,3) -- if
// derivatives are quad-LOCAL, both quad-pairs individually see a CONSTANT value (no
// internal step) and must read a ZERO derivative even though a "global" step exists
// between the pairs. Oracle (quad-local hypothesis): threshold=1.0 -> d=1000 for
// rows/cols {0,1}, d=0 for {2,3}; threshold=2.0 -> d=0 for ALL rows/cols.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(float4 pos [[position]],
                        device uint *buf [[buffer(0)]],
                        constant uint2 &axis_thresh [[buffer(1)]],
                        constant uint2 &dims [[buffer(2)]]) {
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    uint axis = axis_thresh.x;
    float thresh = as_type<float>(axis_thresh.y);
    float coord = (axis == 0) ? pos.x : pos.y;
    float v = (coord >= thresh) ? 1000.0 : 0.0;
    float d = (axis == 0) ? dfdx(v) : dfdy(v);
    buf[idx] = as_type<uint>(d);
    return float4(0,0,0,1);
}
