// split_prolog.metal -- EXP-0129 H2: a genuinely SEPARATE ("noinline"),
// CALL-boundary-crossing vertex-attribute-fetch PROLOG (OWN-SHADER).
//
// EXP-0031/EXP-0109 established vertex attribute fetch is in-shader SOFTWARE
// on Apple9 (a compiler-generated device_load + format-convert sequence),
// not a fixed-function fetch unit. This file constructs, by hand, a fetch
// "prolog" as a genuinely separate noinline function (rather than Metal's
// own inlined-fetch-prologue idiom) to characterize the CALL-boundary
// mechanics a driver would rely on if it wants to compile ONE fetch prolog
// and CALL it from many "main" vertex-shader bodies.
//
// Rasterization-disabled, atomic-indexed-SSBO-append readback pattern
// (mirrors EXP-0109's vsfetch_hw_* / EXP-0092's order-independent append).

#include <metal_stdlib>
using namespace metal;

// The "prolog" -- ordinary MSL function, NOT an entry point, noinline.
// UChar4Normalized-style fetch+normalize (same format family EXP-0109's §1.1
// format matrix exercised inline; here it is a genuinely CALLED function).
[[clang::noinline]] float4 fetch_attr(device const uchar4 *buf, uint idx) {
    uchar4 raw = buf[idx];
    return float4(raw) / 255.0;
}

struct FetchRec {
    float4 attr;
    uint   vid;
};

// rasterizationEnabled=NO requires a void-returning vertex function (own-
// compiler diagnostic, disclosed in PROGRESS.md).
vertex void v_split_prolog(uint vid [[vertex_id]],
                            device const uchar4 *vbuf [[buffer(0)]],
                            device atomic_uint *counter [[buffer(1)]],
                            device FetchRec *out [[buffer(2)]]) {
    float4 attr = fetch_attr(vbuf, vid);
    uint slot = atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    out[slot].attr = attr;
    out[slot].vid = vid;
}
