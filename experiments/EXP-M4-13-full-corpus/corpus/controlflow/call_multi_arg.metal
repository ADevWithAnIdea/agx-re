#include <metal_stdlib>
using namespace metal;
static int4 __attribute__((noinline)) mix4(int4 a, int4 b, int s){ return (a<<s) - (b>>1) + (a^b); }
kernel void k(device int4* o[[buffer(0)]], device const int4* a[[buffer(1)]], device const int4* b[[buffer(2)]], device const int* s[[buffer(3)]], uint i[[thread_position_in_grid]]){
    o[i]=mix4(a[i], b[i], s[i]&7);
}
