#include <metal_stdlib>
using namespace metal;
// bfloat transcendental path. NOTE: exp/log/sqrt/... have no bfloat overload — each
// promotes its bfloat arg to float and returns float, so we cast back per call. This
// captures the f32 transcendental + f32->bf16 rounding-cvt pattern the compiler emits.
kernel void kmain(device bfloat* o [[buffer(0)]],
                  device const bfloat* a [[buffer(1)]],
                  uint i [[thread_position_in_grid]]) {
    bfloat x = a[i];
    bfloat r = bfloat(exp(x))  + bfloat(log(x))  + bfloat(sqrt(x)) + bfloat(rsqrt(x))
             + bfloat(sin(x))  + bfloat(cos(x))  + bfloat(exp2(x)) + bfloat(log2(x));
    o[i] = r;
}
