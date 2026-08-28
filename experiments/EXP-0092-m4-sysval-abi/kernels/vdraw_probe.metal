// EXP-0092 vdraw_probe: GLIO-A03 draw-parameter ABI probe.
//
// A vertex function that reads the four MSL vertex-stage builtins in
// question (vertex_id, instance_id, base_vertex, base_instance) and appends
// one (vid,iid,bv,bi) record per invocation to a device buffer via an atomic
// counter, instead of relying on rasterized pixel output. This lets a single
// indexed/instanced draw with host-controlled baseVertex/firstInstance and a
// host-chosen (non-identity) index buffer directly expose, per invocation,
// whether vertex_id/instance_id already fold in the base and whether
// base_vertex/base_instance equal exactly the host-supplied draw parameters
// -- all compared to a host-computed expected set, never a GPU-inferred one.
//
// The position output is a fixed degenerate point; only the buffer side
// effect (an explicit, required write to externally visible memory) is under
// test, so primitive assembly/rasterization outcome is irrelevant. Metal
// cannot legally optimize away the atomic increment + store: it is a
// visible side effect on a caller-supplied writable buffer.
#include <metal_stdlib>
using namespace metal;

struct VOut {
    float4 position [[position]];
    float point_size [[point_size]];
};

vertex VOut v_main(uint vid              [[vertex_id]],
                    uint iid              [[instance_id]],
                    uint bv               [[base_vertex]],
                    uint bi               [[base_instance]],
                    device uint4* out     [[buffer(0)]],
                    device atomic_uint* counter [[buffer(1)]]) {
    uint slot = atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    out[slot] = uint4(vid, iid, bv, bi);
    VOut o;
    o.position = float4(0.0, 0.0, 0.0, 1.0);
    o.point_size = 1.0;
    return o;
}

fragment float4 f_main() {
    return float4(0.0, 0.0, 0.0, 0.0);
}
