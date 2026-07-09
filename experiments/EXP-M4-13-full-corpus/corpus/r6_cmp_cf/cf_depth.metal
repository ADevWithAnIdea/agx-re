#include <metal_stdlib>
using namespace metal;
// forced-divergent nested ifs at controlled depth. Loop in innermost body defeats predication.
kernel void d1(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int v=a[i]; int acc=0;
    if(v<50){ for(int k=0;k<v;k++) acc+=v*k; o[i]=acc; return; }
    o[i]=7;
}
kernel void d2(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int v=a[i]; int acc=0;
    if(v<50){ if(v>10){ for(int k=0;k<v;k++) acc+=v*k; o[i]=acc; return; } }
    o[i]=7;
}
kernel void d3(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int v=a[i]; int acc=0;
    if(v<50){ if(v>10){ if(v!=25){ for(int k=0;k<v;k++) acc+=v*k; o[i]=acc; return; } } }
    o[i]=7;
}
kernel void d4(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int v=a[i]; int acc=0;
    if(v<50){ if(v>10){ if(v!=25){ if(v<40){ for(int k=0;k<v;k++) acc+=v*k; o[i]=acc; return; } } } }
    o[i]=7;
}
