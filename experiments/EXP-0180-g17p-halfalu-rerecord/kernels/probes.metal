// EXP-0180 authored probe kernels.
//
// Their ONLY job is to supply the two LIFT-CONTROL anchors: the byte-for-byte
// `half_alu_ext8` and `half_alu_fma12` instructions EXP-0169 lifted, so this experiment
// can reproduce EXP-0169's ladder failure on the same device in the same run and show
// that the repair -- not the device, not the day -- is what changed the outcome.
// `k_hadd` supplies the 6-byte sibling used as the instrument control and as the
// low-half seed writer's shape reference.
//
// CLEAN-ROOM: our own MSL. Every byte this experiment inspects or splices is the
// compiled form of the source in this file. No Apple source consulted.
#include <metal_stdlib>
using namespace metal;

kernel void k_hadd(device const half* a [[buffer(0)]],
                   device const half* b [[buffer(1)]],
                   device half* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] + b[g];                       // half_alu, 6B
}

kernel void k_hmul(device const half* a [[buffer(0)]],
                   device const half* b [[buffer(1)]],
                   device half* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = a[g] * b[g];                       // half_alu, 6B, opsel != hadd
}

kernel void k_hsat(device const half* a [[buffer(0)]],
                   device const half* b [[buffer(1)]],
                   device half* out [[buffer(2)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = saturate(a[g] + b[g]);             // half_alu_ext8, add+saturate instance
}

kernel void k_hfma(device const half* a [[buffer(0)]],
                   device const half* b [[buffer(1)]],
                   device const half* c [[buffer(2)]],
                   device half* out [[buffer(3)]],
                   uint g [[thread_position_in_grid]]) {
    out[g] = fma(a[g], b[g], c[g]);             // half_alu_ext8, fma instance (8B)
}

kernel void k_hfma_abs(device const half* a [[buffer(0)]],
                       device const half* b [[buffer(1)]],
                       device const half* c [[buffer(2)]],
                       device half* out [[buffer(3)]],
                       uint g [[thread_position_in_grid]]) {
    out[g] = fma(abs(a[g]), b[g], c[g]);        // half_alu_fma12, 12B abs form
}

kernel void k_hfma_satabs(device const half* a [[buffer(0)]],
                          device const half* b [[buffer(1)]],
                          device const half* c [[buffer(2)]],
                          device half* out [[buffer(3)]],
                          uint g [[thread_position_in_grid]]) {
    out[g] = saturate(fma(abs(a[g]), b[g], c[g]));   // half_alu_fma12 + saturate
}
