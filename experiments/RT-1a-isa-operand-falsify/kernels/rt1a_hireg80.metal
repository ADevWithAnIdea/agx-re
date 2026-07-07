#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]], const device int* v [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    int r[80];
    for (int k=0;k<80;k++) r[k] = v[gid*80+k];
    int acc = 0;
    for (int k=0;k<80;k++) acc ^= (r[k]*3 + 1);
    for (int k=0;k<80;k++) acc += (r[(k*7)%80] ^ r[(k*29+3)%80]);
    out[gid] = acc;
}
