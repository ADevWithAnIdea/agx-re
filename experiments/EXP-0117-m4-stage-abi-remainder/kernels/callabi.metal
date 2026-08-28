// callabi.metal -- EXP-0117 CALL-ABI byte-level probe kernels (OWN-SHADER).
//
// EXP-0109's cs_call_probe (kernel with TWO call sites to the SAME leaf
// callee, no nested/spilling frame) found byte+6==0x54 at both M4 call
// sites, where EXP-0035's A18 single-call-site captures
// (direct_call.txt/dynamic_library.txt) show byte+6==0x56 -- ONE
// unresolved byte-level discrepancy. EXP-0035's OWN "mid" function
// (abi_and_frames.txt, a NON-LEAF caller invoking leaf() TWICE, spilling
// its link register around each call) ALSO shows byte+6==0x54 for both A18
// calls (not 0x56), with byte+5 differing between the two call sites
// (0x10 then 0x00). This file isolates the candidate variable ("how many
// call sites does the CONTAINING function have", independent of whether it
// itself is CALLED by something else / spills) by holding call-COUNT fixed
// at exactly the values needed to separate the two prior observations.

#include <metal_stdlib>
using namespace metal;

// ---- k_single: exactly ONE call site in the whole compiled unit. ----------
__attribute__((noinline)) static float leaf_a(float x) { return x * 2.0f + 1.0f; }
kernel void k_single(device float *out [[buffer(0)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = leaf_a(float(gid));
}

// ---- k_twosame: TWO call sites, SAME callee (reproduces EXP-0109's
// cs_call_probe shape exactly, captured fresh under this experiment's own
// frozen contract rather than only cited). --------------------------------
kernel void k_twosame(device float *out [[buffer(0)]], uint gid [[thread_position_in_grid]]) {
    float a = float(gid);
    float b = a + 3.0f;
    out[gid] = leaf_a(a) + leaf_a(b);
}

// ---- k_twodiff: TWO call sites, DIFFERENT callees. -------------------------
__attribute__((noinline)) static float leaf_b(float x) { return x * 3.0f - 1.0f; }
kernel void k_twodiff(device float *out [[buffer(0)]], uint gid [[thread_position_in_grid]]) {
    float a = float(gid);
    float b = a + 3.0f;
    out[gid] = leaf_a(a) + leaf_b(b);
}

// ---- k_nested: reproduces EXP-0035's "mid" shape on M4 -- a NON-LEAF
// helper (calls leaf_a twice) itself invoked from the kernel entry, forcing
// the caller to spill/restore its own link register around each nested
// call (EXP-0035's 07.. save/restore bracket). --------------------------
__attribute__((noinline)) static float mid_fn(float x) { return leaf_a(x) + leaf_a(x * 3.0f); }
kernel void k_nested(device float *out [[buffer(0)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = mid_fn(float(gid));
}

// ---- k_threecalls: THREE call sites to the same callee, in one function
// with no nesting -- extends the "does byte+6 depend on call-site COUNT >=2"
// hypothesis past 2, and gives a 3rd byte+5 data point in an unspilled frame.
kernel void k_threecalls(device float *out [[buffer(0)]], uint gid [[thread_position_in_grid]]) {
    float a = float(gid);
    out[gid] = leaf_a(a) + leaf_a(a + 1.0f) + leaf_a(a + 2.0f);
}

// ---- k_far / k_near: same single-call-site shape as k_single, but with a
// deliberately large amount of dead code BETWEEN the call site and its
// callee (k_far) vs none (k_near, == k_single) -- tests whether byte+6 (or
// the off40 magnitude/sign) is what actually predicts the byte pattern,
// ruling out "just distance" as the explanation for the 0x56 vs 0x54 split.
__attribute__((noinline)) static float leaf_pad(float x) {
    // Deliberately inflate this callee's own body (not the caller's) so the
    // CALLER->CALLEE offset grows without adding extra call SITES.
    float y = x;
    for (int i = 0; i < 40; i++) { y = y * 1.0000001f + 0.0000001f * float(i); }
    return y + 1.0f;
}
kernel void k_far(device float *out [[buffer(0)]], uint gid [[thread_position_in_grid]]) {
    out[gid] = leaf_pad(float(gid));
}
