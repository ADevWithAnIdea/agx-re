#include <metal_stdlib>
using namespace metal;
// Isolate the read_write texture READ path.
kernel void k_iso_texread(device uint* o[[buffer(0)]],
                          texture2d<uint,access::read_write> t[[texture(0)]],
                          uint2 g[[thread_position_in_grid]]) {
    o[g.x] = t.read(g).x;
}
// Isolate a single texture atomic add.
kernel void k_iso_texatomic(device uint* o[[buffer(0)]],
                            texture2d<uint,access::read_write> t[[texture(0)]],
                            uint2 g[[thread_position_in_grid]]) {
    t.atomic_fetch_add(g, 1u);
}
// Isolate a coordinate pack (uint2 -> combined) feeding a plain sampled read.
kernel void k_iso_texld(device uint* o[[buffer(0)]],
                        texture2d<uint,access::read> t[[texture(0)]],
                        uint2 g[[thread_position_in_grid]]) {
    o[g.x] = t.read(g).x;
}
