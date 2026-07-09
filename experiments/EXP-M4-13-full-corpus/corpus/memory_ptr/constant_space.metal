#include <metal_stdlib>
using namespace metal;
// constant address-space load (uniform buffer) with a per-thread index.
struct Uni { float scale; float bias; uint n; };
kernel void k(constant Uni& u [[buffer(0)]],
              constant float* coef [[buffer(1)]],
              device float* out [[buffer(2)]],
              uint i [[thread_position_in_grid]]) {
    float c = coef[i % u.n];
    out[i] = c * u.scale + u.bias;
}
