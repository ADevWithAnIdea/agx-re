// EXP-0094 cube_faceid.metal -- own MSL. Single-thread compute probe of cube
// face selection: explicit level(0) (no LOD ambiguity), reads back the raw
// RGBA of whichever face/texel the hardware selected for the given direction.
//
// params[0..2] = direction (x,y,z)
#include <metal_stdlib>
using namespace metal;

kernel void kmain(texturecube<float> tex [[texture(0)]],
                   sampler s [[sampler(0)]],
                   constant float *params [[buffer(0)]],
                   device float *out [[buffer(1)]]) {
    float3 dir = float3(params[0], params[1], params[2]);
    float4 v = tex.sample(s, dir, level(0));
    out[0] = v.r; out[1] = v.g; out[2] = v.b; out[3] = v.a;
}
