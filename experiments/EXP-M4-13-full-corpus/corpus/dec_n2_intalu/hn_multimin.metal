#include <metal_stdlib>
using namespace metal;
// force several independent, simultaneously-live signed-min results
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              uint i[[thread_position_in_grid]]) {
    int m0 = min(a[i+0], b[i+0]);
    int m1 = min(a[i+1], b[i+1]);
    int m2 = min(a[i+2], b[i+2]);
    int m3 = min(a[i+3], b[i+3]);
    int m4 = min(a[i+4], b[i+4]);
    int m5 = min(a[i+5], b[i+5]);
    // combine so all stay live (max chain reads each once)
    o[i] = m0 ^ (m1<<1) ^ (m2<<2) ^ (m3<<3) ^ (m4<<4) ^ (m5<<5);
}
