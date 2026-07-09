// conversions_pack: floating-point rounding-mode operators (distinct round opcodes/modes).
// Isolates floor, ceil, trunc, round(half-away), rint(nearest-even) on f32 and f16.
#include <metal_stdlib>
using namespace metal;
kernel void round_modes(device float* o [[buffer(0)]],
                        device const float* fa [[buffer(1)]],
                        device const half* ha [[buffer(2)]],
                        uint i [[thread_position_in_grid]]) {
    float f = fa[i];
    half  h = ha[i];
    float a = floor(f);
    float b = ceil(f);
    float c = trunc(f);
    float d = round(f);          // round half away from zero
    float e = rint(f);           // round to nearest even
    half  g = floor(h);
    half  k = rint(h);
    o[i] = a + b + c + d + e + float(g) + float(k);
}
