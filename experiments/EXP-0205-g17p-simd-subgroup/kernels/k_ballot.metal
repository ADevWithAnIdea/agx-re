// EXP-0205 kernels/k_ballot.metal -- AUTHORED BY US (clean-room OWN-SHADER).
//
// Carriers for simd_ballot.pred (byte+1 high nibble) and simd_ballot.cache
// (byte+2, the whole byte).
//
// LANE DIVERGENCE IS THE POINT.  A ballot whose predicate is uniform across the
// SIMD group cannot distinguish `pred` values: with a uniform-true predicate,
// ballot(predicate) and active_threads_mask are the SAME bit pattern, so the
// field that selects between them is unobservable BY CONSTRUCTION.  Every
// carrier here therefore drives the predicate from a per-lane input word whose
// pattern is the asymmetric constant BALLOT_MASK = 0x6C8AF35D, chosen so that
// the expected ballot differs from 0xFFFFFFFF (all-active), 0xAAAAAAAA
// (odd/even), 0x00000000 (silent zero) and from its own bit-reverse.
//
// Buffer contract (shared by every carrier in this experiment):
//   buffer(0) = out, PRE-FILLED WITH POISON 0xDEADBEEF+i by the harness.
//   buffer(1) = in, our authored per-lane inputs.
//   out[0..31]  per-lane value words
//   out[32..63] per-lane secondary words (only the *_reuse carriers write these)
//   out[72]     INTEGRITY SENTINEL = 12345, stored FIRST, through a constant
//               path that names no register any descriptor under test reads.
//   out[73..79] TAIL: must stay poison; nothing here ever writes it.

#include <metal_stdlib>
using namespace metal;

constant uint SENT_WORD = 72u;
constant uint SENT_VAL  = 12345u;

// ---------------------------------------------------------------- sb_ballot
// simd_ballot(predicate) with a genuinely divergent predicate.  Every lane is
// ACTIVE, so active_threads_mask == 0xFFFFFFFF while ballot(predicate) ==
// 0x6C8AF35D.  That is the whole discriminating power for `pred`.
kernel void k_sb_ballot(device uint *out       [[buffer(0)]],
                        const device uint *in  [[buffer(1)]],
                        uint tid               [[thread_position_in_grid]])
{
    out[SENT_WORD] = SENT_VAL;
    uint v = in[tid];
    bool p = (v & 1u) != 0u;
    simd_vote vt = simd_ballot(p);
    out[tid] = uint((simd_vote::vote_t)vt);
}

// --------------------------------------------------------------- sb_ballot2
// Same code as k_sb_ballot, DIFFERENT AUTHORED INPUT: the predicate mask is
// 0x35D6C8AF instead of 0x6C8AF35D (the mask arrives in buffer(1), not in the
// source, so the two compile to the same bytes on purpose).  Its job is
// ATTRIBUTION: if a `pred` value moves the observation, this carrier says
// whether the new value still TRACKS THE PREDICATE (ballot-like, moves with the
// mask) or is the same on both masks (predicate-independent, active-mask-like).
// One carrier cannot tell those apart.
kernel void k_sb_ballot2(device uint *out       [[buffer(0)]],
                         const device uint *in  [[buffer(1)]],
                         uint tid               [[thread_position_in_grid]])
{
    out[SENT_WORD] = SENT_VAL;
    uint v = in[tid];
    bool p = (v & 1u) != 0u;
    simd_vote vt = simd_ballot(p);
    out[tid] = uint((simd_vote::vote_t)vt);
}

// ---------------------------------------------------------------- sb_active
// simd_active_threads_mask() taken inside a divergent `if`.
//
// PRE-FREEZE CALIBRATION REFUTED THIS CARRIER'S FIRST PREMISE, and the
// refutation is kept rather than edited away (raw/prefreeze/calibration.json).
// The premise was that the divergent region would make the active mask
// 0x6C8AF35D rather than the trivial 0xFFFFFFFF, and that db.json's `pred`
// would read 0x07 here against 0x17 on the ballot carrier.  BOTH are false on
// G17P with our compiler: the observed mask is 0xFFFFFFFF (the region is
// predicated, or the mask reports resident rather than executing lanes -- we do
// not claim which), and `pred` is 0 on BOTH forms.  What actually separates the
// two compiled forms is byte+5 (psrctype 0x00 vs 0x02) and the byte+7..9 tail.
// The carrier is kept because it is still a genuinely different compiled form
// of the same descriptor, with a different tail and a different observable.
kernel void k_sb_active(device uint *out       [[buffer(0)]],
                        const device uint *in  [[buffer(1)]],
                        uint tid               [[thread_position_in_grid]])
{
    out[SENT_WORD] = SENT_VAL;
    uint v = in[tid];
    uint r = 0x00C0FFEEu;
    if ((v & 1u) != 0u) {
        r = uint((simd_vote::vote_t)simd_active_threads_mask());
    }
    out[tid] = r;
}

// ----------------------------------------------------------------- sb_reuse
// THE CACHE-DIMENSION CARRIER.  Public open-source documentation of the older
// AGX generations (dougallj/applegpu, in gpu_knowledge/) describes operand
// `cache`/`discard` hints as: "cache = retain in register cache", "discard =
// future reads undefined, frees register for reuse".  If db.json's byte+2
// `cache` is that, then the dimension it controls is THE CONTENT OF THE SOURCE
// REGISTER AFTER THE INSTRUCTION, and it can only bite when (a) the source is
// read again afterwards and (b) the register file is under enough pressure for
// a freed register to actually be reused.
//
// EXP-0163's four carriers all reused their sources with LOW pressure;
// EXP-0172's `deadsrc` carrier removed the reuse entirely (sources dead after
// one use), which makes a discard hint harmless BY CONSTRUCTION.  Neither
// varied REGISTER PRESSURE.  This carrier does both: 16 independent loads stay
// live across the ballot, and the predicate source `v` is read again after it.
kernel void k_sb_reuse(device uint *out       [[buffer(0)]],
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

    bool p = (v & 1u) != 0u;
    uint m = uint((simd_vote::vote_t)simd_ballot(p));

    // `v` is read AGAIN here, after the ballot, and the 16 a* values are all
    // still live across it.
    uint s = a0 ^ a1 ^ a2 ^ a3 ^ a4 ^ a5 ^ a6 ^ a7
           ^ a8 ^ a9 ^ a10 ^ a11 ^ a12 ^ a13 ^ a14 ^ a15;
    out[tid] = m;
    out[32u + tid] = (v * 3u) + s + (m >> 31);
}

// ----------------------------------------------------------------- sb_width
// SIMD width probe.  Never spliced; run unmutated once per gated run so the
// measured SIMD width is a recorded observation and not an assumption.
kernel void k_sb_width(device uint *out  [[buffer(0)]],
                       uint tid          [[thread_position_in_grid]],
                       uint lane         [[thread_index_in_simdgroup]],
                       uint sgw          [[threads_per_simdgroup]],
                       uint sgi          [[simdgroup_index_in_threadgroup]])
{
    out[SENT_WORD] = SENT_VAL;
    out[tid] = lane | (sgi << 8) | (sgw << 16);
}
