// EXP-0113 H3 buffer-signature carrier, 2-buffer variant. OWN MSL.
// (Text intentionally close to kernels/carrier.metal but not required to
// be byte-identical -- this experiment's own H3 group re-derives its own
// CARRIER_LEN per variant, see baseline.py.)
#include <metal_stdlib>
using namespace metal;
kernel void k(device float* out [[buffer(0)]],
              device float* mem [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid] = mem[tid] + 1.0;
}
