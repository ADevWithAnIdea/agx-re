#include <metal_stdlib>
using namespace metal;
// FS-12 remainder: does discard_fragment() suppress a [[sample_mask]] WRITE attempted by
// the demoted lane AFTER the discard (control flow permits this: discard_fragment() does
// not force an early return)? Whole-invocation discard (even-x lanes), N=4 MSAA,
// resolve-fraction technique (EXP-0091 GLFS-A01 msaa group): every covered lane
// unconditionally writes color=1 and [[sample_mask]]=0xF (all 4 bits) AFTER the
// even-x lanes' discard point. Oracle if suppression is complete: only odd-x (surviving)
// lanes' mask contribution reaches the tilebuffer -> resolved fraction = 1.0 (every
// SAMPLE of a surviving pixel is 4/4 covered by its own mask=0xF write; discarded
// pixels contribute nothing, resolved = 0 there -- both are "complete", the informative
// comparison is against the no-discard control which must read 1.0 everywhere).
struct VOut { float4 pos [[position]]; };
vertex VOut v_main(uint vid [[vertex_id]]) {
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}
struct FOut { float4 color [[color(0)]]; uint mask [[sample_mask]]; };
fragment FOut f_main(float4 pos [[position]]) {
    bool killme = ((uint)pos.x & 1u) == 0u;
    if (killme) discard_fragment();
    FOut o;
    o.color = float4(1,1,1,1);
    o.mask = 0xFu;
    return o;
}
fragment FOut f_control(float4 pos [[position]]) {
    FOut o;
    o.color = float4(1,1,1,1);
    o.mask = 0xFu;
    return o;
}
