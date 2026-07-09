#include <metal_stdlib>
using namespace metal;
// Remainder / decomposition ops that are pure fp32 arithmetic (NOT transcendental):
// fmod, remainder, modf (integer+fraction split), and ldexp (scale by 2^n =
// exponent add). These reach for the rarer exponent/remainder ALU encodings.
kernel void k_fmod(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                   device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = fmod(a[i], b[i]);
}
// NOTE: metal::remainder() does NOT exist in MSL (metal_stdlib) — confirmed
// negative result (see compile_failures). Only fmod is exposed for fp remainder.
kernel void k_modf(device float* ofrac[[buffer(0)]], device float* oint[[buffer(1)]],
                   device const float* a[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    float ip;
    ofrac[i] = modf(a[i], ip);
    oint[i]  = ip;
}
kernel void k_ldexp(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                    device const int* n[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    o[i] = ldexp(a[i], n[i]);
}
kernel void k_frexp(device float* omant[[buffer(0)]], device int* oexp[[buffer(1)]],
                    device const float* a[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    int e;
    omant[i] = frexp(a[i], e);
    oexp[i]  = e;
}
