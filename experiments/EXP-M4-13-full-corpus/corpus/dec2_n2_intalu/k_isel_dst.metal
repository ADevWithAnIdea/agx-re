#include <metal_stdlib>
using namespace metal;
// 8 independent select results, all live, forcing 8 distinct dst regs
kernel void k_isel_dst(device int* out [[buffer(0)]], device const int* a [[buffer(1)]], device const int* b [[buffer(2)]], uint g [[thread_position_in_grid]]) {
  int r0 = a[g+0] < b[g+0] ? a[g+0] : b[g+0];
  int r1 = a[g+1] < b[g+1] ? 7 : 9;
  int r2 = a[g+2] > b[g+2] ? a[g+2] : b[g+2];
  int r3 = a[g+3] == b[g+3] ? a[g+3] : b[g+3];
  int r4 = a[g+4] != b[g+4] ? 1 : 0;
  int r5 = a[g+5] <= b[g+5] ? a[g+5] : b[g+5];
  int r6 = a[g+6] >= b[g+6] ? a[g+6] : b[g+6];
  int r7 = (uint)a[g+7] < (uint)b[g+7] ? a[g+7] : b[g+7];
  out[g+0]=r0;out[g+1]=r1;out[g+2]=r2;out[g+3]=r3;out[g+4]=r4;out[g+5]=r5;out[g+6]=r6;out[g+7]=r7;
}
