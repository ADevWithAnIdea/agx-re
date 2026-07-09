#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int r;
    switch(a[i]&3){
        case 0: r=10; break;
        case 1: r=20; break;
        case 2: r=30; break;
        default: r=40; break;
    }
    o[i]=r;
}
