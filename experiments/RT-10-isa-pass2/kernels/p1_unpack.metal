#include <metal_stdlib>
using namespace metal;
// RT-10 Part1: unpack_convert. RT-ISA-FIX used unorm; use SNORM to force the 0x17/byte+1=0x04 path
// distinctly from ballot (0x17/byte+1 low-nibble 0x7).
kernel void k(device float2* out [[buffer(0)]],
              device const uint* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    out[tid] = unpack_snorm2x16_to_float(in[tid]);
}
