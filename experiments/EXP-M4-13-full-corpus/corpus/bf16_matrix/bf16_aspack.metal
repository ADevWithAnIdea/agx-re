#include <metal_stdlib>
using namespace metal;
// bfloat bit reinterpret (as_type) — bf16<->ushort raw bit moves, no numeric cvt.
kernel void kmain(device ushort* o  [[buffer(0)]],
                  device bfloat* ob [[buffer(1)]],
                  device const bfloat* a  [[buffer(2)]],
                  device const ushort* uin [[buffer(3)]],
                  uint i [[thread_position_in_grid]]) {
    ushort raw  = as_type<ushort>(a[i]);
    bfloat back = as_type<bfloat>(uin[i]);
    o[i]  = raw ^ 0x8000;      // flip sign bit in raw storage
    ob[i] = back;
}
