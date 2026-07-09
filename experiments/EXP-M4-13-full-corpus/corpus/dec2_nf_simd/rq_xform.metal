#include <metal_stdlib>
#include <metal_raytracing>
using namespace metal; using namespace raytracing;
kernel void k(device float* o[[buffer(0)]], instance_acceleration_structure a[[buffer(1)]], uint i[[thread_position_in_grid]]){
  ray r(float3(0,0,0),float3(0,0,1));
  intersection_query<triangle_data, instancing> q; q.reset(r,a);
  while(q.next()) if(q.get_candidate_intersection_type()==intersection_type::triangle) q.commit_triangle_intersection();
  float4x3 m=q.get_committed_object_to_world_transform();
  o[i]=m[0].x+m[1].y+m[2].z+m[3].x;
}
