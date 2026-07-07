// EXP-0022 EMULATED CONTROL: hand-written FMA matmul of the SAME 8x8 shape.
// Diffed against mat.metal's simdgroup_multiply_accumulate to decide dedicated
// matrix HW vs an FMA/shuffle expansion. This one MUST be pure known-ISA ops
// (device_load + fma + device_store); if the simdgroup version differs by a
// small set of novel opcodes, that is the dedicated matrix instruction.
// CLEAN-ROOM: OUR OWN MSL.
#include <metal_stdlib>
using namespace metal;

// One output element per thread: R[i][j] = C[i][j] + sum_k A[i][k]*B[k][j].
// 64 threads (8x8). Pure scalar FMA over device memory.
kernel void hand_mm_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                        device float *C [[buffer(2)]], device float *R [[buffer(3)]],
                        uint tid [[thread_position_in_grid]]) {
    uint i = tid >> 3, j = tid & 7;
    float acc = C[i * 8 + j];
    for (uint k = 0; k < 8; ++k)
        acc = fma(A[i * 8 + k], B[k * 8 + j], acc);
    R[i * 8 + j] = acc;
}

// A lane-cooperative FMA+shuffle emulation, the shape an *emulated* cooperative
// matrix would take: each lane holds a couple of elements, shuffles operands
// across the simdgroup, accumulates with fma. Present so the diff can show what
// a genuine shuffle+FMA lowering looks like (many simd_shuffle + fma), in
// contrast to whatever simdgroup_multiply_accumulate actually emits.
kernel void hand_mm_shuffle(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                            device float *R [[buffer(2)]],
                            uint lane [[thread_index_in_simdgroup]]) {
    // lane holds A row (lane/4)?? keep it simple: 2 outputs per lane.
    uint i = lane >> 2;            // 0..7 row
    uint jb = (lane & 3) * 2;      // 0,2,4,6 col base
    float av[8], acc0 = 0, acc1 = 0;
    for (uint k = 0; k < 8; ++k) av[k] = A[i * 8 + k];
    for (uint k = 0; k < 8; ++k) {
        float b0 = simd_shuffle(B[k * 8 + jb + 0], k);   // force cross-lane traffic
        float b1 = simd_shuffle(B[k * 8 + jb + 1], k);
        acc0 = fma(av[k], b0, acc0);
        acc1 = fma(av[k], b1, acc1);
    }
    R[i * 8 + jb + 0] = acc0;
    R[i * 8 + jb + 1] = acc1;
}
