// EXP-0022 simdgroup_matrix (cooperative matrix) provocation kernels.
// CLEAN-ROOM: OUR OWN MSL. Compiled at runtime; only our own compiled bytes are
// ever inspected. No Apple binary is disassembled.
#include <metal_stdlib>
#include <metal_simdgroup_matrix>
using namespace metal;

// --- Load an 8x8 fp32 tile and store it back --------------------------------
// Isolates simdgroup_load + simdgroup_store and the 8x8-tile -> 32-lane mapping.
kernel void ls_f32(device float *A [[buffer(0)]], device float *R [[buffer(1)]]) {
    simdgroup_float8x8 a;
    simdgroup_load(a, A, 8);
    simdgroup_store(a, R, 8);
}

// --- Multiply-accumulate  r = a*b + c  (the core matrix MAC) -----------------
kernel void mad_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                    device float *C [[buffer(2)]], device float *R [[buffer(3)]]) {
    simdgroup_float8x8 a, b, c, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// --- Multiply only  r = a*b  (diff vs mad_f32 to isolate the C operand) ------
kernel void mul_f32(device float *A [[buffer(0)]], device float *B [[buffer(1)]],
                    device float *R [[buffer(2)]]) {
    simdgroup_float8x8 a, b, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_multiply(r, a, b);
    simdgroup_store(r, R, 8);
}

// --- fp16 x fp16 -> fp16 multiply-accumulate --------------------------------
kernel void mad_f16(device half *A [[buffer(0)]], device half *B [[buffer(1)]],
                    device half *C [[buffer(2)]], device half *R [[buffer(3)]]) {
    simdgroup_half8x8 a, b, c, r;
    simdgroup_load(a, A, 8);
    simdgroup_load(b, B, 8);
    simdgroup_load(c, C, 8);
    simdgroup_multiply_accumulate(r, a, b, c);
    simdgroup_store(r, R, 8);
}

// --- fp16 load/store (lane mapping for half tiles) --------------------------
kernel void ls_f16(device half *A [[buffer(0)]], device half *R [[buffer(1)]]) {
    simdgroup_half8x8 a;
    simdgroup_load(a, A, 8);
    simdgroup_store(a, R, 8);
}

// --- filled constant matrix -> store ----------------------------------------
kernel void fill_f32(device float *R [[buffer(0)]]) {
    simdgroup_float8x8 r = make_filled_simdgroup_matrix<float, 8, 8>(1.0f);
    simdgroup_store(r, R, 8);
}

// --- transposed load variant (does transpose ride the load or a permute?) ---
kernel void ls_f32_t(device float *A [[buffer(0)]], device float *R [[buffer(1)]]) {
    simdgroup_float8x8 a;
    simdgroup_load(a, A, 8, ulong2(0, 0), /*transpose=*/true);
    simdgroup_store(a, R, 8);
}
