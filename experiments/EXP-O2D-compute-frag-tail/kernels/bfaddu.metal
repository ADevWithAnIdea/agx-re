#include <metal_stdlib>
using namespace metal;
// bfloat add with uint bit-pattern I/O so the HW testbed can drive it and we keep
// a genuine bfloat (0x11-group) add. a[i]/b[i] hold bf16 bit patterns in the low 16b.
// add(1.0,2.0)=3.0 -> 0x4040 ; splice opsel 0x1c->0x1d gives mul -> 2.0 -> 0x4000.
kernel void bfaddu(device uint* o [[buffer(0)]],
                   device const uint* a [[buffer(1)]],
                   device const uint* b [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    bfloat x = as_type<bfloat>(ushort(a[i]));
    bfloat y = as_type<bfloat>(ushort(b[i]));
    o[i] = uint(as_type<ushort>(bfloat(x + y)));
}
kernel void bfmulu(device uint* o [[buffer(0)]],
                   device const uint* a [[buffer(1)]],
                   device const uint* b [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    bfloat x = as_type<bfloat>(ushort(a[i]));
    bfloat y = as_type<bfloat>(ushort(b[i]));
    o[i] = uint(as_type<ushort>(bfloat(x * y)));
}
