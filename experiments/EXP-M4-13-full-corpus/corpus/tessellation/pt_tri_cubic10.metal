#include <metal_stdlib>
using namespace metal;
struct CP { float4 pos; };
struct VOut { float4 position [[position]]; };
[[patch(triangle, 10)]]
vertex VOut vMain(const device CP* cp [[buffer(0)]], uint pid [[patch_id]],
                  float3 uvw [[position_in_patch]]) {
    float u=uvw.x, v=uvw.y, w=uvw.z;
    const device CP* p = cp + pid*10;
    // cubic Bezier triangle: sum b_ijk * (3!/(i!j!k!)) u^i v^j w^k
    float4 P =
        p[0].pos*(u*u*u) + p[1].pos*(v*v*v) + p[2].pos*(w*w*w) +
        p[3].pos*(3.0*u*u*v) + p[4].pos*(3.0*u*v*v) +
        p[5].pos*(3.0*v*v*w) + p[6].pos*(3.0*v*w*w) +
        p[7].pos*(3.0*w*w*u) + p[8].pos*(3.0*w*u*u) +
        p[9].pos*(6.0*u*v*w);
    VOut o; o.position = P; return o;
}
fragment float4 fMain(VOut i [[stage_in]]) { return i.position; }
