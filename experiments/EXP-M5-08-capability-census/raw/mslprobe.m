// Clean-room M5 MSL-acceptance probe. Compile-only (newLibraryWithSource:), NO GPU dispatch.
// Determines which MSL constructs the M5 (Apple10/G17g) stack ACCEPTS vs REJECTS at compile
// time. This drives native-vs-emulate capability classifications that the device-flag probe
// (EXP-M5-04) cannot see. All MSL below is OURS.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static id<MTLDevice> gDev;

static void T(const char *name, NSString *src) {
    NSError *e = nil;
    MTLCompileOptions *o = [MTLCompileOptions new];
    id<MTLLibrary> lib = [gDev newLibraryWithSource:src options:o error:&e];
    if (lib) {
        printf("ACCEPT  %s\n", name);
    } else {
        NSString *m = e.localizedDescription ?: @"(nil)";
        // collapse to one line, trim
        m = [m stringByReplacingOccurrencesOfString:@"\n" withString:@" | "];
        if (m.length > 180) m = [m substringToIndex:180];
        printf("REJECT  %s :: %s\n", name, m.UTF8String);
    }
}

int main(void) {
  @autoreleasepool {
    gDev = MTLCreateSystemDefaultDevice();
    printf("device = %s / arch check\n", gDev.name.UTF8String);
    NSString *H = @"#include <metal_stdlib>\n#include <metal_simdgroup_matrix>\nusing namespace metal;\n";

    // ---- simdgroup_matrix (cooperative matrix) dtypes ----
    T("coopmat_fp16", [H stringByAppendingString:@"kernel void k(device half*o,uint i[[thread_position_in_grid]]){simdgroup_half8x8 a=make_filled_simdgroup_matrix<half,8,8>(1),b=a,c=make_filled_simdgroup_matrix<half,8,8>(0);simdgroup_multiply_accumulate(c,a,b,c);simdgroup_store(c,o,8);}"]);
    T("coopmat_fp32", [H stringByAppendingString:@"kernel void k(device float*o,uint i[[thread_position_in_grid]]){simdgroup_float8x8 a=make_filled_simdgroup_matrix<float,8,8>(1),b=a,c=make_filled_simdgroup_matrix<float,8,8>(0);simdgroup_multiply_accumulate(c,a,b,c);simdgroup_store(c,o,8);}"]);
    T("coopmat_bf16", [H stringByAppendingString:@"kernel void k(device bfloat*o,uint i[[thread_position_in_grid]]){simdgroup_matrix<bfloat,8,8> a=make_filled_simdgroup_matrix<bfloat,8,8>(1),b=a;simdgroup_matrix<float,8,8> c=make_filled_simdgroup_matrix<float,8,8>(0);simdgroup_multiply_accumulate(c,a,b,c);simdgroup_store(c,o,8);}"]);
    T("coopmat_int8_char", [H stringByAppendingString:@"kernel void k(device int*o,uint i[[thread_position_in_grid]]){simdgroup_matrix<char,8,8> a=make_filled_simdgroup_matrix<char,8,8>(1),b=a;simdgroup_matrix<int,8,8> c=make_filled_simdgroup_matrix<int,8,8>(0);simdgroup_multiply_accumulate(c,a,b,c);simdgroup_store(c,o,8);}"]);
    T("coopmat_int32", [H stringByAppendingString:@"kernel void k(device int*o,uint i[[thread_position_in_grid]]){simdgroup_matrix<int,8,8> a=make_filled_simdgroup_matrix<int,8,8>(1),b=a,c=make_filled_simdgroup_matrix<int,8,8>(0);simdgroup_multiply_accumulate(c,a,b,c);simdgroup_store(c,o,8);}"]);

    // ---- atomics ----
    NSString *A = @"#include <metal_stdlib>\nusing namespace metal;\n";
    T("atomic_int_add",   [A stringByAppendingString:@"kernel void k(device atomic_int*p){atomic_fetch_add_explicit(p,1,memory_order_relaxed);}"]);
    T("atomic_uint_min",  [A stringByAppendingString:@"kernel void k(device atomic_uint*p){atomic_fetch_min_explicit(p,1u,memory_order_relaxed);}"]);
    T("atomic_float_add", [A stringByAppendingString:@"kernel void k(device atomic<float>*p){atomic_fetch_add_explicit(p,1.0f,memory_order_relaxed);}"]);
    T("atomic_float_min", [A stringByAppendingString:@"kernel void k(device atomic<float>*p){atomic_fetch_min_explicit(p,1.0f,memory_order_relaxed);}"]);
    T("atomic_float_max", [A stringByAppendingString:@"kernel void k(device atomic<float>*p){atomic_fetch_max_explicit(p,1.0f,memory_order_relaxed);}"]);
    T("atomic_u64_add",   [A stringByAppendingString:@"kernel void k(device atomic<ulong>*p){atomic_fetch_add_explicit(p,1ul,memory_order_relaxed);}"]);
    T("atomic_u64_min",   [A stringByAppendingString:@"kernel void k(device atomic<ulong>*p){atomic_fetch_min_explicit(p,1ul,memory_order_relaxed);}"]);
    T("atomic_i64_max",   [A stringByAppendingString:@"kernel void k(device atomic<long>*p){atomic_fetch_max_explicit(p,1l,memory_order_relaxed);}"]);

    // ---- bfloat ALU ----
    T("bfloat_alu", [A stringByAppendingString:@"kernel void k(device bfloat*o,device bfloat*a,device bfloat*b,uint i[[thread_position_in_grid]]){o[i]=a[i]*b[i]+a[i];}"]);

    // ---- RT / intersection ----
    NSString *R = @"#include <metal_stdlib>\n#include <metal_raytracing>\nusing namespace metal;\nusing namespace raytracing;\n";
    T("rt_intersector_inline", [R stringByAppendingString:@"kernel void k(device float*o,instance_acceleration_structure a,uint i[[thread_position_in_grid]]){ray r; r.origin=float3(0); r.direction=float3(0,0,1); r.min_distance=0; r.max_distance=1e9; intersector<instancing,triangle_data> it; auto res=it.intersect(r,a); o[i]=res.distance;}"]);
    T("rt_query_inline", [R stringByAppendingString:@"kernel void k(device float*o,primitive_acceleration_structure a,uint i[[thread_position_in_grid]]){ray r; r.origin=float3(0); r.direction=float3(0,0,1); r.min_distance=0; r.max_distance=1e9; intersection_query<triangle_data> q; q.reset(r,a); q.next(); o[i]=q.get_committed_distance();}"]);
    T("rt_motion", [R stringByAppendingString:@"kernel void k(device float*o,instance_motion_acceleration_structure a,uint i[[thread_position_in_grid]]){ray r; r.origin=float3(0); r.direction=float3(0,0,1); r.min_distance=0; r.max_distance=1e9; intersector<instancing,triangle_data,motion> it; auto res=it.intersect(r,a,0,0.5f); o[i]=res.distance;}"]);

    // ---- Metal-4 tensor in MSL (device / threadgroup) ----
    T("msl_tensor_include", @"#include <metal_stdlib>\n#include <metal_tensor>\nusing namespace metal;\nkernel void k(){}");

    // ---- subgroup / quad tail ----
    T("simd_shuffle_and_fill", [A stringByAppendingString:@"kernel void k(device int*o,uint i[[thread_position_in_grid]]){o[i]=simd_shuffle_and_fill_down(int(i),0,1);}"]);
    T("simd_prefix_inclusive", [A stringByAppendingString:@"kernel void k(device int*o,uint i[[thread_position_in_grid]]){o[i]=simd_prefix_inclusive_sum(int(i));}"]);
    T("quad_shuffle", [A stringByAppendingString:@"kernel void k(device int*o,uint i[[thread_position_in_grid]]){o[i]=quad_shuffle(int(i),0);}"]);

    printf("DONE\n");
  }
  return 0;
}
