#include <metal_stdlib>
using namespace metal;

static inline float from_bits(uint bits) { return as_type<float>(bits); }
static inline uint to_bits(float value) { return as_type<uint>(value); }
static inline half half_from_bits(uint bits) { return as_type<half>(ushort(bits)); }
static inline uint half_to_bits(half value) { return uint(as_type<ushort>(value)); }

kernel void k_fidentity(device const uint *a [[buffer(0)]],
                        device uint *out [[buffer(2)]],
                        uint i [[thread_position_in_grid]]) {
    out[i] = to_bits(from_bits(a[i]));
}

kernel void k_fadd(device const uint *a [[buffer(0)]],
                   device const uint *b [[buffer(1)]],
                   device uint *out [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    out[i] = to_bits(from_bits(a[i]) + from_bits(b[i]));
}

kernel void k_fmul(device const uint *a [[buffer(0)]],
                   device const uint *b [[buffer(1)]],
                   device uint *out [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    out[i] = to_bits(from_bits(a[i]) * from_bits(b[i]));
}

kernel void k_fmin(device const uint *a [[buffer(0)]],
                   device const uint *b [[buffer(1)]],
                   device uint *out [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    out[i] = to_bits(fmin(from_bits(a[i]), from_bits(b[i])));
}

kernel void k_fmax(device const uint *a [[buffer(0)]],
                   device const uint *b [[buffer(1)]],
                   device uint *out [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    out[i] = to_bits(fmax(from_bits(a[i]), from_bits(b[i])));
}

kernel void k_rint(device const uint *a [[buffer(0)]],
                   device uint *out [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    out[i] = to_bits(rint(from_bits(a[i])));
}

kernel void k_round(device const uint *a [[buffer(0)]],
                    device uint *out [[buffer(2)]],
                    uint i [[thread_position_in_grid]]) {
    out[i] = to_bits(round(from_bits(a[i])));
}

kernel void k_hidentity(device const uint *a [[buffer(0)]],
                        device uint *out [[buffer(2)]],
                        uint i [[thread_position_in_grid]]) {
    out[i] = half_to_bits(half_from_bits(a[i]));
}

kernel void k_hadd(device const uint *a [[buffer(0)]],
                   device const uint *b [[buffer(1)]],
                   device uint *out [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    out[i] = half_to_bits(half_from_bits(a[i]) + half_from_bits(b[i]));
}

kernel void k_hmul(device const uint *a [[buffer(0)]],
                   device const uint *b [[buffer(1)]],
                   device uint *out [[buffer(2)]],
                   uint i [[thread_position_in_grid]]) {
    out[i] = half_to_bits(half_from_bits(a[i]) * half_from_bits(b[i]));
}
