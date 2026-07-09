#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int r=0;
    switch(a[i]&7){
        case 0: r+=1;
        case 1: r+=2;
        case 2: r+=4;
        case 3: r+=8; break;
        case 4: r+=16;
        case 5: r+=32; break;
        default: r+=64;
    }
    o[i]=r;
}
