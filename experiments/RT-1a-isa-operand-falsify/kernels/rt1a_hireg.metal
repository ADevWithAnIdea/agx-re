#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], const device int* v [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    int r[40];
    for (int k=0;k<40;k++) r[k] = v[gid*40+k];
    // expression that keeps all 40 live simultaneously (each used twice, non-reducible)
    int acc = 0;
    for (int k=0;k<40;k++) acc ^= (r[k]*3 + 1);
    for (int k=0;k<40;k++) acc += (r[(k*7)%40] ^ r[(k*13+3)%40]);
    out[gid] = acc;
}
