// EXP-M4-02 msl_probes.m — M4 MSL feature compile-accept/reject battery.
// Clean-room category: OWN-SHADER. Every source below is OUR OWN MSL. We only
// call newLibraryWithSource: (runtime compile) and record whether the device's
// compiler ACCEPTS or REJECTS it, plus the first diagnostic line. No GPU work is
// submitted; no Apple binary is inspected.  The A18-expected column is the
// documented A18 Pro result (docs/capability-{matrix,completeness}.md) so the
// re-run can be scored IDENTICAL / DELTA per probe.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation msl_probes.m -o msl_probes
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

typedef struct { const char *name; const char *a18; const char *src; } Probe;

static Probe PROBES[] = {

// ---------- data types / ALU ----------
{"bfloat_alu", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device bfloat* o [[buffer(0)]], device bfloat* a [[buffer(1)]], uint i [[thread_position_in_grid]]){\n"
 "  bfloat x = a[i]; x = x*bfloat(2.0)+bfloat(1.0); o[i]=x; }\n"},

{"half_alu", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device half* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ half2 v=half2(o[i]); v=v*half2(2.0)+half2(1.0); o[i]=v.x+v.y; }\n"},

{"long64_int_alu", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device long* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ long a=o[i]; a=a*3+7; o[i]=a; }\n"},

// ---------- simdgroup_matrix (cooperative matrix) ----------
{"simdgroup_matrix_f16", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device half* o [[buffer(0)]]){\n"
 "  simdgroup_half8x8 a(1.0), b(2.0), c(0.0);\n"
 "  simdgroup_multiply_accumulate(c,a,b,c);\n"
 "  simdgroup_store(c,o,8); }\n"},

{"simdgroup_matrix_f32", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device float* o [[buffer(0)]]){\n"
 "  simdgroup_float8x8 a(1.0), b(2.0), c(0.0);\n"
 "  simdgroup_multiply_accumulate(c,a,b,c);\n"
 "  simdgroup_store(c,o,8); }\n"},

// NOTE: the simdgroup_matrix<bfloat,...> scalar-broadcast constructor has no
// implicit float->bfloat conversion (unlike half/float typedefs), so a bare
// `a(1.0)` literal fails to resolve at the HEADER/LANGUAGE level (not a HW gate).
// Use `bfloat(1.0)` / real load+matmul path — this is the true bf16-matrix test.
{"simdgroup_matrix_bf16", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device float* o [[buffer(0)]], device const bfloat* A [[buffer(1)]], device const bfloat* B [[buffer(2)]]){\n"
 "  simdgroup_matrix<bfloat,8,8> a,b; simdgroup_load(a,A,8); simdgroup_load(b,B,8);\n"
 "  simdgroup_matrix<float,8,8> c(0.0);\n"
 "  simdgroup_multiply_accumulate(c,a,b,c);\n"
 "  simdgroup_store(c,o,8); }\n"},

{"simdgroup_matrix_int8", "REJECTED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device int* o [[buffer(0)]]){\n"
 "  simdgroup_matrix<char,8,8> a(1), b(2);\n"
 "  simdgroup_matrix<int,8,8> c(0);\n"
 "  simdgroup_multiply_accumulate(c,a,b,c);\n"
 "  simdgroup_store(c,o,8); }\n"},

{"simdgroup_matrix_int32", "REJECTED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device int* o [[buffer(0)]]){\n"
 "  simdgroup_matrix<int,8,8> a(1), b(2), c(0);\n"
 "  simdgroup_multiply_accumulate(c,a,b,c);\n"
 "  simdgroup_store(c,o,8); }\n"},

// ---------- atomics ----------
{"atomic_float_add_device", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device atomic<float>* p [[buffer(0)]]){ atomic_fetch_add_explicit(p, 1.0f, memory_order_relaxed); }\n"},

{"atomic_float_min_device", "REJECTED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device atomic<float>* p [[buffer(0)]]){ atomic_fetch_min_explicit(p, 1.0f, memory_order_relaxed); }\n"},

{"atomic_uint64_add", "REJECTED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device atomic<uint64_t>* p [[buffer(0)]]){ atomic_fetch_add_explicit(p, (uint64_t)1, memory_order_relaxed); }\n"},

{"atomic_ulong_min", "REJECTED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device atomic<ulong>* p [[buffer(0)]]){ atomic_fetch_min_explicit(p, (ulong)1, memory_order_relaxed); }\n"},

{"atomic_int_add", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device atomic_uint* p [[buffer(0)]]){ atomic_fetch_add_explicit(p, 1u, memory_order_relaxed); }\n"},

// ---------- subgroup / quad ----------
{"quad_ops", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){\n"
 "  float v=o[i]; v=quad_shuffle(v,0)+quad_broadcast(v,1); o[i]=v; }\n"},

{"simd_prefix_scan", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){\n"
 "  float v=o[i]; v=simd_prefix_inclusive_sum(v)+simd_prefix_exclusive_sum(v); o[i]=v; }\n"},

{"simd_shuffle_and_fill", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){\n"
 "  float v=o[i]; v=simd_shuffle_and_fill_down(v,1.0f,1)+simd_shuffle_and_fill_up(v,2.0f,1); o[i]=v; }\n"},

{"simd_is_helper_thread_frag", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "fragment float4 f(){ return simd_is_helper_thread()?float4(1):float4(0); }\n"},

{"simd_ballot_vote", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device uint* o [[buffer(0)]], uint i [[thread_position_in_grid]]){\n"
 "  simd_vote b=simd_ballot(o[i]!=0u); o[i]=(uint)((simd_vote::vote_t)b); }\n"},

// ---------- ray tracing ----------
{"rt_intersector", "COMPILED",
 "#include <metal_stdlib>\n#include <metal_raytracing>\nusing namespace metal;\nusing namespace raytracing;\n"
 "kernel void k(instance_acceleration_structure accel [[buffer(0)]], device float* o [[buffer(1)]], device float3* dir [[buffer(2)]], uint i [[thread_position_in_grid]]){\n"
 "  ray r; r.origin=float3(0); r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;\n"
 "  intersector<triangle_data, instancing> it;\n"
 "  intersection_result<triangle_data, instancing> res = it.intersect(r, accel);\n"
 "  o[i] = res.distance; }\n"},

{"rt_intersection_query_inline", "COMPILED",
 "#include <metal_stdlib>\n#include <metal_raytracing>\nusing namespace metal;\nusing namespace raytracing;\n"
 "kernel void k(primitive_acceleration_structure accel [[buffer(0)]], device float* o [[buffer(1)]], device float3* dir [[buffer(2)]], uint i [[thread_position_in_grid]]){\n"
 "  ray r; r.origin=float3(0); r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;\n"
 "  intersection_query<triangle_data> q; q.reset(r, accel);\n"
 "  while (q.next()) {}\n"
 "  o[i] = q.get_committed_distance(); }\n"},

{"rt_custom_intersection_fn", "COMPILED",
 "#include <metal_stdlib>\n#include <metal_raytracing>\nusing namespace metal;\nusing namespace raytracing;\n"
 "struct BR{ bool a [[accept_intersection]]; bool c [[continue_search]]; float d [[distance]]; };\n"
 "[[intersection(bounding_box, triangle_data)]]\n"
 "BR isect(float minD [[min_distance]], float maxD [[max_distance]], ray_data float2& pl [[payload]]){ pl+=float2(1,2); return {true,false, minD+0.5f*(maxD-minD)}; }\n"
 "kernel void k(primitive_acceleration_structure accel [[buffer(0)]], intersection_function_table<triangle_data> ft [[buffer(1)]], device float* o [[buffer(2)]], device float3* dir [[buffer(3)]], uint i [[thread_position_in_grid]]){\n"
 "  ray r; r.origin=float3(0); r.direction=dir[i]; r.min_distance=0; r.max_distance=INFINITY;\n"
 "  intersector<triangle_data> it; float2 pl=float2(0);\n"
 "  intersection_result<triangle_data> res = it.intersect(r, accel, ft, pl);\n"
 "  o[i] = res.distance + pl.x; }\n"},

// ---------- mesh / geometry pipeline ----------
{"mesh_object_pipeline", "COMPILED",
 "#include <metal_stdlib>\n#include <metal_mesh>\nusing namespace metal;\n"
 "struct VOut{ float4 position [[position]]; float4 color; };\n"
 "struct POut{ float3 pnormal [[flat]]; };\n"
 "using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;\n"
 "struct Payload{ float scale; };\n"
 "[[object, max_total_threadgroups_per_mesh_grid(1)]]\n"
 "void obj_main(object_data Payload& pl [[payload]], mesh_grid_properties mgp, uint tid [[thread_position_in_grid]]){ pl.scale=1.0f; mgp.set_threadgroups_per_grid(uint3(1,1,1)); }\n"
 "[[mesh, max_total_threads_per_threadgroup(3)]]\n"
 "void mesh_main(tri_mesh out, const object_data Payload& pl [[payload]], uint lane [[thread_index_in_threadgroup]]){\n"
 "  if(lane==0) out.set_primitive_count(1);\n"
 "  float2 P[3]={float2(-0.5,-0.5),float2(0.5,-0.5),float2(0.0,0.5)};\n"
 "  VOut v; v.position=float4(P[lane]*pl.scale,0,1); v.color=float4(0,1,0,1); out.set_vertex(lane,v); out.set_index(lane,uchar(lane));\n"
 "  if(lane==0){ POut p; p.pnormal=float3(0,0,1); out.set_primitive(0,p);} }\n"},

// ---------- tessellation (post-tess vertex fn, drawPatches path) ----------
{"tessellation_posttess_vertex", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "struct CP{ float4 position [[attribute(0)]]; };\n"
 "struct PatchIn{ patch_control_point<CP> cp; };\n"
 "struct VOut{ float4 position [[position]]; };\n"
 "[[patch(triangle,3)]] vertex VOut pv(PatchIn in [[stage_in]], float3 bary [[position_in_patch]]){\n"
 "  float4 p = in.cp[0].position*bary.x + in.cp[1].position*bary.y + in.cp[2].position*bary.z;\n"
 "  VOut o; o.position=p; return o; }\n"},

{"tessellation_factors_compute", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "struct TriF{ half edge[3]; half inside; };\n"
 "kernel void tf(device TriF* f [[buffer(0)]], constant float& l [[buffer(1)]], uint p [[thread_position_in_grid]]){ f[p].edge[0]=half(l); f[p].edge[1]=half(l); f[p].edge[2]=half(l); f[p].inside=half(l); }\n"},

// ---------- logging ----------
{"os_log", "COMPILED",
 "#include <metal_stdlib>\n#include <metal_logging>\nusing namespace metal;\n"
 "kernel void k(uint i [[thread_position_in_grid]]){ os_log_default.log(\"hi %d\", (int)i); }\n"},

{"printf_msl", "UNKNOWN(A18: os_log, not MSL printf)",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(uint i [[thread_position_in_grid]]){ printf(\"hi %d\", (int)i); }\n"},

// ---------- samplers (border-color presets; Metal exposes only 3) ----------
{"sampler_border_opaque_white", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "constexpr sampler s(address::clamp_to_border, border_color::opaque_white);\n"
 "fragment float4 f(texture2d<float> t [[texture(0)]]){ return t.sample(s, float2(0.5)); }\n"},

{"sampler_border_transparent_black", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "constexpr sampler s(address::clamp_to_border, border_color::transparent_black);\n"
 "fragment float4 f(texture2d<float> t [[texture(0)]]){ return t.sample(s, float2(0.5)); }\n"},

{"sampler_border_opaque_black", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "constexpr sampler s(address::clamp_to_border, border_color::opaque_black);\n"
 "fragment float4 f(texture2d<float> t [[texture(0)]]){ return t.sample(s, float2(0.5)); }\n"},

// ---------- Metal-4 tensor probes (may be M4/Metal-4 additions) ----------
{"metal_tensor_type", "UNKNOWN(Metal-4)",
 "#include <metal_stdlib>\n#include <metal_tensor>\nusing namespace metal;\n"
 "kernel void k(tensor<device float, dextents<int,2>> t [[buffer(0)]]){ (void)t; }\n"},

{"mpp_tensor_ops_matmul2d", "UNKNOWN(Metal-4 MPP)",
 "#include <metal_stdlib>\n#include <MetalPerformancePrimitives/MetalPerformancePrimitives.h>\nusing namespace metal;\nusing namespace mpp;\n"
 "kernel void k(device float* o [[buffer(0)]]){ (void)o; }\n"},

// ---------- texture atomics (Metal 3.1+) ----------
{"texture_atomic", "COMPILED",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(texture2d<uint, access::read_write> t [[texture(0)]], uint2 c [[thread_position_in_grid]]){ t.atomic_fetch_add(c, 1u); }\n"},
};

int main(void) {
  @autoreleasepool {
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    if (!d) { fprintf(stderr, "no Metal device\n"); return 1; }
    printf("device = %s\n", d.name.UTF8String);
    printf("%-34s  %-8s  %-30s  %s\n", "PROBE", "M4", "A18-expected", "diagnostic(first line)");
    printf("%-34s  %-8s  %-30s  %s\n", "-----", "--", "------------", "----------------------");
    unsigned n = sizeof(PROBES)/sizeof(PROBES[0]);
    for (unsigned i=0;i<n;i++) {
      NSError *e = nil;
      NSString *src = [NSString stringWithUTF8String:PROBES[i].src];
      id<MTLLibrary> lib = [d newLibraryWithSource:src options:nil error:&e];
      const char *res = lib ? "COMPILED" : "REJECTED";
      const char *diag = "";
      if (!lib && e) {
        NSString *msg = e.localizedDescription ?: @"";
        // take the first non-empty line that looks like a compiler message
        NSString *first = @"";
        for (NSString *ln in [msg componentsSeparatedByString:@"\n"]) {
          NSString *t = [ln stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
          if (t.length && ![t hasPrefix:@"program_source"]) { first = t; break; }
          if (t.length) first = t;
        }
        if (first.length > 100) first = [first substringToIndex:100];
        diag = first.UTF8String;
      }
      printf("%-34s  %-8s  %-30s  %s\n", PROBES[i].name, res, PROBES[i].a18, diag);
    }
    return 0;
  }
}
