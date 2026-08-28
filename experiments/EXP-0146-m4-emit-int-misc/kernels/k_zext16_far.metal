#include <metal_stdlib>
using namespace metal;
// EXP-0146 P3: the 16-bit zero-extend's source is NOT the immediately preceding load --
// an arithmetic result several instructions away -- so byte+1 cannot be satisfied by an
// ALU-forward of the previous load.
kernel void k(device const uint *a [[buffer(0)]],
              device const uint *b [[buffer(1)]],
              device uint *out     [[buffer(2)]],
              uint gid [[thread_position_in_grid]]) {
    uint t = a[gid] * 3u + b[gid];
    uint u = t ^ 0x5A5A5A5Au;
    out[gid] = uint(ushort(u)) + (u & 0xFFFF0000u);
}
