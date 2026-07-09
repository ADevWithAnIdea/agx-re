// EXP-M4-13 R2 n7: 0x27 ibfins byte+1==0x00 (bitfield-insert form).
#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]], device const uint* b[[buffer(2)]], uint i[[thread_position_in_grid]]){ o[i]=insert_bits(a[i], b[i], 3u, 6u); }
