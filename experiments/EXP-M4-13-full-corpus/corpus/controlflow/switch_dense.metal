#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int r;
    switch(a[i]&15){
        case 0: r=1; break; case 1: r=4; break; case 2: r=9; break; case 3: r=16; break;
        case 4: r=25; break; case 5: r=36; break; case 6: r=49; break; case 7: r=64; break;
        case 8: r=81; break; case 9: r=100; break; case 10: r=121; break; case 11: r=144; break;
        case 12: r=169; break; case 13: r=196; break; case 14: r=225; break; default: r=256; break;
    }
    o[i]=r;
}
