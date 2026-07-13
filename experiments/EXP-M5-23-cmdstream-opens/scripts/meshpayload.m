// meshpayload.m — payload-heavy / multi-object mesh probe. Generates a mesh pipeline
// with a parameterised payload size, object-grid, and mesh vertex/primitive counts to
// force the mesh dispatch-descriptor / UVB machinery (the A18 0x100000f8000 BO) to
// materialise, and to see how object-grid dims are encoded in the mesh-grid-dispatch
// record. --heavy switches minimal->heavy. Clean-room: OWN MSL/API + DATA-TRACE.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
int main(int argc,char**argv){@autoreleasepool{
  int doDump=0,heavy=0; long W=128,H=128;
  int payloadFloats=1, objGX=1,objGY=1, maxV=3,maxP=1, meshTPT=3;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--heavy")){heavy=1;payloadFloats=48;objGX=4;objGY=2;maxV=64;maxP=32;meshTPT=32;}
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s MESHPAYLOAD heavy=%d payloadF=%d objGrid=%dx%d maxV=%d maxP=%d meshTPT=%d\n",
    [[dev name]UTF8String],heavy,payloadFloats,objGX,objGY,maxV,maxP,meshTPT);
  NSMutableString*s=[NSMutableString stringWithString:@"#include <metal_stdlib>\n#include <metal_mesh>\nusing namespace metal;\n"];
  [s appendString:@"struct VOut{float4 position [[position]];float4 color;};\n"];
  [s appendString:@"struct POut{float3 pnormal [[flat]];};\n"];
  [s appendFormat:@"using tri_mesh=metal::mesh<VOut,POut,%d,%d,metal::topology::triangle>;\n",maxV,maxP];
  [s appendFormat:@"struct Payload{float v[%d];};\n",payloadFloats];
  [s appendFormat:@"[[object,max_total_threadgroups_per_mesh_grid(%d)]]\n",(maxP>0?1:1)];
  [s appendString:@"void obj_main(object_data Payload &pl [[payload]],mesh_grid_properties mgp,uint2 og[[threadgroup_position_in_grid]]){\n"];
  [s appendFormat:@"  for(int i=0;i<%d;i++) pl.v[i]=float(i)+float(og.x)*0.5f;\n",payloadFloats];
  [s appendString:@"  mgp.set_threadgroups_per_grid(uint3(1,1,1)); }\n"];
  [s appendFormat:@"[[mesh,max_total_threads_per_threadgroup(%d)]]\n",meshTPT];
  [s appendString:@"void mesh_main(tri_mesh out,const object_data Payload &pl [[payload]],uint lane[[thread_index_in_threadgroup]]){\n"];
  [s appendFormat:@"  uint nv=%d,np=%d;\n",maxV,maxP];
  [s appendString:@"  if(lane==0) out.set_primitive_count(np);\n"];
  [s appendString:@"  if(lane<nv){ VOut v; float a=float(lane)/float(nv)*6.28318f;\n"];
  [s appendString:@"    float s=0.5f+pl.v[0]*0.0f; v.position=float4(cos(a)*s,sin(a)*s,0,1); v.color=float4(0,1,0,1); out.set_vertex(lane,v); }\n"];
  [s appendString:@"  if(lane<np){ out.set_index(lane*3+0,uchar((lane*3+0)%nv)); out.set_index(lane*3+1,uchar((lane*3+1)%nv)); out.set_index(lane*3+2,uchar((lane*3+2)%nv));\n"];
  [s appendString:@"    POut p; p.pnormal=float3(0,0,1); out.set_primitive(lane,p);} }\n"];
  [s appendString:@"struct FragIn{VOut v;POut p;};\n"];
  [s appendString:@"fragment float4 frag_main(FragIn in [[stage_in]]){return in.v.color;}\n"];
  NSError*err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:s options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLMeshRenderPipelineDescriptor*md=[MTLMeshRenderPipelineDescriptor new];
  md.objectFunction=[lib newFunctionWithName:@"obj_main"];
  md.meshFunction=[lib newFunctionWithName:@"mesh_main"];
  md.fragmentFunction=[lib newFunctionWithName:@"frag_main"];
  md.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithMeshDescriptor:md options:MTLPipelineOptionNone reflection:nil error:&err];
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
  [enc drawMeshThreadgroups:MTLSizeMake(objGX,objGY,1)
        threadsPerObjectThreadgroup:MTLSizeMake(1,1,1)
          threadsPerMeshThreadgroup:MTLSizeMake(meshTPT,1,1)];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  if([cb error])printf("CB_ERROR %s\n",[[[cb error]localizedDescription]UTF8String]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(500000);}
  return 0;
}}
