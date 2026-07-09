#include <metal_stdlib>
using namespace metal;
// 16-bit ushort device load/store + 16-bit signed load with sign-extend.
kernel void k(device ushort* out [[buffer(0)]],
              device const ushort* in [[buffer(1)]],
              device const short* si [[buffer(2)]],
              device int* wide [[buffer(3)]],
              uint i [[thread_position_in_grid]]) {
    ushort v = in[i];
    wide[i] = int(si[i]);       // sign-extend 16->32
    out[i] = ushort(v + 5);
}
