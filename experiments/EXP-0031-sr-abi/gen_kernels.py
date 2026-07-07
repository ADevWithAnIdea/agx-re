#!/usr/bin/env python3
# EXP-0031 kernel generator (OWN-SHADER).
# Emits one MSL file per built-in, each reading EXACTLY ONE built-in and storing
# it to a CONSTANT address (out[0]) so the ONLY get_sr in the program is the one
# under study. A second "indexed" variant (out[tid]=builtin) is used for HW
# validation dispatches. Graphics (vertex/fragment) shaders read one built-in and
# route it through the required output (position / color).
import os, json, sys

OUT = os.path.join(os.path.dirname(__file__), "kernels")
os.makedirs(OUT, exist_ok=True)

manifest = []  # (file, kind, funcs..., builtin, note)

# ---------------------------------------------------------------------------
# COMPUTE built-ins.  kind="compute"; func always "k".
# expr = MSL expression producing a uint from the built-in argument list.
# argdecl = the kernel argument declaration carrying the attribute(s).
# ---------------------------------------------------------------------------
compute = [
    # name,                       argdecl,                                              expr
    ("tpig_x",  "uint3 v [[thread_position_in_grid]]",            "v.x"),
    ("tpig_y",  "uint3 v [[thread_position_in_grid]]",            "v.y"),
    ("tpig_z",  "uint3 v [[thread_position_in_grid]]",            "v.z"),
    ("tpit_x",  "uint3 v [[thread_position_in_threadgroup]]",     "v.x"),
    ("tpit_y",  "uint3 v [[thread_position_in_threadgroup]]",     "v.y"),
    ("tpit_z",  "uint3 v [[thread_position_in_threadgroup]]",     "v.z"),
    ("tgpig_x", "uint3 v [[threadgroup_position_in_grid]]",       "v.x"),
    ("tgpig_y", "uint3 v [[threadgroup_position_in_grid]]",       "v.y"),
    ("tgpig_z", "uint3 v [[threadgroup_position_in_grid]]",       "v.z"),
    ("tptg_x",  "uint3 v [[threads_per_threadgroup]]",            "v.x"),
    ("tptg_y",  "uint3 v [[threads_per_threadgroup]]",            "v.y"),
    ("tptg_z",  "uint3 v [[threads_per_threadgroup]]",            "v.z"),
    ("tgpg_x",  "uint3 v [[threadgroups_per_grid]]",              "v.x"),
    ("tgpg_y",  "uint3 v [[threadgroups_per_grid]]",              "v.y"),
    ("tgpg_z",  "uint3 v [[threadgroups_per_grid]]",              "v.z"),
    ("tidx_tg", "uint v [[thread_index_in_threadgroup]]",         "v"),
    ("lane",    "uint v [[thread_index_in_simdgroup]]",           "v"),   # simd_lane_id
    ("sgid",    "uint v [[simdgroup_index_in_threadgroup]]",      "v"),   # simd_group_id
    ("simdw",   "uint v [[threads_per_simdgroup]]",               "v"),
    ("nsimd",   "uint v [[simdgroups_per_threadgroup]]",          "v"),
    ("qlane",   "uint v [[thread_index_in_quadgroup]]",           "v"),
    ("qgid",    "uint v [[quadgroup_index_in_threadgroup]]",      "v"),
]

for name, argdecl, expr in compute:
    # constant-address isolation variant
    src = (
        "#include <metal_stdlib>\n"
        "using namespace metal;\n"
        f"kernel void k(device uint* out [[buffer(0)]],\n"
        f"              {argdecl}) {{\n"
        f"    out[0] = {expr};\n"
        "}\n"
    )
    fn = f"c_{name}.metal"
    with open(os.path.join(OUT, fn), "w") as f:
        f.write(src)
    manifest.append({"file": fn, "kind": "compute", "func": "k",
                     "builtin": name, "variant": "const-addr"})

# indexed variant for a couple of scalar built-ins (HW validation: out[gid]=builtin)
hwval = [
    ("hw_tpig", "uint gid [[thread_position_in_grid]]",
                "uint v [[thread_position_in_grid]]", "v"),
    ("hw_tidx", "uint gid [[thread_position_in_grid]]",
                "uint v [[thread_index_in_threadgroup]]", "v"),
    ("hw_lane", "uint gid [[thread_position_in_grid]]",
                "uint v [[thread_index_in_simdgroup]]", "v"),
    ("hw_tgid", "uint gid [[thread_position_in_grid]]",
                "uint v [[threadgroup_position_in_grid]]", "v"),
    ("hw_tptg", "uint gid [[thread_position_in_grid]]",
                "uint v [[threads_per_threadgroup]]", "v"),
    ("hw_simdw","uint gid [[thread_position_in_grid]]",
                "uint v [[threads_per_simdgroup]]", "v"),
]
for name, gidarg, varg, expr in hwval:
    src = (
        "#include <metal_stdlib>\n"
        "using namespace metal;\n"
        f"kernel void k(device uint* out [[buffer(0)]],\n"
        f"              {gidarg},\n"
        f"              {varg}) {{\n"
        f"    out[gid] = {expr};\n"
        "}\n"
    )
    fn = f"{name}.metal"
    with open(os.path.join(OUT, fn), "w") as f:
        f.write(src)
    manifest.append({"file": fn, "kind": "compute", "func": "k",
                     "builtin": name, "variant": "indexed-hwval"})

