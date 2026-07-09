#include <metal_stdlib>
using namespace metal;
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int v=a[i]; int r;
    if(v<10){ if(v<5){ if(v<2) r=1; else r=2; } else { if(v<8) r=3; else r=4; } }
    else { if(v<20){ if(v<15) r=5; else r=6; } else { if(v<30) r=7; else r=8; } }
    o[i]=r;
}
