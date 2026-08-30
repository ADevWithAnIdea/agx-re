// EXP-0203 anchor probes (authored by us).
//
// These compile to REAL instances of the two families under test, so the experiment has a
// compiler-produced anchor to compare its SYNTHESIZED instances against. They are not the
// carrier: the carrier's body is replaced wholesale.
//
// CLEAN-ROOM: our own MSL; the only machine code inspected anywhere in this experiment is
// the compiled form of these and of the two carriers.
#include <metal_stdlib>
using namespace metal;

// 12-byte fp16 fma form: fma(abs(a), b, c) is what EXP-M4-14 showed reaches the 12-byte
// (opsel 6, length-selector 3) encoding.
kernel void k_hfma_abs(device half* out [[buffer(0)]], device half* in [[buffer(1)]],
                       uint tid [[thread_position_in_grid]]) {
    half a = in[tid], b = in[tid + 4], c = in[tid + 8];
    out[tid] = fma(abs(a), b, c);
}

kernel void k_hfma(device half* out [[buffer(0)]], device half* in [[buffer(1)]],
                   uint tid [[thread_position_in_grid]]) {
    out[tid] = fma(in[tid], in[tid + 4], in[tid + 8]);
}

// half2 add: the low lane goes through the byte0-low-nibble-0 family and the high lane
// through the 0x?8 family that db.json currently calls `half_pack`.
kernel void k_half2(device half2* out [[buffer(0)]], device half2* in [[buffer(1)]],
                    uint tid [[thread_position_in_grid]]) {
    out[tid] = in[tid] + in[tid + 4];
}

kernel void k_half2mul(device half2* out [[buffer(0)]], device half2* in [[buffer(1)]],
                       uint tid [[thread_position_in_grid]]) {
    out[tid] = in[tid] * in[tid + 4];
}
