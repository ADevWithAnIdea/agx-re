"""EXP-0123 deterministic MSL generation -- ONE case in, byte-identical
.metal text out (same case params always produce the same source, which is
what the cross-run byte-identity gate depends on). No Apple code is copied;
every template below is authored for this experiment.
"""
import math

FULLCOVER_VS = """#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; }};
vertex VOut vs_full(uint vid [[vertex_id]]) {{
    float2 pos[3] = {{ float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) }};
    VOut o; o.position = float4(pos[vid], {z}, 1.0);
    return o;
}}
"""


def _pixel_to_ndc_expr(w, h):
    return (w, h)


def gen(case, gen_dir):
    """Returns (binary, args_dict_without_op_or_case_id, metal_paths_written)."""
    kind = case["kind"]
    p = case["params"]
    cid = case["id"]
    fn = getattr(_G, "gen_" + kind)
    return fn(cid, p, gen_dir)


class _G:
    @staticmethod
    def gen_render_grid(cid, p, gen_dir):
        w, h = p["width"], p["height"]
        path = gen_dir / f"{cid}.metal"
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; }};
vertex VOut vs_line(uint vid [[vertex_id]]) {{
    float2 px[2] = {{ float2({p['x0']},{p['y0']}), float2({p['x1']},{p['y1']}) }};
    float2 p2 = px[vid];
    float2 ndc = float2( (p2.x/float({w}))*2.0-1.0, 1.0-(p2.y/float({h}))*2.0 );
    VOut o; o.position = float4(ndc, 0.0, 1.0);
    return o;
}}
fragment float4 fs_line() {{ return float4(1,1,1,1); }}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_line", "fragment_fn": "fs_line",
                "topology": p["topology"], "width": w, "height": h, "vcount": 2, "readback": "grid"}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_render_point_centered(cid, p, gen_dir):
        w, h = p["width"], p["height"]
        path = gen_dir / f"{cid}.metal"
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; float point_size [[point_size]]; }};
vertex VOut vs_pt(uint vid [[vertex_id]]) {{
    float2 p2 = float2({p['cx']}, {p['cy']});
    float2 ndc = float2((p2.x/float({w}))*2.0-1.0, 1.0-(p2.y/float({h}))*2.0);
    VOut o; o.position = float4(ndc, 0.0, 1.0); o.point_size = {p['size']};
    return o;
}}
fragment float4 fs_pt() {{ return float4(1,1,1,1); }}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_pt", "fragment_fn": "fs_pt",
                "topology": "point", "width": w, "height": h, "vcount": 1, "readback": "point"}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_render_fillmode(cid, p, gen_dir):
        w, h = p["width"], p["height"]
        path = gen_dir / f"{cid}.metal"
        topo = p["topology"]
        if topo == "triangle":
            body = "float2 pos[3] = { float2(-0.8,-0.8), float2(0.8,-0.8), float2(0.0,0.8) };"
            vcount = 3
        else:
            body = "float2 pos[2] = { float2(-0.8,-0.8), float2(0.8,0.8) };"
            vcount = 2
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; }};
vertex VOut vs_tri(uint vid [[vertex_id]]) {{
    {body}
    VOut o; o.position = float4(pos[vid], 0.0, 1.0); return o;
}}
fragment float4 fs_white() {{ return float4(1,1,1,1); }}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_tri", "fragment_fn": "fs_white",
                "topology": topo, "width": w, "height": h, "vcount": vcount,
                "fill_mode": p["fill_mode"], "readback": "point"}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_render_depthclip(cid, p, gen_dir):
        w, h = p["width"], p["height"]
        path = gen_dir / f"{cid}.metal"
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; }};
vertex VOut vs_tri(uint vid [[vertex_id]]) {{
    float2 pos[3] = {{ float2(-0.8,-0.8), float2(0.8,-0.8), float2(0.0,0.8) }};
    VOut o; o.position = float4(pos[vid], {p['z']}, 1.0);
    return o;
}}
fragment float4 fs_white() {{ return float4(1,1,1,1); }}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_tri", "fragment_fn": "fs_white",
                "topology": "triangle", "width": w, "height": h, "vcount": 3,
                "depth_clip_mode": p["depth_clip_mode"], "want_depth": True,
                "depth_compare": "always", "depth_write": True, "depth_clear": 0.4321,
                "readback": "point"}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_render_subpixel_tri(cid, p, gen_dir):
        w, h = p["width"], p["height"]
        path = gen_dir / f"{cid}.metal"
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; }};
vertex VOut vs_tri(uint vid [[vertex_id]]) {{
    float2 px[3] = {{ float2({p['x0']},{p['y0']}), float2({p['x1']},{p['y1']}), float2({p['x2']},{p['y2']}) }};
    float2 p2 = px[vid];
    float2 ndc = float2((p2.x/float({w}))*2.0-1.0, 1.0-(p2.y/float({h}))*2.0);
    VOut o; o.position = float4(ndc, 0.0, 1.0); return o;
}}
fragment float4 fs_white() {{ return float4(1,1,1,1); }}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_tri", "fragment_fn": "fs_white",
                "topology": "triangle", "width": w, "height": h, "vcount": 3, "readback": "grid"}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_render_coverage(cid, p, gen_dir):
        w, h = p["width"], p["height"]
        path = gen_dir / f"{cid}.metal"
        alpha = "1.0" if p["alpha"] else "0.0"
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; }};
vertex VOut vs_full(uint vid [[vertex_id]]) {{
    float2 pos[3] = {{ float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) }};
    VOut o; o.position = float4(pos[vid], 0.5, 1.0); return o;
}}
fragment float4 fs_cov() {{ return float4(1,1,1,{alpha}); }}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_full", "fragment_fn": "fs_cov",
                "topology": "triangle", "width": w, "height": h, "vcount": 3,
                "sample_count": p["sample_count"], "alpha_to_coverage": p["alpha_to_coverage"],
                "want_depth": True, "depth_compare": "always", "depth_write": True,
                "depth_clear": 0.9, "want_occlusion": True, "readback": "point"}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_multiattach(cid, p, gen_dir):
        n = p["n"]
        path = gen_dir / f"{cid}.metal"
        outs = "\n".join(f"    float4 c{i} [[color({i})]];" for i in range(min(n, 8)))
        rets = "\n".join(f"    o.c{i} = float4(float({i})/8.0, 0.5, 0.5, 1.0);" for i in range(min(n, 8)))
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; }};
struct FOut {{
{outs}
}};
vertex VOut vs_tri(uint vid [[vertex_id]]) {{
    float2 pos[3] = {{ float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) }};
    VOut o; o.position = float4(pos[vid], 0.0, 1.0); return o;
}}
fragment FOut fs_multi() {{
    FOut o;
{rets}
    return o;
}}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_tri", "fragment_fn": "fs_multi",
                "n_attachments": n, "width": p["width"], "height": p["height"]}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_viewport_functional(cid, p, gen_dir):
        n = p["n"]
        path = gen_dir / f"{cid}.metal"
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; uint vpidx [[viewport_array_index]]; }};
vertex VOut vs_vp(uint vid [[vertex_id]], uint iid [[instance_id]]) {{
    float2 pos[3] = {{ float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) }};
    VOut o; o.position = float4(pos[vid], 0.0, 1.0); o.vpidx = iid % {n}u;
    return o;
}}
fragment float4 fs_white() {{ return float4(1,1,1,1); }}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_vp", "fragment_fn": "fs_white",
                "topology": "triangle", "width": n, "height": 2, "vcount": 3,
                "instance_count": n, "viewport_count": n, "readback": "grid"}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_texcreate(cid, p, gen_dir):
        args = {"texture_type": p["type"], "pixel_format": "r8unorm",
                "width": p["width"], "height": p["height"],
                "mip_level_count": p.get("mips", 1), "do_render": False}
        if p["type"] == "3d":
            args["depth"] = p["depth"]
        if p["type"] == "2d_array":
            args["depth"] = p["depth"]
        return "rasterprobe", args, []

    @staticmethod
    def gen_bufferindex_compile(cid, p, gen_dir):
        idx = p["index"]
        path = gen_dir / f"{cid}.metal"
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; }};
vertex VOut vs_full(uint vid [[vertex_id]]) {{
    float2 pos[3] = {{ float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) }};
    VOut o; o.position = float4(pos[vid], 0.0, 1.0); return o;
}}
fragment float4 fs_bidx(constant float4& v [[buffer({idx})]]) {{
    return v;
}}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_full", "fragment_fn": "fs_bidx",
                "stage": "fragment", "index": idx, "buffer_value": 0.5}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_texindex_compile(cid, p, gen_dir):
        idx = p["index"]
        path = gen_dir / f"{cid}.metal"
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 position [[position]]; }};
vertex VOut vs_full(uint vid [[vertex_id]]) {{
    float2 pos[3] = {{ float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) }};
    VOut o; o.position = float4(pos[vid], 0.0, 1.0); return o;
}}
fragment float4 fs_tbind(texture2d<float> tex [[texture({idx})]]) {{
    constexpr sampler s(coord::pixel, filter::nearest);
    return tex.sample(s, float2(0,0));
}}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_full", "fragment_fn": "fs_tbind", "index": idx}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_bytesconst(cid, p, gen_dir):
        path = gen_dir / f"{cid}.metal"
        path.write_text("""#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut vs_full(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) };
    VOut o; o.position = float4(pos[vid], 0.0, 1.0); return o;
}
fragment float4 fs_bytes(constant uchar* buf [[buffer(0)]], constant uint& checkIdx [[buffer(1)]]) {
    return float4(float(buf[0])/255.0, float(buf[checkIdx])/255.0, 0,1);
}
""")
        # checkIdx (buffer 1) was confirmed by direct exploration to NOT move
        # the per-call inline-constant boundary (single- and dual-setBytes
        # variants both broke at exactly length=32753) -- using it here lets
        # the verdict check BOTH the first and the exact last byte of the
        # blob, not just byte[0..1], while still exercising the real boundary.
        args = {"metal_source": str(path), "vertex_fn": "vs_full", "fragment_fn": "fs_bytes",
                "stage": "fragment", "length": p["length"], "second_buffer": True}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_bufferalign(cid, p, gen_dir):
        path = gen_dir / f"{cid}.metal"
        path.write_text("""#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; };
vertex VOut vs_full(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-2.0,-2.0), float2(2.0,-2.0), float2(0.0,2.0) };
    VOut o; o.position = float4(pos[vid], 0.0, 1.0); return o;
}
fragment float4 fs_bufalign(constant uchar* buf [[buffer(0)]]) {
    return float4(float(buf[0])/255.0, float(buf[1])/255.0, float(buf[2])/255.0, float(buf[3])/255.0);
}
""")
        args = {"metal_source": str(path), "vertex_fn": "vs_full", "fragment_fn": "fs_bufalign",
                "offset": p["offset"]}
        return "rasterprobe", args, [path]

    @staticmethod
    def gen_compute_threadgroup(cid, p, gen_dir):
        path = gen_dir / f"{cid}.metal"
        path.write_text("""#include <metal_stdlib>
using namespace metal;
kernel void cs_tg(device uint* out [[buffer(0)]],
                   uint tid [[thread_position_in_grid]],
                   uint tew [[thread_execution_width]],
                   uint lane [[thread_index_in_simdgroup]]) {
    out[tid] = tew * 1000 + lane;
}
""")
        tg = p["tg"]
        args = {"metal_source": str(path), "kernel_fn": "cs_tg", "tg_x": tg, "grid_x": tg,
                "dispatch_mode": "threadgroups", "out_count": 8}
        return "computeprobe", args, [path]

    @staticmethod
    def gen_compute_tgmem(cid, p, gen_dir):
        path = gen_dir / f"{cid}.metal"
        path.write_text("""#include <metal_stdlib>
using namespace metal;
kernel void cs_tgmem(device uint* out [[buffer(0)]],
                      threadgroup uchar* dyn [[threadgroup(0)]],
                      uint tid [[thread_position_in_grid]]) {
    if (tid == 0) { dyn[0] = 7; out[0] = (uint)dyn[0]; }
}
""")
        args = {"metal_source": str(path), "kernel_fn": "cs_tgmem", "tg_x": 32, "grid_x": 32,
                "dispatch_mode": "threadgroups", "dyn_tg_mem_bytes": p["bytes"], "out_count": 4}
        return "computeprobe", args, [path]

    @staticmethod
    def gen_compute_simdwidth(cid, p, gen_dir):
        path = gen_dir / f"{cid}.metal"
        path.write_text("""#include <metal_stdlib>
using namespace metal;
kernel void cs_simd(device uint* out [[buffer(0)]],
                     uint tid [[thread_position_in_grid]],
                     uint tew [[thread_execution_width]],
                     uint lane [[thread_index_in_simdgroup]]) {
    out[tid] = tew * 1000 + lane;
}
""")
        tg = p["tg"]
        args = {"metal_source": str(path), "kernel_fn": "cs_simd", "tg_x": tg, "grid_x": tg,
                "dispatch_mode": "threadgroups", "out_count": tg}
        return "computeprobe", args, [path]

    @staticmethod
    def gen_compute_simdshuffle(cid, p, gen_dir):
        src = p["src"]
        path = gen_dir / f"{cid}.metal"
        path.write_text(f"""#include <metal_stdlib>
using namespace metal;
kernel void cs_shuf(device uint* out [[buffer(0)]], uint tid [[thread_position_in_grid]], uint lane [[thread_index_in_simdgroup]]) {{
    uint v = lane * 10 + 1;
    uint got = simd_shuffle(v, (uint){src});
    out[tid] = got;
}}
""")
        args = {"metal_source": str(path), "kernel_fn": "cs_shuf", "tg_x": 32, "grid_x": 32,
                "dispatch_mode": "threadgroups", "out_count": 4}
        return "computeprobe", args, [path]
