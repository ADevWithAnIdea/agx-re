// EXP-0130 kernels -- OWN-SHADER MSL authored fresh for this experiment.
//
// Goal: construct, from our own MSL source, a fragment-shaped program that
// performs the two operations an AGX end-of-tile (EOT) program must perform
// -- read the tilebuffer's current resident value, and write it to a bound
// attachment (real backing memory) -- with NO per-fragment blend/combine
// step (real EOT evicts the tile as-is; it does not compute a new value).
// This is a stricter, more EOT-faithful shape than EXP-0029/EXP-0117's
// "blend_read"/logic-op constructions, which additionally combine the read
// value with a second (src) operand.
//
// Every function here is authored by us and compiled at runtime by the
// public `newLibraryWithSource:` API (tools/shdump technique). No Apple
// binary is inspected.

#include <metal_stdlib>
using namespace metal;

// Full-screen triangle, no vertex buffer, no varyings needed by any
// fragment function below.
vertex float4 v_full(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    return float4(pos[vid], 0.0, 1.0);
}

// PRIMARY CONSTRUCTION -- "f_eot_evict": source-level, this reads the
// tile's current value via the [[color(0)]] fragment INPUT mechanism
// (EXP-0029 HW-proved this MSL construct compiles, in general, to
// `tile_read`, byte0 0x67 byte+1 0x0e) and writes it back out unchanged
// via the ordinary fragment-output mechanism (EXP-0029 HW-proved this
// compiles, in general, to `frag_color_store`, byte0 0xe7 byte+1 0x06).
// Pilot exploration (work/, pre-freeze) found the *compiled bytes for
// this exact identity shader* contain NEITHER op -- the compiler proves
// the whole shader a no-op (output == input for the same attachment) and
// elides both instructions; see RESULTS.md. Both the behavioral pixel
// result and this structural finding are recorded as first-class
// evidence; see f_eot_combine for the non-elidable construction.
fragment float4 f_eot_evict(float4 dst [[color(0)]]) {
    return dst;
}

// FALSIFIER / PAIRED CONTROL -- "f_eot_ctrl": identical output-writing
// shape (same frag_color_store), but never declares a [[color(n)]]
// parameter, so it cannot possibly read the tile's resident value. Its
// output must be independent of whatever clear color establishes "dst"
// for the same render-pass configuration. If f_eot_evict's measured
// output were ALSO independent of dst, that would falsify "the tile read
// is load-bearing".
fragment float4 f_eot_ctrl(constant float4 &konst [[buffer(0)]]) {
    return konst;
}

// SECONDARY / STRUCTURAL-CHECK CONSTRUCTION -- "f_eot_combine": reads the
// tile's current value AND combines it with a genuinely runtime, non-
// constant-foldable second operand (a buffer value; no MTLBlendFactor
// descriptor is used anywhere in this harness -- the combination is
// ordinary explicit ALU in shader source). Verifies (see RESULTS.md) that
// f_eot_evict's compiled bytes contain NEITHER `tile_read` nor
// `frag_color_store` (the compiler proved the whole shader a no-op and
// elided both), whereas this shader's compiled bytes DO contain both --
// isolating exactly which authored shape actually exercises the hardware
// tilebuffer-read instruction versus which is silently optimized away.
fragment float4 f_eot_combine(float4 dst [[color(0)]], constant float4 &src [[buffer(0)]]) {
    return dst * 2.0 + src;
}
