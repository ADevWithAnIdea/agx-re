#include <metal_stdlib>
using namespace metal;
// Floating-point classification: isnan, isinf, isfinite, isnormal, signbit.
// These are the highest-value probes here — under fast-math they may fold to
// constants, so this file is intended to ALSO be compiled --no-fast-math where
// the real classify opcodes (unordered compare, exponent test) appear.
kernel void k_isnan(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                    uint i[[thread_position_in_grid]]) {
    o[i] = isnan(a[i]) ? 1.0f : 0.0f;
}
kernel void k_isinf(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                    uint i[[thread_position_in_grid]]) {
    o[i] = isinf(a[i]) ? 1.0f : 0.0f;
}
kernel void k_isfinite(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                       uint i[[thread_position_in_grid]]) {
    o[i] = isfinite(a[i]) ? 1.0f : 0.0f;
}
kernel void k_isnormal(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                       uint i[[thread_position_in_grid]]) {
    o[i] = isnormal(a[i]) ? 1.0f : 0.0f;
}
kernel void k_signbit(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                      uint i[[thread_position_in_grid]]) {
    o[i] = signbit(a[i]) ? 1.0f : 0.0f;
}
kernel void k_isunordered(device float* o[[buffer(0)]], device const float* a[[buffer(1)]],
                          device const float* b[[buffer(2)]], uint i[[thread_position_in_grid]]) {
    // unordered compare: true iff either operand is NaN
    o[i] = (isnan(a[i]) || isnan(b[i])) ? 1.0f : 0.0f;
}
