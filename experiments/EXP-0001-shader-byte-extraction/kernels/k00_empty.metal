#include <metal_stdlib>
using namespace metal;

// Near-empty kernel: does nothing. Baseline / prolog+epilog only.
kernel void k(device float *out [[buffer(0)]],
              uint gid [[thread_position_in_grid]]) {
}
