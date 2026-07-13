// EXP-M5-22 OBJ-3: M5 compute image-store (texture2d<...,access::write>.write).
// On M5 this compiles to the `?4 80 0?` family (NOT the A18 0xd7). We byte-diff
// const-color vs buffer-color writes to separate the immediate-materialisation ops
// from the actual STORE op, and vary the texture slot / coord to type the fields.
// Also a trivial vertex to test whether `24 80 03` is image-specific or a general op.
// CLEAN-ROOM: OUR OWN MSL. No Apple binary inspected.
#include <metal_stdlib>
using namespace metal;

// (1) minimal 1-texture write of a COMPILE-TIME-CONST color.
kernel void k_wr1(texture2d<float,access::write> w [[texture(0)]], uint2 g [[thread_position_in_grid]]) {
    w.write(float4(1,2,3,4), g);
}
// (2) write of a BUFFER-sourced color -> no immediate-materialisation ops.
kernel void k_wrbuf(texture2d<float,access::write> w [[texture(0)]],
    device const float4* c [[buffer(0)]], uint2 g [[thread_position_in_grid]]) {
    w.write(c[0], g);
}
// (3) write buffer color to texture SLOT 1 (t0 also bound & written to keep it live) -> slot byte-diff vs (2).
kernel void k_wrbuf_t1(texture2d<float,access::write> t0 [[texture(0)]],
    texture2d<float,access::write> w [[texture(1)]],
    device const float4* c [[buffer(0)]], uint2 g [[thread_position_in_grid]]) {
    t0.write(c[1], g);
    w.write(c[0], g);
}
// (4) write buffer color to texture SLOT 2 (t0,t1 live) -> slot byte-diff for slot>=2.
kernel void k_wrbuf_t2(texture2d<float,access::write> t0 [[texture(0)]],
    texture2d<float,access::write> t1 [[texture(1)]],
    texture2d<float,access::write> w [[texture(2)]],
    device const float4* c [[buffer(0)]], uint2 g [[thread_position_in_grid]]) {
    t0.write(c[1], g); t1.write(c[2], g); w.write(c[0], g);
}
// (5) different coordinate (g + const) to type the coord operand.
kernel void k_wrbuf_coord(texture2d<float,access::write> w [[texture(0)]],
    device const float4* c [[buffer(0)]], uint2 g [[thread_position_in_grid]]) {
    w.write(c[0], g + uint2(5,7));
}
// (6) uint texture write (type variant).
kernel void k_wru(texture2d<uint,access::write> w [[texture(0)]],
    device const uint4* c [[buffer(0)]], uint2 g [[thread_position_in_grid]]) {
    w.write(c[0], g);
}
// (7) trivial vertex passthrough: is `24 80 03` present with NO image op?
struct VOut { float4 pos [[position]]; };
vertex VOut v_pos(uint vid [[vertex_id]], device const float2* vb [[buffer(0)]]) {
    VOut o; o.pos = float4(vb[vid], 0, 1); return o;
}
// (8) trivial fragment (constant output) — control.
fragment float4 f_red() { return float4(1,0,0,1); }
