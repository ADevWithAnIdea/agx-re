#include <metal_stdlib>
using namespace metal;
// int_arith :: cmpsel_u32 -- isolates: full unsigned compare set -> select
kernel void m(device uint* o[[buffer(0)]],
              device const uint* a[[buffer(1)]],
              device const uint* b[[buffer(2)]],
              device const uint* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = uint(a[i]<b[i]) + 2u*uint(a[i]<=b[i]) + 4u*uint(a[i]>b[i]) + 8u*uint(a[i]>=b[i]) + 16u*uint(a[i]==b[i]) + 32u*uint(a[i]!=b[i]);
}
