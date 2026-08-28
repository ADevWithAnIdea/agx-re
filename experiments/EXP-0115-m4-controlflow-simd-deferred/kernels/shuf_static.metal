// shuf_static.metal -- EXP-0115 item 4: static/immediate-index shuffle family
// out-of-range probe targets. Own-authored MSL. Each kernel calls the shuffle
// builtin with a COMPILE-TIME-CONSTANT (literal) index; reconnaissance
// (work/pilot, real compiles) showed Metal's compiler lowers a literal index
// to a SINGLE shuffle instruction with the index embedded directly in the
// instruction's "lane" byte (encoded as index<<1) -- a qualitatively simpler,
// cleanly-tokenizing encoding than the multi-instruction sequence emitted for
// a genuinely runtime (register-sourced) index (EXP-0104's SIMD-03 "dynamic"
// form). This file's compiled instructions are the splice targets: the lane
// byte is overwritten directly to CONSTRUCT arbitrary raw values (the
// compiler's own literal-index range checking/masking is bypassed entirely,
// per this experiment's directive to construct encodings ourselves rather
// than rely on what the compiler emits). No Apple code read.
#include <metal_stdlib>
using namespace metal;

kernel void shuffle_static(device int* out [[buffer(0)]],
                            uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    out[i] = simd_shuffle(v, (ushort)5);
}

kernel void shufflexor_static(device int* out [[buffer(0)]],
                               uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    out[i] = simd_shuffle_xor(v, (ushort)1);
}

kernel void quadshuffle_static(device int* out [[buffer(0)]],
                                uint i [[thread_position_in_grid]]) {
    int v = (int)i;
    out[i] = quad_shuffle(v, (ushort)1);
}
