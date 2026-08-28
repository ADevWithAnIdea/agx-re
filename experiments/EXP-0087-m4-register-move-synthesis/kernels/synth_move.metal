// EXP-0087 synthesis carrier (OWN-SHADER). One compute kernel, function `k`.
//
// Sixteen thread-invariant (constant-index) loads force the compiler to
// marshal each value through its own compact 4-byte GPR-move instruction
// (AGX byte0 low-nibble 0xb family -- the reg_move_c0/c1/c9/cb/c2var /
// uniform_mov descriptors under test) immediately before four vectorized
// device_store instructions read the resulting registers back out. Because
// every buffer index is a compile-time constant, in[K] does not depend on
// thread_position_in_grid and the compiler hoists all sixteen loads into the
// thread-invariant ("uniform") data path -- leaving exactly sixteen 4-byte
// moves feeding four 16-byte vector stores in _agc.main, with no intervening
// ALU op. This gives sixteen independently identifiable, independently
// spliceable "move -> store" carriers with a fully known baseline
// (out[K] == in[K] for K in 0..15).
//
// Confirmed by compiling with tools/shdump (macOS 26.6.2, clang 21, M4/G16G,
// --no-fast-math): the compiled _agc.main is
//   cb080108 db0a0108 eb0c0108 fb0e0108 8b100108 9b120108 ab140108 bb160108
//   4b180108 5b1a0108 6b1c0108 7b1e0108 0b200108 1b220108 2b240108 3b260108
//   e7005418 00000000 17000090 0000
//   e7005410 00000000 17800090 0000
//   e7005408 00000000 17000190 0000
//   e7005400 00000000 17800190 0000
//   0e000000
// (124 bytes; 16 x 4B uniform_mov + 4 x 14B device_store + 4B stop). See
// baseline.py for the anchored, re-derived version of this claim.
#include <metal_stdlib>
using namespace metal;

kernel void k(device float* out [[buffer(0)]],
              device const float* in [[buffer(1)]],
              uint tid [[thread_position_in_grid]]) {
    float v0  = in[0];
    float v1  = in[1];
    float v2  = in[2];
    float v3  = in[3];
    float v4  = in[4];
    float v5  = in[5];
    float v6  = in[6];
    float v7  = in[7];
    float v8  = in[8];
    float v9  = in[9];
    float v10 = in[10];
    float v11 = in[11];
    float v12 = in[12];
    float v13 = in[13];
    float v14 = in[14];
    float v15 = in[15];
    out[0]  = v0;
    out[1]  = v1;
    out[2]  = v2;
    out[3]  = v3;
    out[4]  = v4;
    out[5]  = v5;
    out[6]  = v6;
    out[7]  = v7;
    out[8]  = v8;
    out[9]  = v9;
    out[10] = v10;
    out[11] = v11;
    out[12] = v12;
    out[13] = v13;
    out[14] = v14;
    out[15] = v15;
}