# ---------------------------------------------------------------------------
# VERTEX built-ins.  kind="render"; needs a fragment too. func names v_main/f_main.
# Each VS reads one built-in and routes it into the position output so it is USED.
# ---------------------------------------------------------------------------
FRAG = (
    "fragment float4 f_main() {\n"
    "    return float4(1.0, 0.5, 0.25, 1.0);\n"
    "}\n"
)

# baseline VS reading NOTHING but a constant (to diff against)
vbase = (
    "#include <metal_stdlib>\n"
    "using namespace metal;\n"
    "vertex float4 v_main() {\n"
    "    return float4(0.0, 0.0, 0.0, 1.0);\n"
    "}\n" + FRAG
)
with open(os.path.join(OUT, "v_base.metal"), "w") as f:
    f.write(vbase)
manifest.append({"file": "v_base.metal", "kind": "render", "vfunc": "v_main",
                 "ffunc": "f_main", "builtin": "none", "variant": "vs-baseline"})

vertex = [
    ("vid",   "uint vid [[vertex_id]]",       "float(vid)"),
    ("iid",   "uint iid [[instance_id]]",     "float(iid)"),
    ("bvtx",  "uint bv [[base_vertex]]",      "float(bv)"),
    ("binst", "uint bi [[base_instance]]",    "float(bi)"),
    # combos to see whether both preload into adjacent regs
    ("vid_iid", "uint vid [[vertex_id]], uint iid [[instance_id]]", "float(vid) + float(iid)*0.0"),
]
for name, argdecl, expr in vertex:
    src = (
        "#include <metal_stdlib>\n"
        "using namespace metal;\n"
        f"vertex float4 v_main({argdecl}) {{\n"
        f"    return float4({expr}, 0.0, 0.0, 1.0);\n"
        "}\n" + FRAG
    )
    fn = f"v_{name}.metal"
    with open(os.path.join(OUT, fn), "w") as f:
        f.write(src)
    manifest.append({"file": fn, "kind": "render", "vfunc": "v_main",
                     "ffunc": "f_main", "builtin": name, "variant": "vs"})

# ---------------------------------------------------------------------------
# FRAGMENT built-ins.  Minimal VS (constant position); FS reads one built-in.
# ---------------------------------------------------------------------------
VS_MIN = (
    "#include <metal_stdlib>\n"
    "using namespace metal;\n"
    "vertex float4 v_main(uint vid [[vertex_id]]) {\n"
    "    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };\n"
    "    return float4(p[vid], 0.0, 1.0);\n"
    "}\n"
)

# FS baseline (constant) to diff against
with open(os.path.join(OUT, "f_base.metal"), "w") as f:
    f.write(VS_MIN + FRAG)
manifest.append({"file": "f_base.metal", "kind": "render", "vfunc": "v_main",
                 "ffunc": "f_main", "builtin": "none", "variant": "fs-baseline"})

frag = [
    # name,   fs-arg-decl,                                     body-return
    ("pos",    "float4 pos [[position]]",
               "float4(pos.x, pos.y, pos.z, pos.w)"),
    ("sampid", "uint sid [[sample_id]]",
               "float4(float(sid), 0, 0, 1)"),
    ("facing", "bool ff [[front_facing]]",
               "float4(ff ? 1.0 : 0.0, 0, 0, 1)"),
    ("ptcoord","float2 pc [[point_coord]]",
               "float4(pc.x, pc.y, 0, 1)"),
    ("primid", "uint pid [[primitive_id]]",
               "float4(float(pid), 0, 0, 1)"),
]
for name, argdecl, ret in frag:
    src = VS_MIN + (
        f"fragment float4 f_main({argdecl}) {{\n"
        f"    return {ret};\n"
        "}\n"
    )
    fn = f"f_{name}.metal"
    with open(os.path.join(OUT, fn), "w") as f:
        f.write(src)
    manifest.append({"file": fn, "kind": "render", "vfunc": "v_main",
                     "ffunc": "f_main", "builtin": name, "variant": "fs"})

# barycentric_coord needs a stage_in varying + interpolant; separate file
bary = (
    "#include <metal_stdlib>\n"
    "using namespace metal;\n"
    "vertex float4 v_main(uint vid [[vertex_id]]) {\n"
    "    float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };\n"
    "    return float4(p[vid], 0.0, 1.0);\n"
    "}\n"
    "struct BaryIn {\n"
    "    float3 bc [[barycentric_coord]];\n"
    "};\n"
    "fragment float4 f_main(BaryIn in) {\n"
    "    return float4(in.bc, 1.0);\n"
    "}\n"
)
with open(os.path.join(OUT, "f_bary.metal"), "w") as f:
    f.write(bary)
manifest.append({"file": "f_bary.metal", "kind": "render", "vfunc": "v_main",
                 "ffunc": "f_main", "builtin": "bary", "variant": "fs"})

with open(os.path.join(os.path.dirname(__file__), "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=1)

print(f"wrote {len(manifest)} kernels to {OUT}")
for m in manifest:
    print(" ", m["file"], m["kind"], m.get("builtin"))
