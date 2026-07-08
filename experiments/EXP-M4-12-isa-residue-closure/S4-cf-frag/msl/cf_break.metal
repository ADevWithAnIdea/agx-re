#include <metal_stdlib>
using namespace metal;
kernel void k_iso(device int* o[[buffer(0)]], device const int* a[[buffer(1)]],
                  uint i[[thread_position_in_grid]]) {
    int acc=0;
    for (int j=0;j<a[i];j++){ acc += a[(i+j)&255]; if (acc>1000) break; if(a[j&255]<0) continue; acc+=1; }
    o[i] = acc;
}
