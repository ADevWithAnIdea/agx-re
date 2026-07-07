#include <metal_stdlib>
using namespace metal;
struct VO{float4 pos [[position]];};
vertex VO vid_vs(uint vid [[vertex_id]]){VO o;o.pos=float4(float(vid),0,0,1);return o;}
vertex VO iid_vs(uint iid [[instance_id]]){VO o;o.pos=float4(float(iid),0,0,1);return o;}
fragment float4 ff_fs(bool ff [[front_facing]]){return ff?float4(1,0,0,1):float4(0,0,1,1);}
