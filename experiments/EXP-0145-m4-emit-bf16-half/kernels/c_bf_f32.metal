// EXP-0145 carrier C1 -- AUTHORED BY US (clean-room OWN-SHADER).
// float32 in/out, native bfloat compute: provokes the byte0-low-nibble-1
// bfloat ALU with BOTH operands in the LOW half of two DIFFERENT registers.
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* a   [[buffer(1)]],
              device float* b   [[buffer(2)]],
              uint tid [[thread_position_in_grid]]) {
    bfloat x = bfloat(a[tid]);
    bfloat y = bfloat(b[tid]);
    out[tid] = float(x + y);
}
