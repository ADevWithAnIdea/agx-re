// EXP-0085 — MEM-13 texture-sample interlock probe (authored MSL).
// out[i] = tex.read(coord) consumed immediately by ALU, zero slack. Uses
// texture2d::read (integer texel fetch, no sampler/filtering ambiguity) so
// the expected value is exactly the authored texel content, bit-exact.
#include <metal_stdlib>
using namespace metal;

kernel void il_tex_alu(texture2d<float, access::read> tex [[texture(0)]],
                        device float* out [[buffer(0)]],
                        uint2 gid [[thread_position_in_grid]],
                        uint2 gsize [[threads_per_grid]]) {
    float4 v = tex.read(gid);
    uint lin = gid.y * gsize.x + gid.x;
    out[lin] = v.x * 2.0f + 1.0f;
}
