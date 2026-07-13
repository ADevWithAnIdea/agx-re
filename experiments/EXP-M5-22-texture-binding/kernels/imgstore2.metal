// EXP-M5-22 OBJ-3: clean same-color image-store slot byte-diff. Write the SAME
// buffer color c[0] to textures at slots 0..3 so the ONLY per-store difference is
// the texture slot -> isolates the slot field in the 18-byte `?5 ?? 11 04` store.
// CLEAN-ROOM: OUR OWN MSL. No Apple binary inspected.
#include <metal_stdlib>
using namespace metal;

kernel void k_wr4same(
    texture2d<float,access::write> t0 [[texture(0)]],
    texture2d<float,access::write> t1 [[texture(1)]],
    texture2d<float,access::write> t2 [[texture(2)]],
    texture2d<float,access::write> t3 [[texture(3)]],
    device const float4* c [[buffer(0)]], uint2 g [[thread_position_in_grid]]) {
    float4 v = c[0];
    t0.write(v, g); t1.write(v, g); t2.write(v, g); t3.write(v, g);
}
// argument-buffer (Tier-2) writable table: is the store index-agnostic like samples?
struct WrTable { array<texture2d<float,access::write>, 4> t; };
kernel void k_wrab0(constant WrTable& tt [[buffer(1)]], device const float4* c [[buffer(0)]], uint2 g [[thread_position_in_grid]]) { tt.t[0].write(c[0], g); }
kernel void k_wrab2(constant WrTable& tt [[buffer(1)]], device const float4* c [[buffer(0)]], uint2 g [[thread_position_in_grid]]) { tt.t[2].write(c[0], g); }
