#include <metal_stdlib>
using namespace metal;
// GLFS-A08 primary litmus (texture, STRONG/protected). N overlapping fragments
// (drawn as N instances of a full-screen triangle covering the same 1x1 target)
// each perform a non-atomic read-modify-write increment of a shared read_write
// texture counter, protected by [[raster_order_group(0)]]. If raster-order
// serialization (mutual exclusion) holds, the final counter value equals
// exactly N regardless of scheduling. OUR OWN MSL.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment void f_main(texture2d<uint, access::read_write> ctr
                        [[raster_order_group(0), texture(0)]]) {
    uint v = ctr.read(uint2(0, 0)).r;
    ctr.write(uint4(v + 1u, 0, 0, 0), uint2(0, 0));
}
