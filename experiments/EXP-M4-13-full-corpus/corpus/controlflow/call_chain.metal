#include <metal_stdlib>
using namespace metal;
static int __attribute__((noinline)) inner(int x){ return x*x + 7; }
static int __attribute__((noinline)) outer(int x, int y){ return inner(x) - inner(y); }
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* b[[buffer(2)]], uint i[[thread_position_in_grid]]){
    o[i]=outer(a[i], b[i]);
}
