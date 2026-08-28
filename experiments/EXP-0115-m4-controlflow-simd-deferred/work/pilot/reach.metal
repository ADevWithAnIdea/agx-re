#include <metal_stdlib>
using namespace metal;
kernel void reach_loop(device int* o [[buffer(0)]],
                        device const int* a [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) {
    int v = a[i];
    int s = 1;
    for (int k = 0; k < v; k++) { s = s * 3 + 1; }
    o[i] = s;
}
