"""EXP-0097 MSL kernel generator. Pure string templating, no device access --
safe to import/call in any tree state (selftest requirement). Every generated
kernel is written by run.py into work/gen/<case_id>.metal before invocation;
the generator functions themselves are the authored source of truth (their
SHA-256 is pinned via the case matrix + generated file, not this module,
since output varies by parameter -- the module itself is hashed instead,
see CAPTURE_CONTRACT.json authored_file_sha256).
"""

WCOMP = {"float": 1, "float2": 2, "float3": 3, "float4": 4, "half": 1, "half2": 2, "half3": 3, "half4": 4}


def gen_vary_scalar(n_declared, n_used, width="float"):
    """N_declared varyings of `width`; VS assigns all; FS sums only the
    first n_used (post-link liveness / declared-vs-consumed test)."""
    wc = WCOMP[width]
    is_half = width.startswith("half")
    fields = "\n".join(f"    {width} v{i} [[user(v{i})]];" for i in range(n_declared))
    def lit(i, c):
        val = f"{i}*0.0001+{c}*0.2"
        return f"{width}({val})" if is_half else val
    assigns = []
    for i in range(n_declared):
        if wc == 1:
            assigns.append(f"    o.v{i} = {lit(i,0)};")
        else:
            comps = ", ".join(f"{i}*0.0001+{c}*0.2" for c in range(wc))
            assigns.append(f"    o.v{i} = {width}({comps});")
    assigns_s = "\n".join(assigns)
    def readterm(i):
        base = f"in.v{i}.x" if wc > 1 else f"in.v{i}"
        return f"float({base})" if is_half else base
    sumterms = " + ".join(readterm(i) for i in range(n_used)) if n_used > 0 else "0.0"
    return f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{
    float4 position [[position]];
{fields}
}};
vertex VOut v_main(uint vid [[vertex_id]]) {{
    VOut o;
    float2 pos[3] = {{ float2(-1,-1), float2(3,-1), float2(-1,3) }};
    o.position = float4(pos[vid], 0, 1);
{assigns_s}
    return o;
}}
fragment float4 f_main(VOut in [[stage_in]]) {{
    float s = {sumterms};
    return float4(s, 0, 0, 1);
}}
"""


def gen_clip(n):
    """N clip_distance components (0 => omit the attribute entirely)."""
    if n == 0:
        clip_field, clip_assigns = "", ""
    else:
        clip_field = f"    float clip_dist [[clip_distance]] [{n}];"
        clip_assigns = "\n".join(f"    o.clip_dist[{i}] = 1.0;" for i in range(n))
    return f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{
    float4 position [[position]];
{clip_field}
}};
struct FIn {{
    float4 position [[position]];
}};
vertex VOut v_main(uint vid [[vertex_id]]) {{
    VOut o;
    float2 pos[3] = {{ float2(-1,-1), float2(3,-1), float2(-1,3) }};
    o.position = float4(pos[vid], 0, 1);
{clip_assigns}
    return o;
}}
fragment float4 f_main(FIn in [[stage_in]]) {{
    return float4(1,1,1,1);
}}
"""


