// mesh.m — corrected M5 object+mesh+fragment draw for cmdstream capture.
// Fixes the EXP-M5-10 abort: that harness called the *tile* pipeline method
// newRenderPipelineStateWithDescriptor:options:reflection: with a MESH descriptor.
// The correct call is newRenderPipelineStateWithMeshDescriptor:options:reflection:
// (as the known-good A18 EXP-0030 harness). Modeled directly on that MSL.
// Clean-room: our own MSL + public Metal API; dumps our own BOs via SIGUSR1.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

int main(int argc,char**argv){@autoreleasepool{
  int doDump=0; long W=64,H=64;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--w")&&i+1<argc)W=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--h")&&i+1<argc)H=strtol(argv[++i],0,0);
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s MESH w=%ld h=%ld\n",[[dev name]UTF8String],W,H);
  NSString*src=
    @"#include <metal_stdlib>\n#include <metal_mesh>\nusing namespace metal;\n"
     "struct VOut { float4 position [[position]]; float4 color; };\n"
     "struct POut { float3 pnormal [[flat]]; };\n"
     "using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;\n"
     "struct Payload { float scale; float p0; float p1; float p2; };\n"
     "[[object, max_total_threadgroups_per_mesh_grid(1)]]\n"
     "void obj_main(object_data Payload &pl [[payload]], mesh_grid_properties mgp, uint tid [[thread_position_in_grid]]) {\n"
     "  pl.scale = 1.0f; mgp.set_threadgroups_per_grid(uint3(1,1,1)); }\n"
     "[[mesh, max_total_threads_per_threadgroup(3)]]\n"
     "void mesh_main(tri_mesh out, const object_data Payload &pl [[payload]], uint lane [[thread_index_in_threadgroup]]) {\n"
     "  if (lane==0) out.set_primitive_count(1);\n"
     "  float2 P[3] = { float2(-0.5,-0.5), float2(0.5,-0.5), float2(0.0,0.5) };\n"
     "  VOut v; v.position = float4(P[lane]*pl.scale,0,1); v.color = float4(0,1,0,1);\n"
     "  out.set_vertex(lane, v); out.set_index(lane, uchar(lane));\n"
     "  if (lane==0){ POut p; p.pnormal=float3(0,0,1); out.set_primitive(0,p); } }\n"
     "struct FragIn { VOut v; POut p; };\n"
     "fragment float4 frag_main(FragIn in [[stage_in]]) { return in.v.color; }\n";
  NSError*err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLMeshRenderPipelineDescriptor*md=[MTLMeshRenderPipelineDescriptor new];
  md.objectFunction=[lib newFunctionWithName:@"obj_main"];
  md.meshFunction=[lib newFunctionWithName:@"mesh_main"];
  md.fragmentFunction=[lib newFunctionWithName:@"frag_main"];
  md.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  id<MTLRenderPipelineState> pso=
    [dev newRenderPipelineStateWithMeshDescriptor:md options:MTLPipelineOptionNone reflection:nil error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;td.storageMode=MTLStorageModeShared;
  id<MTLTexture> target=[dev newTextureWithDescriptor:td];
  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  [enc setRenderPipelineState:pso];
  [enc drawMeshThreadgroups:MTLSizeMake(1,1,1)
        threadsPerObjectThreadgroup:MTLSizeMake(1,1,1)
          threadsPerMeshThreadgroup:MTLSizeMake(3,1,1)];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  unsigned char px[4];
  [target getBytes:px bytesPerRow:4 fromRegion:MTLRegionMake2D(W/2,H/2,1,1) mipmapLevel:0];
  printf("PIXEL center bgra=%02x%02x%02x%02x (expect green ~00ff00ff)\n",px[0],px[1],px[2],px[3]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
