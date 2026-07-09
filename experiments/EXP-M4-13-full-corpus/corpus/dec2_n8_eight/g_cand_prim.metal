#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal;
using namespace raytracing;
kernel void kmain(device float* o [[buffer(0)]], instance_acceleration_structure accel [[buffer(1)]], uint i [[thread_position_in_grid]]) {
    ray r(float3(0,0,0), float3(0,0,1));
    intersection_query<triangle_data, instancing> q;
    q.reset(r, accel);
    while(q.next()){} o[i]=float(q.get_candidate_primitive_id());
}
