#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]]) {
    int acc=a[i]; int k=0;
    while (acc > 100) { acc -= 7; k++; }
    o[i] = acc + k;
}
