// EXP-M5-20: simdgroup_matrix (cooperative-matrix) MAC operand bit-packing.
// CLEAN-ROOM: OUR OWN MSL, compiled at runtime on-device; only our own compiled
// bytes are inspected/spliced. No Apple binary is disassembled. Extends EXP-M5-09.
#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;

// ---- fp32 8x8 MAC: R = A*B + C ------------------------------------------------
// One full simdgroup (dispatch grid=32, tg=32). A,B,C,R are 64-float row-major.
kernel void mad_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                    device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_float8x8 a, b, c, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// ---- fp32 multiply only: R = A*B ---------------------------------------------
kernel void mul_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                    device float *R [[buffer(2)]]) {
    simdgroup_float8x8 a, b, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_multiply(r, a, b);
    simdgroup_store(r, R, 8);
}

// ---- TWO independent MACs, distinct tiles, two outputs -----------------------
// Forces the compiler to allocate ~6-8 distinct tile slots so a spliced operand
// field in MAC#0 can be redirected to a tile that MAC#1 uses (numeric change).
kernel void mad2_f32(device float *A0 [[buffer(0)]], device float *B0 [[buffer(1)]],
                     device float *C0 [[buffer(2)]], device float *A1 [[buffer(3)]],
                     device float *B1 [[buffer(4)]], device float *C1 [[buffer(5)]],
                     device float *R0 [[buffer(6)]], device float *R1 [[buffer(7)]]) {
    simdgroup_float8x8 a0, b0, c0, r0, a1, b1, c1, r1;
    simdgroup_load(a0, A0, 8); simdgroup_load(b0, B0, 8); simdgroup_load(c0, C0, 8);
    simdgroup_load(a1, A1, 8); simdgroup_load(b1, B1, 8); simdgroup_load(c1, C1, 8);
    simdgroup_multiply_accumulate(r0, a0, b0, c0);
    simdgroup_multiply_accumulate(r1, a1, b1, c1);
    simdgroup_store(r0, R0, 8);
    simdgroup_store(r1, R1, 8);
}

// ---- role-swapped variants (byte-diff the operand order) ---------------------
// R = B*A + C  (multiply operands swapped vs mad_f32)
kernel void mad_ba_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                       device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_float8x8 a, b, c, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, b, a, c);
    simdgroup_store(r, R, 8);
}

// ---- TWO live tiles, two stores: clean tile-register (byte0-hi) proof ---------
// a and b are BOTH live at their stores; redirecting store-a's source tile to
// b's tile makes R0 read b's data (no dead-register confound).
kernel void st2_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                    device float *R0 [[buffer(2)]], device float *R1 [[buffer(3)]]) {
    simdgroup_float8x8 a, b;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_store(a, R0, 8);
    simdgroup_store(b, R1, 8);
}
