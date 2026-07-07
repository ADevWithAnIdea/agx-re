// EXP-O2C tensor/matrix provocation kernels (extends EXP-0022).
// CLEAN-ROOM: OUR OWN MSL. Compiled at runtime; only our own compiled bytes are
// inspected. No Apple binary is disassembled.
#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;

// r = a*b + c  (float) -- the reference op for the 0xcf operand-selector decode.
kernel void mad_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                    device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_float8x8 a, b, c, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// r = a*b (multiply only) -- diff vs mad_f32 to isolate C operand & accumulate bit.
kernel void mul_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                    device float *R [[buffer(2)]]) {
    simdgroup_float8x8 a, b, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_multiply(r, a, b);
    simdgroup_store(r, R, 8);
}

// half MAC.
kernel void mad_f16(device half *A [[buffer(0)]], device half *B [[buffer(1)]],
                    device half *C [[buffer(2)]], device half *R [[buffer(3)]]) {
    simdgroup_half8x8 a, b, c, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// bfloat MAC (dtype probe; bf16 shares the 32-bit datapath per EXP-0022).
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

// r = b*a + c  (operands swapped in source) -- byte-diff vs mad_f32 to see which
// 0xcf field carries the A vs the B operand register.
kernel void mad_ba(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                   device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_float8x8 a, b, c, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, b, a, c);   // note: b*a
    simdgroup_store(r, R, 8);
}

// Two chained MACs into one accumulator: r = a*b; r = r*c (+r) -- forces the dst
// register to also be a source, to expose the dst selector field.
kernel void mad_chain(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                      device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_float8x8 a, b, c, r, t;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply(t, a, b);
    simdgroup_multiply_accumulate(r, t, c, t);   // r = t*c + t
    simdgroup_store(r, R, 8);
}

// load->store round-trip (element<->lane mapping baseline).
kernel void ls_f32(device float *A [[buffer(0)]], device float *R [[buffer(1)]]) {
    simdgroup_float8x8 a;
    simdgroup_load(a, A, 8);
    simdgroup_store(a, R, 8);
}

// transposed load: does transpose ride the load, or a separate permute/opcode?
kernel void ls_f32_t(device float *A [[buffer(0)]], device float *R [[buffer(1)]]) {
    simdgroup_float8x8 a;
    simdgroup_load(a, A, 8, ulong2(0, 0), /*transpose=*/true);
    simdgroup_store(a, R, 8);
}

// transposed store.
kernel void ls_f32_st(device float *A [[buffer(0)]], device float *R [[buffer(1)]]) {
    simdgroup_float8x8 a;
    simdgroup_load(a, A, 8);
    simdgroup_store(a, R, 8, ulong2(0, 0), /*transpose=*/true);
}

// MAC with transposed A load (matmul with a transposed operand).
kernel void mad_at(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                   device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_float8x8 a, b, c, r;
    simdgroup_load(a, A, 8, ulong2(0,0), true);   // A^T
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}
