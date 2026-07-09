#include <metal_stdlib>
using namespace metal;
// bfloat <-> {float, half, int, uint} conversions — surface bf16 cvt encodings.
kernel void kmain(device bfloat* o  [[buffer(0)]],
                  device float*  of [[buffer(1)]],
                  device const float* fin [[buffer(2)]],
                  device const half*  hin [[buffer(3)]],
                  device const int*   iin [[buffer(4)]],
                  device const uint*  uin [[buffer(5)]],
                  uint i [[thread_position_in_grid]]) {
    bfloat b0 = bfloat(fin[i]);
    bfloat b1 = bfloat(hin[i]);
    bfloat b2 = bfloat(iin[i]);
    bfloat b3 = bfloat(uin[i]);
    o[i]  = b0 + b1 + b2 + b3;
    of[i] = float(b0) + float(b1) + float(int(b2)) + float(uint(b3));
}
