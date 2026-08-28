#include <metal_stdlib>
using namespace metal;
kernel void ifnest_004(device int* o [[buffer(0)]],
                    device const int* a [[buffer(1)]],
                    uint i [[thread_position_in_grid]]) {
    int v = a[i];
    if (v > 1) {
    if (v > 2) {
    if (v > 3) {
    if (v > 4) {
    int acc = 0;
    for (int k = 0; k < v; k++) { acc += v; }
    o[i] = acc;
    } else {
    o[i] = -(1000 + 4);
    return;
    }
    } else {
    o[i] = -(1000 + 3);
    return;
    }
    } else {
    o[i] = -(1000 + 2);
    return;
    }
    } else {
    o[i] = -(1000 + 1);
    return;
    }
}
