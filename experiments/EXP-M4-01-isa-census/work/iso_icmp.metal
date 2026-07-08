#include <metal_stdlib>
using namespace metal;
// Nested/independent predicated branches -> compiler allocates several predicate
// registers -> some icmp ops get byte0 low-nibble a with a NON-zero high nibble
// (dst = predicate reg). Output is a simple function of which lanes took which branch.
kernel void k_iso_icmp(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                       uint i[[thread_position_in_grid]]) {
    uint x = a[i];
    uint r = 0;
    if (x > 3u)  r += 1u;
    if (x > 7u)  r += 2u;
    if (x > 11u) r += 4u;
    if (x > 15u) r += 8u;
    o[i] = r;
}
