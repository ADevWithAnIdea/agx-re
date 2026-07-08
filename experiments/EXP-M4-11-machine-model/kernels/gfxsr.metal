#include <metal_stdlib>
using namespace metal;
struct VO { float4 pos [[position]]; float v; };
vertex VO v_main(uint vid [[vertex_id]], uint iid [[instance_id]]) {
    VO o; o.pos = float4(0,0,0,1); o.v = float(vid) + float(iid); return o;
}
fragment float4 f_main(VO in [[stage_in]], bool ff [[front_facing]]) {
    return float4(in.v, ff ? 1.0 : 0.0, 0, 1);
}
