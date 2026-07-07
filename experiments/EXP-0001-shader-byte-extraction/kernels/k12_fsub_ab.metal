#include <metal_stdlib>
using namespace metal;

// a - b. Minimal pair with k13_fsub_ba: subtraction is non-commutative, so
// swapping the operands forces the compiler to swap the two source-register
// fields in the ALU instruction -> localizes source-operand/register bits.
kernel void k(device const float *a [[buffer(0)]],
              device const float *b [[buffer(1)]],
              device float *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] - b[gid];
}
