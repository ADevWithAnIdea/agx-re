// EXP-0113 H3 buffer-signature carrier, 1-buffer variant. OWN MSL.
// Same splice-target role as kernels/carrier.metal (own arithmetic never
// executed by any H3 case; exists only to fix the compiled kernel's own
// argument/uniform-file layout at exactly ONE bound buffer).
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid] = float(tid) + 1.0;
}
