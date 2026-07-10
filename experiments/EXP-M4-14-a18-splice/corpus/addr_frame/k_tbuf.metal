#include <metal_stdlib>
using namespace metal;
kernel void k(device uint* o[[buffer(0)]], texture_buffer<uint,access::read_write> tb[[texture(0)]],
              uint i[[thread_position_in_grid]]) {
    tb.atomic_fetch_add(i, 1u);
    o[i] = tb.read(i).x;
}
