#include <metal_stdlib>
using namespace metal;
kernel void mm3(device int* o, device const int* a, device const int* b, device const int* c, uint g[[thread_position_in_grid]]){
    int x=a[g],y=b[g],z=c[g]; o[g]=min3(x,y,z)+max3(x,y,z)+median3(x,y,z)+clamp(x,y,z);
}
kernel void l_add(device long* o, device const long* a, device const long* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]+b[g]; }
kernel void l_sub(device long* o, device const long* a, device const long* b, uint g[[thread_position_in_grid]]){ o[g]=a[g]-b[g]; }
kernel void l_cmp(device long* o, device const long* a, device const long* b, uint g[[thread_position_in_grid]]){ o[g]=(a[g]<b[g])?a[g]:b[g]; }
kernel void i_selreg(device int* o, device const int* a, device const int* b, device const int* c, device const int* d, uint g[[thread_position_in_grid]]){
    o[g]=(a[g]<b[g])?c[g]:d[g];
}
