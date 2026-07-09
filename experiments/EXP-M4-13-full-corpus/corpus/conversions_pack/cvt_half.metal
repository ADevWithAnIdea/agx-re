// conversions_pack: f32<->f16 up/down conversion + f16<->i32.
// Isolates narrowing f32->f16 (round), widening f16->f32, and half<->int converts.
#include <metal_stdlib>
using namespace metal;
kernel void cvt_half(device float* o [[buffer(0)]],
                     device const float* fa [[buffer(1)]],
                     device const half* ha [[buffer(2)]],
                     uint i [[thread_position_in_grid]]) {
    float f = fa[i];
    half  h = ha[i];
    half  a = half(f);           // f32 -> f16 (rounding narrow)
    float b = float(h);          // f16 -> f32 (widen)
    int   c = int(h);            // f16 -> i32
    half  d = half(c + 3);       // i32 -> f16
    o[i] = float(a) + b + float(c) + float(d);
}
