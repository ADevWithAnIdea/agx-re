// EXP-0153: verbatim copy of experiments/EXP-0146-m4-emit-int-misc/kernels/k_u64sub.metal.
#include <metal_stdlib>
using namespace metal;
kernel void k(device const ulong *a [[buffer(0)]],
              device const ulong *b [[buffer(1)]],
              device ulong *out     [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] - b[gid];
}
