#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
static id<MTLDevice> gDev;
static void T(const char *name, NSString *src){
  NSError *e=nil; id<MTLLibrary> lib=[gDev newLibraryWithSource:src options:[MTLCompileOptions new] error:&e];
  if(lib){printf("ACCEPT  %s\n",name);} else {NSString*m=e.localizedDescription?:@"(nil)";
    m=[m stringByReplacingOccurrencesOfString:@"\n" withString:@" | "]; if(m.length>200)m=[m substringToIndex:200];
    printf("REJECT  %s :: %s\n",name,m.UTF8String);} }
int main(void){@autoreleasepool{ gDev=MTLCreateSystemDefaultDevice();
  NSString*H=@"#include <metal_stdlib>\n#include <metal_simdgroup_matrix>\nusing namespace metal;\n";
  // bf16 coopmat: accumulate in float, store to float* (correct types)
  T("coopmat_bf16_fixed",[H stringByAppendingString:@"kernel void k(device float*o,uint i[[thread_position_in_grid]]){simdgroup_matrix<bfloat,8,8> a=make_filled_simdgroup_matrix<bfloat,8,8>(1),b=a;simdgroup_matrix<float,8,8> c=make_filled_simdgroup_matrix<float,8,8>(0);simdgroup_multiply_accumulate(c,a,b,c);simdgroup_store(c,o,8);}"]);
  // bf16 coopmat pure bf16 accumulate + store to bfloat*
  T("coopmat_bf16_pure",[H stringByAppendingString:@"kernel void k(device bfloat*o,uint i[[thread_position_in_grid]]){simdgroup_matrix<bfloat,8,8> a=make_filled_simdgroup_matrix<bfloat,8,8>(1),b=a,c=make_filled_simdgroup_matrix<bfloat,8,8>(0);simdgroup_multiply_accumulate(c,a,b,c);simdgroup_store(c,o,8);}"]);
  // RT motion — several spellings
  NSString*R=@"#include <metal_stdlib>\n#include <metal_raytracing>\nusing namespace metal;\nusing namespace raytracing;\n";
  T("rt_prim_motion_tag",[R stringByAppendingString:@"kernel void k(device float*o,primitive_acceleration_structure a,uint i[[thread_position_in_grid]]){ray r;r.origin=float3(0);r.direction=float3(0,0,1);r.min_distance=0;r.max_distance=1e9;intersector<triangle_data,primitive_motion> it;auto res=it.intersect(r,a,0.5f);o[i]=res.distance;}"]);
  T("rt_inst_motion_tag",[R stringByAppendingString:@"kernel void k(device float*o,instance_acceleration_structure a,uint i[[thread_position_in_grid]]){ray r;r.origin=float3(0);r.direction=float3(0,0,1);r.min_distance=0;r.max_distance=1e9;intersector<instancing,triangle_data,instance_motion> it;auto res=it.intersect(r,a,0.5f);o[i]=res.distance;}"]);
  T("rt_query_world_space",[R stringByAppendingString:@"kernel void k(device float*o,instance_acceleration_structure a,uint i[[thread_position_in_grid]]){ray r;r.origin=float3(0);r.direction=float3(0,0,1);r.min_distance=0;r.max_distance=1e9;intersection_query<instancing,triangle_data,world_space_data> q;q.reset(r,a);q.next();o[i]=q.get_committed_distance();}"]);
  printf("DONE\n"); } return 0; }
