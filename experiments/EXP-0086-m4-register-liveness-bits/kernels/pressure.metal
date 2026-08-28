#include <metal_stdlib>
using namespace metal;
kernel void k(device float* a [[buffer(0)]],
              device float* out [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float v = a[tid];
    float x1 = v + 10.0f;
    float f0 = a[tid+1] + 0.0010f;
    float f1 = a[tid+2] + 0.0020f;
    float f2 = a[tid+3] + 0.0030f;
    float f3 = a[tid+4] + 0.0040f;
    float f4 = a[tid+5] + 0.0050f;
    float f5 = a[tid+6] + 0.0060f;
    float f6 = a[tid+7] + 0.0070f;
    float f7 = a[tid+8] + 0.0080f;
    float f8 = a[tid+9] + 0.0090f;
    float f9 = a[tid+10] + 0.0100f;
    float f10 = a[tid+11] + 0.0110f;
    float f11 = a[tid+12] + 0.0120f;
    float f12 = a[tid+13] + 0.0130f;
    float f13 = a[tid+14] + 0.0140f;
    float f14 = a[tid+15] + 0.0150f;
    float f15 = a[tid+16] + 0.0160f;
    float f16 = a[tid+17] + 0.0170f;
    float f17 = a[tid+18] + 0.0180f;
    float f18 = a[tid+19] + 0.0190f;
    float f19 = a[tid+20] + 0.0200f;
    float f20 = a[tid+21] + 0.0210f;
    float f21 = a[tid+22] + 0.0220f;
    float f22 = a[tid+23] + 0.0230f;
    float f23 = a[tid+24] + 0.0240f;
    float f24 = a[tid+25] + 0.0250f;
    float f25 = a[tid+26] + 0.0260f;
    float f26 = a[tid+27] + 0.0270f;
    float f27 = a[tid+28] + 0.0280f;
    float f28 = a[tid+29] + 0.0290f;
    float f29 = a[tid+30] + 0.0300f;
    float f30 = a[tid+31] + 0.0310f;
    float f31 = a[tid+32] + 0.0320f;
    float f32 = a[tid+33] + 0.0330f;
    float f33 = a[tid+34] + 0.0340f;
    float f34 = a[tid+35] + 0.0350f;
    float f35 = a[tid+36] + 0.0360f;
    float f36 = a[tid+37] + 0.0370f;
    float f37 = a[tid+38] + 0.0380f;
    float f38 = a[tid+39] + 0.0390f;
    float f39 = a[tid+40] + 0.0400f;
    float x2 = v + 20.0f;
    float sum = f0 + f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9 + f10 + f11 + f12 + f13 + f14 + f15 + f16 + f17 + f18 + f19 + f20 + f21 + f22 + f23 + f24 + f25 + f26 + f27 + f28 + f29 + f30 + f31 + f32 + f33 + f34 + f35 + f36 + f37 + f38 + f39;
    out[tid*3+0] = x1;
    out[tid*3+1] = x2;
    out[tid*3+2] = sum;
}
