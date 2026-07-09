#include <metal_stdlib>
using namespace metal;
static int __attribute__((noinline)) step(int acc, int x){ return acc + x*x - (x>>1); }
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]){
    int acc=0; int cnt=n[i];
    for(int j=0;j<cnt;j++) acc=step(acc, a[j]);
    o[i]=acc;
}
