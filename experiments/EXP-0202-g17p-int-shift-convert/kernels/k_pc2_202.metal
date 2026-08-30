// EXP-0202 AMENDMENT (v3) -- a SECOND, DISJOINT READBACK PLAN for ibitcount.dst.
// AUTHORED BY US; OWN-SHADER. The v1/v2 kernel files are NOT edited.
//
// `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` section 6:
//   "Seed all candidate sources with unique values and dump all architecturally
//    observable registers, not just one presumed destination. Keep the
//    store/readback index fixed while sweeping a destination. Use at least two
//    disjoint register/readback plans so a hidden write or destination alias
//    cannot masquerade as inertness."
//
// Every v1 ibitcount carrier stores ONE word per lane, so redirecting the count
// onto another live register is invisible unless that register happens to feed
// the same store. This carrier keeps FOUR mutually distinct live values per lane
// and stores all four at FIXED indices, so a redirected destination shows up as
// one of the other three words changing to the count.
//
//   w0 = popcount(a[t])            <- the instruction under test
//   w1 = a[t]*3 + 1                <- distinct codeword, no bit pattern in common
//   w2 = a[t] ^ 0x5A5A5A5A
//   w3 = a[t] + 0x01010101
//
// grid = 4, so the value region is 16 words; sentinel at word 16.
#include <metal_stdlib>
using namespace metal;

kernel void k_pc_dump(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      uint t [[thread_position_in_grid]]) {
    out[16] = 12345u;
    uint w0 = popcount(a[t]);
    uint w1 = a[t] * 3u + 1u;
    uint w2 = a[t] ^ 0x5A5A5A5Au;
    uint w3 = a[t] + 0x01010101u;
    out[4 * t + 0] = w0;
    out[4 * t + 1] = w1;
    out[4 * t + 2] = w2;
    out[4 * t + 3] = w3;
}
