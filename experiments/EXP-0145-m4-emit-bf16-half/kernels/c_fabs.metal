// EXP-0145 carrier C9 -- AUTHORED BY US (clean-room OWN-SHADER). float source-modifier move.
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]], device float* a [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) { out[tid] = fabs(a[tid]); }
