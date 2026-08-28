#include <metal_stdlib>
using namespace metal;
// Compute-side texture-class threadgroup_barrier -- resolves the current db.json
// ambiguity between the EXP-M4-13 "mem_texture 0x51/0xd1 pair, flags 0x0e" finding
// and the mem_fence doc-note claiming a byte+4==0x06 pixel_order-style pair.
kernel void k_main(texture2d<float, access::read_write> tex [[texture(0)]],
                    uint2 tid [[thread_position_in_grid]]) {
    float4 v = tex.read(tid);
    threadgroup_barrier(mem_flags::mem_texture);
    tex.write(v + 1.0, tid);
}
