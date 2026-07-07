// a_icb.m -- RT-12 Part A: independent re-verify of ICB command-count @0x18000+0x04 and
// mesh-in-ICB lowering to the 0x70000600 mesh-grid-dispatch record.
// DIFFERENT counts than RT-6 (which did draw 1/2/3, mesh 1/2, mixed): here draw n in {4,5},
// pure-mesh n=3.
//   --mode draw --n N : ICB of N classic draw commands  -> +0x04 = N, N x opcode 0x61c4
//   --mode mesh --n N : ICB of N mesh commands          -> +0x04 = N, N x 0x70000600 in 0x18000
// CLEAN-ROOM: OWN-SHADER + public Metal API + DATA-TRACE (read-only iotrace). See ../../CLAUDE.md.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o a_icb a_icb.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
static void pv(const char*l,uint64_t v){printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)v);}
int main(int argc,char**argv){ @autoreleasepool{
  const char*mode="draw"; long N=4; int doDump=0;
  for(int i=1;i<argc;i++){ if(!strcmp(argv[i],"--mode")&&i+1<argc) mode=argv[++i];
    else if(!strcmp(argv[i],"--n")&&i+1<argc) N=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--dump")) doDump=1; }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); NSError*err=nil;
  printf("DEVICE %s MODE %s N=%ld\n",[[dev name]UTF8String],mode,N);
  id<MTLCommandQueue> q=[dev newCommandQueue];
  long W=64,H=64; NSUInteger bpr=((W*4)+255)&~255UL;
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
  id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
  id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
  id<MTLBuffer> vb=[dev newBufferWithLength:24 options:MTLResourceStorageModeShared];
  float*vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
  pv("vtxBuf",[vb gpuAddress]);
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1); rp.colorAttachments[0].storeAction=MTLStoreActionStore;

  if(!strcmp(mode,"mesh")){
    NSString*ms=@"#include <metal_stdlib>\n#include <metal_mesh>\nusing namespace metal;\n"
      "struct VOut{float4 position [[position]];float4 color;};\n"
      "struct POut{float3 pnormal [[flat]];};\n"
      "using tri_mesh=metal::mesh<VOut,POut,3,1,metal::topology::triangle>;\n"
      "struct Payload{float scale;};\n"
      "[[object,max_total_threadgroups_per_mesh_grid(1)]]\n"
      "void obj_main(object_data Payload &pl [[payload]],mesh_grid_properties mgp){pl.scale=1.0f;mgp.set_threadgroups_per_grid(uint3(1,1,1));}\n"
      "[[mesh,max_total_threads_per_threadgroup(3)]]\n"
      "void mesh_main(tri_mesh out,const object_data Payload &pl [[payload]],uint lane [[thread_index_in_threadgroup]]){\n"
      " if(lane==0)out.set_primitive_count(1);float2 P[3]={float2(-0.5,-0.5),float2(0.5,-0.5),float2(0.0,0.5)};\n"
      " VOut v;v.position=float4(P[lane]*pl.scale,0,1);v.color=float4(0,1,0,1);out.set_vertex(lane,v);out.set_index(lane,uchar(lane));\n"
      " if(lane==0){POut p;p.pnormal=float3(0,0,1);out.set_primitive(0,p);}}\n"
      "struct FragIn{VOut v;POut p;};\n"
      "fragment float4 frag_main(FragIn in [[stage_in]]){return in.v.color;}\n";
    id<MTLLibrary> ml=[dev newLibraryWithSource:ms options:nil error:&err];
    if(!ml){printf("MESH_LIB_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLMeshRenderPipelineDescriptor*mpd=[MTLMeshRenderPipelineDescriptor new];
    mpd.objectFunction=[ml newFunctionWithName:@"obj_main"];
    mpd.meshFunction=[ml newFunctionWithName:@"mesh_main"];
    mpd.fragmentFunction=[ml newFunctionWithName:@"frag_main"];
    mpd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    mpd.supportIndirectCommandBuffers=YES;
    id<MTLRenderPipelineState> mpso=[dev newRenderPipelineStateWithMeshDescriptor:mpd options:MTLPipelineOptionNone reflection:nil error:&err];
    if(!mpso){printf("MESH_PSO_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLIndirectCommandBufferDescriptor*icbd=[MTLIndirectCommandBufferDescriptor new];
    icbd.commandTypes=MTLIndirectCommandTypeDrawMeshThreadgroups;
    icbd.inheritBuffers=NO; icbd.inheritPipelineState=NO;
    if(@available(macOS 14.0,*)) icbd.maxMeshBufferBindCount=1;
    id<MTLIndirectCommandBuffer> icb=[dev newIndirectCommandBufferWithDescriptor:icbd maxCommandCount:(NSUInteger)N options:0];
    for(long c=0;c<N;c++){ id<MTLIndirectRenderCommand> rc=[icb indirectRenderCommandAtIndex:(NSUInteger)c];
      [rc setRenderPipelineState:mpso];
      [rc drawMeshThreadgroups:MTLSizeMake(1,1,1) threadsPerObjectThreadgroup:MTLSizeMake(1,1,1) threadsPerMeshThreadgroup:MTLSizeMake(3,1,1)]; }
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
    [enc executeCommandsInBuffer:icb withRange:NSMakeRange(0,(NSUInteger)N)];
    [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("SUBMIT status=%ld\n",(long)[cb status]);
    if([cb error]) printf("CB_ERROR %s\n",[[[cb error]localizedDescription]UTF8String]);
    if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(500000);}
    return 0;
  }
  // draw mode
  NSString*g=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]){VO o;o.pos=float4(p[vid],0,1);o.col=float4(0.3,0.6,0.9,1);return o;}\n"
    "fragment float4 f_main(VO in [[stage_in]]){return in.col;}\n";
  id<MTLLibrary> gl=[dev newLibraryWithSource:g options:nil error:&err];
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[gl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[gl newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  pd.supportIndirectCommandBuffers=YES;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  MTLIndirectCommandBufferDescriptor*icbd=[MTLIndirectCommandBufferDescriptor new];
  icbd.commandTypes=MTLIndirectCommandTypeDraw;
  icbd.inheritBuffers=NO; icbd.inheritPipelineState=NO; icbd.maxVertexBufferBindCount=1;
  id<MTLIndirectCommandBuffer> icb=[dev newIndirectCommandBufferWithDescriptor:icbd maxCommandCount:(NSUInteger)N options:0];
  for(long c=0;c<N;c++){ id<MTLIndirectRenderCommand> rc=[icb indirectRenderCommandAtIndex:(NSUInteger)c];
    [rc setRenderPipelineState:pso]; [rc setVertexBuffer:vb offset:0 atIndex:0];
    [rc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1 baseInstance:0]; }
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
  [enc useResource:vb usage:MTLResourceUsageRead];
  [enc executeCommandsInBuffer:icb withRange:NSMakeRange(0,(NSUInteger)N)];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld\n",(long)[cb status]);
  if([cb error]) printf("CB_ERROR %s\n",[[[cb error]localizedDescription]UTF8String]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(500000);}
  return 0;
}}
