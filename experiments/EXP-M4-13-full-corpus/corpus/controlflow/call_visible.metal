#include <metal_stdlib>
using namespace metal;
static int __attribute__((noinline)) helper(int a, int b){ return (a*b) ^ (a+b); }
kernel void k(device int* o[[buffer(0)]], device const int* a[[buffer(1)]], device const int* b[[buffer(2)]], uint i[[thread_position_in_grid]]){
    o[i]=helper(a[i], b[i]);
}
