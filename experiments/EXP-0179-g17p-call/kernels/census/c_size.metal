// EXP-0179 census: constructs with NO inlining attribute at all, where the shape
// of the program is the only thing pushing toward an out-of-line call.
// CLEAN-ROOM: our own MSL. We report per-construct outcomes only; we make no
// claim about WHY a construct inlined (declared clean-room boundary).
#include <metal_stdlib>
using namespace metal;

// C10 large body, no attribute.
static float h_big(float a, float b) {
    float acc = a;
    float x = b;
    for (int k = 0; k < 64; ++k) {
        acc = acc * 1.5f + x;
        x = x + acc * 0.5f;
        acc = fma(acc, 0.75f, x);
        x = fma(x, 1.25f, acc);
    }
    return acc + x;
}
kernel void k_bigbody(device const float* A [[buffer(0)]],
                      device const float* B [[buffer(1)]],
                      device float* O [[buffer(2)]],
                      uint i [[thread_position_in_grid]]) {
    O[i] = h_big(A[i], B[i]);
}

// C11 a moderately large body called from TWELVE sites, no attribute.
static float h_mid(float a, float b) {
    float t = a;
    for (int k = 0; k < 12; ++k) { t = t * 1.03f + b; b = b * 0.97f + t; }
    return t + b;
}
kernel void k_manysites(device const float* A [[buffer(0)]],
                        device float* O [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) {
    float s = 0.0f;
    for (uint j = 0; j < 12; ++j) s += h_mid(A[12*i+j], A[12*i+((j+1)%12)]);
    O[i] = s;
}
