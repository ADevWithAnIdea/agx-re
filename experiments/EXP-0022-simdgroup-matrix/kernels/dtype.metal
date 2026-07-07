// EXP-0022 data-type envelope for simdgroup_matrix. Each kernel is a separate
// availability + encoding probe. Some are expected to FAIL to compile (that is a
// first-class negative result -> Metal does not expose that matrix dtype).
// CLEAN-ROOM: OUR OWN MSL.
#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;

// bfloat x bfloat -> bfloat
kernel void mad_bf16(device bfloat *A [[buffer(0)]], device bfloat *B [[buffer(1)]],
                     device bfloat *C [[buffer(2)]], device bfloat *R [[buffer(3)]]) {
    simdgroup_matrix<bfloat,8,8> a, b, c, r;
    simdgroup_load(a, A, 8); simdgroup_load(b, B, 8); simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// half x half -> FLOAT accumulate (mixed-precision: the ML-relevant path)
kernel void mad_f16_f32acc(device half *A [[buffer(0)]], device half *B [[buffer(1)]],
                           device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_matrix<half,8,8> a, b;
    simdgroup_matrix<float,8,8> c, r;
    simdgroup_load(a, A, 8); simdgroup_load(b, B, 8); simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// bfloat x bfloat -> FLOAT accumulate
kernel void mad_bf16_f32acc(device bfloat *A [[buffer(0)]], device bfloat *B [[buffer(1)]],
                            device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_matrix<bfloat,8,8> a, b;
    simdgroup_matrix<float,8,8> c, r;
    simdgroup_load(a, A, 8); simdgroup_load(b, B, 8); simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// int8 x int8 -> int32
kernel void mad_i8(device char *A [[buffer(0)]], device char *B [[buffer(1)]],
                   device int *C [[buffer(2)]], device int *R [[buffer(3)]]) {
    simdgroup_matrix<char,8,8> a, b;
    simdgroup_matrix<int,8,8> c, r;
    simdgroup_load(a, A, 8); simdgroup_load(b, B, 8); simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// int32 x int32 -> int32
kernel void mad_i32(device int *A [[buffer(0)]], device int *B [[buffer(1)]],
                    device int *C [[buffer(2)]], device int *R [[buffer(3)]]) {
    simdgroup_matrix<int,8,8> a, b, c, r;
    simdgroup_load(a, A, 8); simdgroup_load(b, B, 8); simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// non-8x8 dimension probe (does MSL expose other simdgroup_matrix dims?)
kernel void mad_f32_16(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                       device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_matrix<float,16,16> a, b, c, r;
    simdgroup_load(a, A, 16); simdgroup_load(b, B, 16); simdgroup_load(c, C, 16);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 16);
}