def gen_vary_clip_combo(n_used, clip_n):
    """n_used live float varyings (declared==used) AND clip_n clip_distance
    components in the SAME vertex output -- tests whether the two namespaces
    share one budget or are independent."""
    fields = "\n".join(f"    float v{i} [[user(v{i})]];" for i in range(n_used))
    assigns = "\n".join(f"    o.v{i} = {i}*0.0001+0.1;" for i in range(n_used))
    clip_field = f"    float clip_dist [[clip_distance]] [{clip_n}];" if clip_n > 0 else ""
    clip_assigns = "\n".join(f"    o.clip_dist[{i}] = 1.0;" for i in range(clip_n))
    sumterms = " + ".join(f"in.v{i}" for i in range(n_used)) if n_used > 0 else "0.0"
    return f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{
    float4 position [[position]];
{fields}
{clip_field}
}};
struct FIn {{
    float4 position [[position]];
{fields}
}};
vertex VOut v_main(uint vid [[vertex_id]]) {{
    VOut o;
    float2 pos[3] = {{ float2(-1,-1), float2(3,-1), float2(-1,3) }};
    o.position = float4(pos[vid], 0, 1);
{assigns}
{clip_assigns}
    return o;
}}
fragment float4 f_main(FIn in [[stage_in]]) {{
    float s = {sumterms};
    return float4(s, 0, 0, 1);
}}
"""


def gen_cull():
    """Attempt to use [[cull_distance]] -- expected-negative structural probe
    (MSL does not define this attribute; frontend should warn/reject)."""
    return """#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
    float cull_dist [[cull_distance]] [1];
};
struct FIn {
    float4 position [[position]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float2 pos[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(pos[vid], 0, 1);
    o.cull_dist[0] = 1.0;
    return o;
}
fragment float4 f_main(FIn in [[stage_in]]) {
    return float4(1,1,1,1);
}
"""


# ---------------------------------------------------------------------------
# GLPRE-A03
# ---------------------------------------------------------------------------

def gen_position_baseline():
    """Fully-finite, unperturbed full-target triangle -- the TRUE positive
    control for the position_special family (expect 100% fill)."""
    return """#include <metal_stdlib>
using namespace metal;
struct VOut {
    float4 position [[position]];
};
vertex VOut v_main(uint vid [[vertex_id]]) {
    VOut o;
    float4 pos[3] = { float4(-1,-1,0,1), float4(3,-1,0,1), float4(-1,3,0,1) };
    o.position = pos[vid];
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    return float4(1,1,1,1);
}
"""


def gen_position_special(component, special_expr):
    """A full-target triangle where ONE vertex's `component` ('x','y','z','w')
    is replaced with `special_expr` (an MSL float literal/expression, e.g.
    '0.0/0.0' for NaN, '1.0/0.0' for +Inf, '-1.0/0.0' for -Inf,
    '-0.0' for signed zero). The other two vertices are unperturbed and the
    triangle covers the whole target at w=1 baseline, so a fully-finite
    control renders solid (1,1,1,1) everywhere; any deviation in coverage or
    color is the observable."""
    comp_idx = {"x": 0, "y": 1, "z": 2, "w": 3}[component]
    return f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{
    float4 position [[position]];
}};
vertex VOut v_main(uint vid [[vertex_id]]) {{
    VOut o;
    float4 pos[3] = {{ float4(-1,-1,0,1), float4(3,-1,0,1), float4(-1,3,0,1) }};
    float4 p = pos[vid];
    if (vid == 0) {{
        p[{comp_idx}] = ({special_expr});
    }}
    o.position = p;
    return o;
}}
fragment float4 f_main(VOut in [[stage_in]]) {{
    return float4(1,1,1,1);
}}
"""


def gen_point_size(size_expr):
    """A single point primitive centered in the target with
    [[point_size]] = size_expr (an MSL float literal/expression)."""
    return f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{
    float4 position [[position]];
    float psize [[point_size]];
}};
vertex VOut v_main(uint vid [[vertex_id]]) {{
    VOut o;
    o.position = float4(0, 0, 0, 1); // NDC center -> screen center of the target
    o.psize = ({size_expr});
    return o;
}}
fragment float4 f_main(VOut in [[stage_in]]) {{
    return float4(1,1,1,1);
}}
"""


def gen_layer(index_expr, layer_count):
    """One full-target triangle whose [[render_target_array_index]] =
    index_expr (an MSL uint literal/expression, possibly out of [0,layer_count))."""
    return f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{
    float4 position [[position]];
    uint layer [[render_target_array_index]];
}};
vertex VOut v_main(uint vid [[vertex_id]]) {{
    VOut o;
    float2 pos[3] = {{ float2(-1,-1), float2(3,-1), float2(-1,3) }};
    o.position = float4(pos[vid], 0, 1);
    o.layer = ({index_expr});
    return o;
}}
fragment float4 f_main(VOut in [[stage_in]]) {{
    return float4(1,1,1,1);
}}
"""


def gen_viewport(index_expr, viewport_count):
    """One full-NDC triangle whose [[viewport_array_index]] = index_expr
    (an MSL uint literal/expression, possibly out of [0,viewport_count))."""
    return f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{
    float4 position [[position]];
    uint vp [[viewport_array_index]];
}};
vertex VOut v_main(uint vid [[vertex_id]]) {{
    VOut o;
    float2 pos[3] = {{ float2(-1,-1), float2(3,-1), float2(-1,3) }};
    o.position = float4(pos[vid], 0, 1);
    o.vp = ({index_expr});
    return o;
}}
fragment float4 f_main(VOut in [[stage_in]]) {{
    return float4(1,1,1,1);
}}
"""


def gen_provoking(topology):
    """Flat-shaded color keyed by vertex_id, distinguishable per vertex:
    vid0 -> (1,0,0,1) red, vid1 -> (0,1,0,1) green, vid2/3 -> (0,0,1,1) blue.
    `topology` is 'list' or 'strip'; the harness selects MTLPrimitiveType via
    --topology and (for 'strip') uses 4 vertices (2 triangles) so the SECOND
    triangle's provoking-vertex behavior under shared-vertex reuse can be read
    from a second sample point."""
    if topology == "list":
        body = """
    float2 pos[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };
    o.position = float4(pos[vid], 0, 1);
    float4 colors[3] = { float4(1,0,0,1), float4(0,1,0,1), float4(0,0,1,1) };
    o.flatcolor = colors[vid];
"""
    else:  # strip: two triangles sharing an edge, covering two halves of the target
        body = """
    // Strip verts: 0,1,2,3 -> tri0=(0,1,2) tri1=(1,2,3) (Metal strip winding).
    float2 pos[4] = { float2(-1,-1), float2(-1,1), float2(0,-1), float2(0,1) };
    o.position = float4(pos[vid]*float2(1,1) + float2(vid>=2 ? 1.0 : 0.0, 0), 0, 1);
    float4 colors[4] = { float4(1,0,0,1), float4(0,1,0,1), float4(0,0,1,1), float4(1,1,0,1) };
    o.flatcolor = colors[vid];
"""
    return f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{
    float4 position [[position]];
    float4 flatcolor [[flat]] [[user(flatcolor)]];
}};
vertex VOut v_main(uint vid [[vertex_id]]) {{
    VOut o;
{body}
    return o;
}}
fragment float4 f_main(VOut in [[stage_in]]) {{
    return in.flatcolor;
}}
"""
