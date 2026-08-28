// EXP-0145 carrier C4 -- AUTHORED BY US (clean-room OWN-SHADER).
// native bfloat buffers: both operands land in the TWO HALVES of ONE register,
// which is what makes the byte+4 half-select bits observable.
#include <metal_stdlib>
using namespace metal;
kernel void k(device bfloat* out       [[buffer(0)]],
              device const bfloat* a   [[buffer(1)]],
              device const bfloat* b   [[buffer(2)]],
              uint g [[thread_position_in_grid]]) { out[g] = a[g] * b[g]; }
