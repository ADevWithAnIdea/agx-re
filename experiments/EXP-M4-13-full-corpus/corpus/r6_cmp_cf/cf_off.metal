#include <metal_stdlib>
using namespace metal;
// if-body of increasing size; the forward jump_cond (skip-then) offset should grow.
kernel void o1(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int v=a[i]; int acc=0;
    if(v<50){ for(int k=0;k<v;k++) acc+=v*k; o[i]=acc; return; }
    o[i]=7;
}
kernel void o2(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int v=a[i]; int acc=0;
    if(v<50){ for(int k=0;k<v;k++){ acc+=v*k; acc^=v; acc-=k; } o[i]=acc; return; }
    o[i]=7;
}
kernel void o3(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], uint i[[thread_position_in_grid]]){
    int v=a[i]; int acc=0;
    if(v<50){ for(int k=0;k<v;k++){ acc+=v*k; acc^=v; acc-=k; acc*=3; acc+=k*k; acc^=(v<<2); acc-=v*7; } o[i]=acc; return; }
    o[i]=7;
}
