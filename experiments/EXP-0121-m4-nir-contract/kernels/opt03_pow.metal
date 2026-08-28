#include <metal_stdlib>
using namespace metal;
// OPT-03: does pow need a special-case fixup beyond exp2(y*log2(x))? Edge-case corpus
// (negative base, 0^0, x^0 for any x, negative-zero base with odd/even exponent, huge
// exponents) is supplied at runtime (buffers), never folded at compile time.
kernel void k_pow_builtin(device float* x [[buffer(0)]], device float* y [[buffer(1)]],
                           device float* out [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = pow(x[gid], y[gid]);
}
kernel void k_pow_manual(device float* x [[buffer(0)]], device float* y [[buffer(1)]],
                          device float* out [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = exp2(y[gid] * log2(x[gid]));
}
