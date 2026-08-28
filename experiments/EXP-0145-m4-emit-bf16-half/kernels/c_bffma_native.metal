// EXP-0145 carrier C5 -- AUTHORED BY US (clean-room OWN-SHADER).
// native bfloat 3-source product-sum: the ONLY MSL shape found that makes the
// compiler emit the 10-byte bfloat fma (opsel 0x1e). `fma(bfloat,...)` does NOT.
#include <metal_stdlib>
using namespace metal;
kernel void k(device bfloat* out       [[buffer(0)]],
              device const bfloat* a   [[buffer(1)]],
              device const bfloat* b   [[buffer(2)]],
              device const bfloat* c   [[buffer(3)]],
              uint g [[thread_position_in_grid]]) { out[g] = a[g] * b[g] + c[g]; }
