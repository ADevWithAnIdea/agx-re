#include <metal_stdlib>
using namespace metal;

// Loops -> back-edge jump (0f 00 ...). Vary the loop body length so the
// back-edge OFFSET changes (isolates the offset field) while mid/tail stay.
kernel void loop_small(device int* o, device int* a, uint i [[thread_position_in_grid]]) {
    int s = 0;
    for (int k = 0; k < a[0]; ++k) { s += a[i]; }
    o[i] = s;
}
kernel void loop_big(device int* o, device int* a, uint i [[thread_position_in_grid]]) {
    int s = 0;
    for (int k = 0; k < a[0]; ++k) {
        s += a[i] * 3;
        s ^= a[i] << 1;
        s -= a[i] >> 2;
        s += a[i] & 7;
    }
    o[i] = s;
}
kernel void loop_nest(device int* o, device int* a, uint i [[thread_position_in_grid]]) {
    int s = 0;
    for (int k = 0; k < a[0]; ++k)
        for (int j = 0; j < a[1]; ++j)
            s += a[i] + k * j;
    o[i] = s;
}
// while loop
kernel void loop_while(device int* o, device int* a, uint i [[thread_position_in_grid]]) {
    int s = a[i];
    while (s > a[0]) { s -= a[1]; }
    o[i] = s;
}
