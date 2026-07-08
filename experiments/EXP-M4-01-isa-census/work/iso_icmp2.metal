#include <metal_stdlib>
using namespace metal;
// Loop with a conditional break + an early continue -> execution-mask divergence ->
// multiple predicate registers -> low-nibble-a icmp with high nibble = predicate reg.
kernel void k_iso_icmp2(device uint* o[[buffer(0)]], device const uint* a[[buffer(1)]],
                        uint i[[thread_position_in_grid]]) {
    uint x = a[i];
    uint acc = 0;
    for (uint k = 0; k < x; ++k) {
        if (k == 5u) continue;
        if (acc > 100u) break;
        acc += k * 2u + 1u;
    }
    o[i] = acc;
}
