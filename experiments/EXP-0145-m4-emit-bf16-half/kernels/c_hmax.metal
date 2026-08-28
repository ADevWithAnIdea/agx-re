// EXP-0145 carrier C7 -- AUTHORED BY US (clean-room OWN-SHADER). native fp16 max.
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* out       [[buffer(0)]],
              device const half* a   [[buffer(1)]],
              device const half* b   [[buffer(2)]],
              uint g [[thread_position_in_grid]]) { out[g] = max(a[g], b[g]); }
