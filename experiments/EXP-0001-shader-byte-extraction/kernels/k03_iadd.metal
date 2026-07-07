#include <metal_stdlib>
using namespace metal;

// int32 add. Minimal pair with k04_imul (only the operator differs);
// also compares against k01_fadd (int vs float add, same shape).
kernel void k(device const int *a [[buffer(0)]],
              device const int *b [[buffer(1)]],
              device int *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}
