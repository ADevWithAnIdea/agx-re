// EXP-M5-19 canonical RT kernel for splice-and-observe with a real AS (M5).
// CLEAN-ROOM: OUR OWN MSL. Dynamic origin+dir (device-loaded) so the ray-data reads
// and the AS-load are present in _agc.main and controllable at runtime; const tmin/tmax.
#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;

kernel void rtk(primitive_acceleration_structure accel [[buffer(0)]],
                device float *out [[buffer(1)]],
                device const packed_float3 *org [[buffer(2)]],
                device const packed_float3 *dir [[buffer(3)]],
                uint i [[thread_position_in_grid]]) {
    ray r;
    r.origin = float3(org[i]);
    r.direction = float3(dir[i]);
    r.min_distance = 0.0f;
    r.max_distance = INFINITY;
    intersector<triangle_data> isect;
    isect.assume_geometry_type(geometry_type::triangle);
    auto res = isect.intersect(r, accel);
    out[i] = (res.type == intersection_type::triangle) ? res.distance : -1.0f;
}
