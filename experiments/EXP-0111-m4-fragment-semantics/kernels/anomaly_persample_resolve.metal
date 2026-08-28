#include <metal_stdlib>
using namespace metal;
// Anomaly (b) second method: EXP-0091 GLFS-A07's f_persample_discard_N4 (per-sample-id-
// conditioned discard: odd sample_id invocations call discard_fragment(), gated via a
// (pixel,sample)-indexed ATOMIC COUNTER buffer) found a deterministic but spatially
// NON-UNIFORM suppression pattern: only 2 of 8 "should be suppressed" (pixel,odd-sample)
// slots actually read as suppressed; the other 6 read as NOT suppressed -- unlike the
// uniform, complete suppression g6_suppress/GLFS-A06 found for WHOLE-fragment discard.
//
// Second, INDEPENDENT method: same per-sample-id-conditioned discard, but measured via
// the resolve-fraction technique (EXP-0091 GLFS-A01 msaa group, HW-VALIDATED, no atomics,
// no (pixel,sample)-indexed buffer addressing at all) instead of an atomic counter: each
// covered, non-discarded (even sample_id) invocation writes color=1 for ITS sample; odd
// sample_id invocations discard before any color write. Standard MSAA box-filter resolve
// then reads back the fraction of surviving samples per pixel. Oracle if per-sample
// discard suppression is COMPLETE and uniform: resolved fraction == 0.5 (2 of 4 samples
// survive) at every pixel, matching g6_suppress's completeness -- a genuinely different
// measurement mechanism than the atomic-buffer approach that produced the anomaly.
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
fragment float4 f_main(uint sid [[sample_id]]) {
    if ((sid & 1u) == 1u) discard_fragment();
    return float4(1,1,1,1);
}
fragment float4 f_control(uint sid [[sample_id]]) {
    return float4(1,1,1,1);
}
