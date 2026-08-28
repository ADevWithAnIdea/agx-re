// EXP-0094 grad_probe.metal -- own MSL. Single-thread compute probe of the
// explicit gradient2d() operand (independent dx/dy, not compiler-symmetric).
//
// params[0..1] = dPdx (x,y);  params[2..3] = dPdy (x,y)
#include <metal_stdlib>
using namespace metal;

kernel void kmain(texture2d<float> tex [[texture(0)]],
                   sampler s [[sampler(0)]],
                   constant float *params [[buffer(0)]],
                   device float *out [[buffer(1)]]) {
    float2 dx = float2(params[0], params[1]);
    float2 dy = float2(params[2], params[3]);
    float v = tex.sample(s, float2(0.5, 0.5), gradient2d(dx, dy)).r;
    out[0] = v;
}
