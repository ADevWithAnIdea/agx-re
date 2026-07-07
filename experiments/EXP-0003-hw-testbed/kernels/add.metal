#include <metal_stdlib>
using namespace metal;

// out[i] = a[i] + b[i]  — the EXP-0003 round-trip test kernel.
// Byte-identical in structure to EXP-0001 k01_fadd, so the known float
// op-select byte sits at offset 0x22 of _agc.main (1c=add, 1d=mul).
kernel void k(device const float *a [[buffer(0)]],
              device const float *b [[buffer(1)]],
              device float *out [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = a[gid] + b[gid];
}
