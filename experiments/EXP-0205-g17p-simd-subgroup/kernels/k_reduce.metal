// EXP-0205 kernels/k_reduce.metal -- AUTHORED BY US (clean-room OWN-SHADER).
//
// Carriers for simd_reduce.op (byte+1) and simd_reduce.dtype (byte+7).
//
// WHY PER-LANE READ-BACK IS THE WHOLE DESIGN.  db.json's `dtype` enum mixes
// REDUCE forms (every lane gets the same total) with INCLUSIVE and EXCLUSIVE
// SCAN forms (every lane gets a different partial).  A carrier that collapsed
// the SIMD group to one output word could not tell those apart at all; with 32
// separate output words the three are trivially distinguishable, and the host
// oracle predicts a DIFFERENT 32-word vector for each of them.  Likewise `op`
// (ior/isum/smax/umax/f16/fmin/f32/fmax) predicts a different vector per value.
//
// Four carriers, deliberately with DIFFERENT BASELINE VALUES of the two fields
// under test, so the sweep is not one carrier run four times:
//   sr_sum   int   reduce            baseline op=isum   dtype=i32_reduce
//   sr_scan  int   inclusive scan    baseline op=isum   dtype=i32_incl_scan
//   sr_max   int   max reduce        baseline op=smax   dtype=s32_minmax
//   sr_fsum  float reduce            baseline op=f32sum dtype=f32_reduce
// The float carrier exists so that the FLOAT half of the `op` enum has a
// predictable oracle: on the int carriers a float-op reinterpretation of small
// integers is a denormal and is not honestly predictable, and we say so rather
// than scoring it.
//
// Buffer/word contract: see k_ballot.metal.

#include <metal_stdlib>
using namespace metal;

constant uint SENT_WORD = 72u;
constant uint SENT_VAL  = 12345u;

// ------------------------------------------------------------------- sr_sum
kernel void k_sr_sum(device uint *out       [[buffer(0)]],
                     const device uint *in  [[buffer(1)]],
                     uint tid               [[thread_position_in_grid]])
{
    out[SENT_WORD] = SENT_VAL;
    int v = int(in[tid]);
    int r = simd_sum(v);
    out[tid] = uint(r);
}

// ------------------------------------------------------------------ sr_scan
kernel void k_sr_scan(device uint *out       [[buffer(0)]],
                      const device uint *in  [[buffer(1)]],
                      uint tid               [[thread_position_in_grid]])
{
    out[SENT_WORD] = SENT_VAL;
    int v = int(in[tid]);
    int r = simd_prefix_inclusive_sum(v);
    out[tid] = uint(r);
}

// ------------------------------------------------------------------- sr_max
kernel void k_sr_max(device uint *out       [[buffer(0)]],
                     const device uint *in  [[buffer(1)]],
                     uint tid               [[thread_position_in_grid]])
{
    out[SENT_WORD] = SENT_VAL;
    int v = int(in[tid]);
    int r = simd_max(v);
    out[tid] = uint(r);
}

// ------------------------------------------------------------------ sr_fsum
// The output buffer stays `device uint*` on EVERY carrier so the integrity
// sentinel is the SAME integer store through the SAME path everywhere; the
// float result is written as its bit pattern and decoded as f32 on the host.
// (A float sentinel would have been a denormal for 12345 and could be flushed.)
kernel void k_sr_fsum(device uint *out        [[buffer(0)]],
                      const device float *in  [[buffer(1)]],
                      uint tid                [[thread_position_in_grid]])
{
    out[SENT_WORD] = SENT_VAL;
    float v = in[tid];
    float r = simd_sum(v);
    out[tid] = as_type<uint>(r);
}
