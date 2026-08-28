#include <metal_stdlib>
using namespace metal;

kernel void k0(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = 0u;
}

kernel void k1(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = (a_ & b_);
}

kernel void k2(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = (a_ & ~b_);
}

kernel void k3(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = a_;
}

kernel void k4(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = (~a_ & b_);
}

kernel void k5(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = b_;
}

kernel void k6(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = (a_ ^ b_);
}

kernel void k7(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = (a_ | b_);
}

kernel void k8(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = ~(a_ | b_);
}

kernel void k9(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = ~(a_ ^ b_);
}

kernel void k10(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = ~b_;
}

kernel void k11(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = (a_ | ~b_);
}

kernel void k12(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = ~a_;
}

kernel void k13(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = (~a_ | b_);
}

kernel void k14(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = ~(a_ & b_);
}

kernel void k15(device const uint *a [[buffer(0)]],
                device const uint *b [[buffer(1)]],
                device uint *out [[buffer(2)]],
                uint gid [[thread_position_in_grid]]) {
    uint a_ = a[gid]; uint b_ = b[gid];
    out[gid] = 0xFFFFFFFFu;
}
