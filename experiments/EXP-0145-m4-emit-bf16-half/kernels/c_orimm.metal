// EXP-0145 carrier C10 -- AUTHORED BY US (clean-room OWN-SHADER). integer-logic
// move with an immediate tail (the byte+2==0x0f funary_imm form).
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* out [[buffer(0)]], device uint* a [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) { out[tid] = a[tid] | 0x100u; }
