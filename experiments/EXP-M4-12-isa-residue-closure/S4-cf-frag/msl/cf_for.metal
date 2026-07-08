#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]]) {
    int acc=0; int n = a[i] & 31;
    for (int j=0;j<n;j++) acc += a[(i+j)&255];
    o[i] = acc;
}
