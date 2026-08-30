// EXP-0205 kernels/k_shuffle.metal -- AUTHORED BY US (clean-room OWN-SHADER).
//
// Carriers for simd_shuffle.dir (byte0 bit 7) and simd_shuffle.cache (byte+2
// bit 1).
//
// `dir` is where per-lane read-back pays off most.  db.json says byte0 bit 7
// selects broadcast/up (0x47) against xor/down (0xC7).  With 32 DISTINCT
// per-lane source values the two produce completely different 32-word vectors:
//   dir=0, mode=simd, lane=5  ->  every lane reads lane 5's value
//   dir=1, mode=simd, lane=5  ->  lane t reads lane (t XOR 5)'s value
// The host predicts both vectors exactly, so the oracle DIFFERS PER FIELD
// VALUE rather than merely asserting "something was written".
//
// The two carriers have OPPOSITE BASELINE VALUES of `dir` (sh_bc compiles from
// simd_broadcast, sh_xor from simd_shuffle_xor), so each is the other's
// falsifier: a splice on either must land on the other's measured baseline
// vector.
//
// Buffer/word contract: see k_ballot.metal.

#include <metal_stdlib>
using namespace metal;

constant uint SENT_WORD = 72u;
constant uint SENT_VAL  = 12345u;
constant uint SHUF_LANE = 5u;

// -------------------------------------------------------------------- sh_bc
kernel void k_sh_bc(device uint *out       [[buffer(0)]],
                    const device uint *in  [[buffer(1)]],
                    uint tid               [[thread_position_in_grid]])
{
    out[SENT_WORD] = SENT_VAL;
    uint v = in[tid];
    out[tid] = simd_broadcast(v, SHUF_LANE);
}

// ------------------------------------------------------------------- sh_xor
kernel void k_sh_xor(device uint *out       [[buffer(0)]],
                     const device uint *in  [[buffer(1)]],
                     uint tid               [[thread_position_in_grid]])
{
    out[SENT_WORD] = SENT_VAL;
    uint v = in[tid];
    out[tid] = simd_shuffle_xor(v, SHUF_LANE);
}

// ----------------------------------------------------------------- sh_reuse
// THE CACHE-DIMENSION CARRIER for simd_shuffle, built on the same reasoning as
// k_sb_reuse: the source `v` is read AGAIN after the shuffle, and 16
// independent loads stay live across it so the register file is under real
// pressure.  If byte+2 bit 1 is the operand `discard` hint the public docs
// describe, its effect is on `v`'s register AFTER the instruction, and
// out[32+tid] is where that would show.
kernel void k_sh_reuse(device uint *out       [[buffer(0)]],
                       const device uint *in  [[buffer(1)]],
                       uint tid               [[thread_position_in_grid]])
{
    out[SENT_WORD] = SENT_VAL;
    uint v = in[tid];
    uint a0  = in[32u + ((tid +  0u) & 31u)];
    uint a1  = in[32u + ((tid +  1u) & 31u)];
    uint a2  = in[32u + ((tid +  2u) & 31u)];
    uint a3  = in[32u + ((tid +  3u) & 31u)];
    uint a4  = in[32u + ((tid +  4u) & 31u)];
    uint a5  = in[32u + ((tid +  5u) & 31u)];
    uint a6  = in[32u + ((tid +  6u) & 31u)];
    uint a7  = in[32u + ((tid +  7u) & 31u)];
    uint a8  = in[32u + ((tid +  8u) & 31u)];
    uint a9  = in[32u + ((tid +  9u) & 31u)];
    uint a10 = in[32u + ((tid + 10u) & 31u)];
    uint a11 = in[32u + ((tid + 11u) & 31u)];
    uint a12 = in[32u + ((tid + 12u) & 31u)];
    uint a13 = in[32u + ((tid + 13u) & 31u)];
    uint a14 = in[32u + ((tid + 14u) & 31u)];
    uint a15 = in[32u + ((tid + 15u) & 31u)];

    uint r = simd_broadcast(v, SHUF_LANE);

    uint s = a0 ^ a1 ^ a2 ^ a3 ^ a4 ^ a5 ^ a6 ^ a7
           ^ a8 ^ a9 ^ a10 ^ a11 ^ a12 ^ a13 ^ a14 ^ a15;
    out[tid] = r;
    out[32u + tid] = (v * 3u) + s + (r >> 31);
}
