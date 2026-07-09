// OWN-SHADER. Isolate mixed half/float expressions forcing inline up/down converts.
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* o[[buffer(0)]],
              device const half* h[[buffer(1)]],
              device const float* f[[buffer(2)]],
              uint i[[thread_position_in_grid]]) {
    half  hx = h[i];
    float fx = f[i];
    // each mixed op forces a f16<->f32 conversion at a different spot
    float m0 = float(hx) * fx;          // promote then mul
    half  m1 = hx + half(fx);           // demote then add (half domain)
    float m2 = fma(float(hx), fx, float(hx * hx)); // half mul feeds float fma
    half  m3 = half(fx) * hx + hx;      // half mad after demote
    float m4 = mix(float(hx), fx, 0.25f);
    o[i] = m0 + float(m1) + m2 + float(m3) + m4;
}
