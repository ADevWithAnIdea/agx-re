// EXP-M5-09 MARQUEE: simdgroup_matrix (cooperative-matrix) MAC provocations on M5.
// CLEAN-ROOM: OUR OWN MSL. Compiled at runtime; only our own compiled bytes are
// inspected. No Apple binary is disassembled. Reused/extended from EXP-O2C (A18).
#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;

// f32 MAC r = a*b + c
kernel void mad_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                    device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_float8x8 a, b, c, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// f32 multiply only r = a*b
kernel void mul_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                    device float *R [[buffer(2)]]) {
    simdgroup_float8x8 a, b, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_multiply(r, a, b);
    simdgroup_store(r, R, 8);
}

// f16 MAC
kernel void mad_f16(device half *A [[buffer(0)]], device half *B [[buffer(1)]],
                    device half *C [[buffer(2)]], device half *R [[buffer(3)]]) {
    simdgroup_half8x8 a, b, c, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// CONTROL: load+store only, NO matrix multiply. Isolates tile load/store ops from the MAC.
kernel void ls_f32(device float *A [[buffer(0)]], device float *R [[buffer(1)]]) {
    simdgroup_float8x8 a;
    simdgroup_load(a, A, 8);
    simdgroup_store(a, R, 8);
}

// bf16 MAC (bfloat inputs, float accumulate)
kernel void mad_bf16(device bfloat *A [[buffer(0)]], device bfloat *B [[buffer(1)]],
                     device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_matrix<bfloat,8,8> a, b;
    simdgroup_matrix<float,8,8> c, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}
