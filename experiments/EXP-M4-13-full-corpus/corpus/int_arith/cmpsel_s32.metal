#include <metal_stdlib>
using namespace metal;
// int_arith :: cmpsel_s32 -- isolates: full signed compare set -> select
kernel void m(device int* o[[buffer(0)]],
              device const int* a[[buffer(1)]],
              device const int* b[[buffer(2)]],
              device const int* c[[buffer(3)]],
              uint i[[thread_position_in_grid]]) {
    o[i] = (a[i]<b[i]) + 2*(a[i]<=b[i]) + 4*(a[i]>b[i]) + 8*(a[i]>=b[i]) + 16*(a[i]==b[i]) + 32*(a[i]!=b[i]);
}
