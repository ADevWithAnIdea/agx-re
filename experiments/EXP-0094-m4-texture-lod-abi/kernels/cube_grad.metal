// EXP-0094 cube_grad.metal -- own MSL. Single-thread compute probe of explicit
// cube gradients (gradientcube), using the LOD-recovery texture (every
// face/level constant-filled with float(level)) to read back the CONTINUOUS
// effective LOD the hardware selected for a given direction + 3-component
// dPdx/dPdy.
//
// params[0..2] = direction (x,y,z)
// params[3..5] = dPdx (x,y,z)
// params[6..8] = dPdy (x,y,z)
#include <metal_stdlib>
using namespace metal;

kernel void kmain(texturecube<float> tex [[texture(0)]],
                   sampler s [[sampler(0)]],
                   constant float *params [[buffer(0)]],
                   device float *out [[buffer(1)]]) {
    float3 dir  = float3(params[0], params[1], params[2]);
    float3 dPdx = float3(params[3], params[4], params[5]);
    float3 dPdy = float3(params[6], params[7], params[8]);
    float v = tex.sample(s, dir, gradientcube(dPdx, dPdy)).r;
    out[0] = v;
}
