#!/usr/bin/env python3
"""Generate the GLFS-A05 (early/late depth-stencil ordering) kernel family.
Authored generator -- output .metal files are the actual committed, hash-frozen
probes; this script just avoids hand-duplicating 6 near-identical files."""
import pathlib
HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "kernels"

TEMPLATE = """#include <metal_stdlib>
using namespace metal;
// GLFS-A05 probe: {desc}
// Vertex shader emits a big screen-covering triangle whose z is a purely linear
// function of ndc.x (so rasterized/interpolated z is EXACTLY z=clamp((ndcx+1)/2,0,1)
// at every covered pixel -- a deterministic left(pass)/right(fail) depth gradient
// against a Less-compare, clear=0.5 depth attachment).
struct VOut {{ float4 pos [[position]]; }};
vertex VOut v_main(uint vid [[vertex_id]]) {{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    float2 ndc = p * 2.0 - 1.0;
    float z = (ndc.x + 1.0) * 0.5;  // UNCLAMPED at vertices: the big-triangle trick
    // oversizes vertices beyond the visible NDC square on purpose; clamping the
    // per-vertex z here would distort the barycentric-interpolated in-triangle
    // gradient (verified empirically -- an earlier clamped version halved the
    // observed depth range). The offscreen part of the triangle where z>1 lies
    // entirely outside the visible x range and is clipped by the viewport, not by
    // this value.
    VOut o; o.pos = float4(ndc, z, 1.0); return o;
}}
struct Rec {{ uint marker; uint ran; uint depth_bits; uint pad0; }};
{early_attr}
fragment {ret_type} f_main(float4 pos [[position]],
                        device atomic_uint *ctr [[buffer(0)]],
                        device Rec *out [[buffer(1)]],
                        constant uint2 &dims [[buffer(2)]]){depth_out_decl}
{{
    uint px = (uint)pos.x, py = (uint)pos.y;
    uint idx = py * dims.x + px;
    atomic_fetch_add_explicit(&ctr[idx], 1u, memory_order_relaxed);
    out[idx].marker = idx + 1u;
    out[idx].ran = 1u;
    {discard_stmt}
    {depth_write_stmt}
    out[idx].depth_bits = as_type<uint>(pos.z);
    {return_stmt}
}}
"""

def make(name, early, discard, shaderdepth):
    early_attr = ""
    ret_type = "float4"
    depth_out_decl = ""
    depth_write_stmt = ""
    return_stmt = "return float4(0.75, 0.5, 0.25, 1.0);"
    if shaderdepth:
        ret_type = "FDOut"
        # depth(any) is required to combine explicit depth write with early_fragment_tests
        struct_decl = "struct FDOut { float4 color [[color(0)]]; float d [[depth(any)]]; };\n"
        depth_write_stmt = "FDOut fo; fo.color = float4(0.75, 0.5, 0.25, 1.0); fo.d = pos.z;"
        return_stmt = "return fo;"
    else:
        struct_decl = ""
    if early:
        early_attr = "[[early_fragment_tests]]"
    discard_stmt = ""
    if discard:
        discard_stmt = "if (py < dims.y / 2u) { discard_fragment(); }"
    text = struct_decl + TEMPLATE.format(
        desc=name, early_attr=early_attr, ret_type=ret_type,
        depth_out_decl="", discard_stmt=discard_stmt,
        depth_write_stmt=depth_write_stmt, return_stmt=return_stmt)
    (OUT / f"{name}.metal").write_text(text)
    print("wrote", name)

make("e_late_nodiscard", early=False, discard=False, shaderdepth=False)
make("e_early_nodiscard", early=True, discard=False, shaderdepth=False)
make("e_late_discard", early=False, discard=True, shaderdepth=False)
make("e_early_discard", early=True, discard=True, shaderdepth=False)
make("e_shaderdepth_nodiscard", early=False, discard=False, shaderdepth=True)
make("e_shaderdepth_discard", early=False, discard=True, shaderdepth=True)
