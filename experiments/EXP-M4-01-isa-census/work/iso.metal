#include <metal_stdlib>
using namespace metal;
// minimal isolations of the integer compare/minmax/select (low-nibble-2) group
kernel void i_max(device int* o, device const int* a, device const int* b, uint g[[thread_position_in_grid]]){ o[g]=max(a[g],b[g]); }
kernel void i_min(device int* o, device const int* a, device const int* b, uint g[[thread_position_in_grid]]){ o[g]=min(a[g],b[g]); }
kernel void u_max(device uint* o, device const uint* a, device const uint* b, uint g[[thread_position_in_grid]]){ o[g]=max(a[g],b[g]); }
kernel void i_sel(device int* o, device const int* a, device const int* b, uint g[[thread_position_in_grid]]){ o[g]=(a[g]<b[g])?a[g]:b[g]; }
kernel void i_cmp(device int* o, device const int* a, device const int* b, uint g[[thread_position_in_grid]]){ o[g]=(a[g]<b[g])?1:0; }
// force several results into distinct dst registers to sweep the high nibble
kernel void i_multi(device int* o, device const int* a, device const int* b, device const int* c, uint g[[thread_position_in_grid]]){
    int m0=max(a[g],b[g]); int m1=max(a[g],c[g]); int m2=max(b[g],c[g]); int m3=min(a[g],c[g]);
    o[g]=m0*1+m1*3+m2*5+m3*7;
}
