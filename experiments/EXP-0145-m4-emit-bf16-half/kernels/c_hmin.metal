// EXP-0145 carrier C6 -- AUTHORED BY US (clean-room OWN-SHADER). native fp16 min.
#include <metal_stdlib>
using namespace metal;
kernel void k(device half* out       [[buffer(0)]],
              device const half* a   [[buffer(1)]],
              device const half* b   [[buffer(2)]],
              uint g [[thread_position_in_grid]]) { out[g] = min(a[g], b[g]); }
