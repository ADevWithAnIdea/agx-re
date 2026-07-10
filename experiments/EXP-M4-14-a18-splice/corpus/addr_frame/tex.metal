#include <metal_stdlib>
using namespace metal;
// exact census reproduction
kernel void k_tex_atomic(device uint* o[[buffer(0)]], texture2d<uint,access::read_write> t[[texture(0)]],
                        texture_buffer<uint,access::read_write> tb[[texture(1)]],
                        uint2 g[[thread_position_in_grid]]) {
    t.atomic_fetch_add(g, 1u);
    tb.atomic_fetch_add(g.x, 1u);
    t.atomic_fetch_max(g, g.x);
    o[g.x] = t.read(g).x;
}
// isolate: only 2D atomic add
kernel void k_add(device uint* o[[buffer(0)]], texture2d<uint,access::read_write> t[[texture(0)]],
                  uint2 g[[thread_position_in_grid]]) {
    t.atomic_fetch_add(g, 1u);
    o[g.x] = t.read(g).x;
}
// isolate: only 2D atomic max
kernel void k_max(device uint* o[[buffer(0)]], texture2d<uint,access::read_write> t[[texture(0)]],
                  uint2 g[[thread_position_in_grid]]) {
    t.atomic_fetch_max(g, g.x);
    o[g.x] = t.read(g).x;
}
// isolate: only 2D read
kernel void k_read(device uint* o[[buffer(0)]], texture2d<uint,access::read_write> t[[texture(0)]],
                   uint2 g[[thread_position_in_grid]]) {
    o[g.x] = t.read(g).x;
}
// coord fixed y=0
kernel void k_addy0(device uint* o[[buffer(0)]], texture2d<uint,access::read_write> t[[texture(0)]],
                    uint g[[thread_position_in_grid]]) {
    t.atomic_fetch_add(uint2(g,0), 1u);
    o[g] = t.read(uint2(g,0)).x;
}
