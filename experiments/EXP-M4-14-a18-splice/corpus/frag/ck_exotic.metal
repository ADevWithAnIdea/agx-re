#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace metal::raytracing;

// Integer subgroup product + quad ops + ray-query getters -- the exact contexts
// R9 named as producing the byte0-low-nibble-4 residue op.
kernel void k(device int *out [[buffer(0)]],
              device const int *in [[buffer(1)]],
              uint tid [[thread_position_in_grid]],
              uint lane [[thread_index_in_simdgroup]],
              uint qlane [[thread_index_in_quadgroup]]) {
    int v = in[tid];
    int p = simd_product(v);
    int px = simd_prefix_exclusive_product(v);
    int q = quad_shuffle(v, (qlane + 1) & 3);
    int b = quad_broadcast(v, 0);
    int s = simd_shuffle_xor(v, 1);
    out[tid] = p + px + q + b + s + int(lane);
}

// Ray-query getters (intersection_query) -- second named context.
kernel void kq(device float *out [[buffer(0)]],
               const device float3 *org [[buffer(1)]],
               instance_acceleration_structure accel [[buffer(2)]],
               uint tid [[thread_position_in_grid]]) {
    ray r;
    r.origin = org[tid];
    r.direction = float3(0, 0, 1);
    r.min_distance = 0.0f;
    r.max_distance = 100.0f;
    intersection_query<instancing> iq;
    iq.reset(r, accel);
    iq.next();
    float d = iq.get_committed_distance();
    uint pid = iq.get_committed_primitive_id();
    uint gid = iq.get_committed_geometry_id();
    out[tid] = d + float(pid) + float(gid);
}
