// icbx.m — RT-6 adversarial ICB harness: execute-range subset + mixed draw/mesh ICB.
// Clean-room: OWN-SHADER + public Metal API. Our own MSL; no Apple binary inspected.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o icbx icbx.m
// Modes:
//   subset  --enc N --rstart S --rlen L : encode N draw cmds, execute range (S,L)
//   mixed                                : ICB commandTypes=Draw|DrawMeshThreadgroups,
//                                          cmd0=draw, cmd1=mesh (probe Metal acceptance)
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char*l,uint64_t v){printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)v);}

int main(int argc,char**argv){
 @autoreleasepool{
  const char*mode="subset"; long enc=3,rs=0,rl=0; int doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--mode")&&i+1<argc) mode=argv[++i];
    else if(!strcmp(argv[i],"--enc")&&i+1<argc) enc=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--rstart")&&i+1<argc) rs=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--rlen")&&i+1<argc) rl=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--dump")) doDump=1;
  }
  if(rl<=0) rl=enc-rs;
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  printf("CONFIG mode=%s enc=%ld rstart=%ld rlen=%ld\n",mode,enc,rs,rl);
  NSError*err=nil;
  id<MTLCommandQueue> q=[dev newCommandQueue];

  // normal graphics pipeline (draw)
  NSString*g=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]){VO o;o.pos=float4(p[vid],0,1);o.col=float4(0.25,0.5,0.75,1);return o;}\n"
    "fragment float4 f_main(VO in [[stage_in]]){return in.col;}\n";
  id<MTLLibrary> gl=[dev newLibraryWithSource:g options:nil error:&err];
  if(!gl){printf("LIB_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[gl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[gl newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  pd.supportIndirectCommandBuffers=YES;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PSO_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}

  long W=64,H=64,bpp=4; NSUInteger bpr=((W*bpp)+255)&~255UL;
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
  id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
  id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
  print_va("rtBuf",[rtb gpuAddress]);
  id<MTLBuffer> vb=[dev newBufferWithLength:24 options:MTLResourceStorageModeShared];
  float*vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
  print_va("vtxBuf",[vb gpuAddress]);

  if(!strcmp(mode,"mixed")){
    // mesh pipeline
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
    icbd.commandTypes=MTLIndirectCommandTypeDraw|MTLIndirectCommandTypeDrawMeshThreadgroups;
    icbd.inheritBuffers=NO; icbd.inheritPipelineState=NO;
    icbd.maxVertexBufferBindCount=1;
    if(@available(macOS 14.0,*)) icbd.maxMeshBufferBindCount=1;
    id<MTLIndirectCommandBuffer> icb=nil;
    @try{ icb=[dev newIndirectCommandBufferWithDescriptor:icbd maxCommandCount:2 options:0]; }
    @catch(NSException*e){printf("REJECT at=icb-create name=%s reason=%s\n",[[e name]UTF8String],[[e reason]UTF8String]);return 0;}
    if(!icb){printf("REJECT at=icb-create (nil)\n");return 0;}
    printf("OK mixed ICB created (commandTypes=Draw|Mesh)\n");
    @try{
      id<MTLIndirectRenderCommand> c0=[icb indirectRenderCommandAtIndex:0];
      [c0 setRenderPipelineState:pso];
      [c0 setVertexBuffer:vb offset:0 atIndex:0];
      [c0 drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1 baseInstance:0];
      printf("OK encoded cmd0=draw\n");
      id<MTLIndirectRenderCommand> c1=[icb indirectRenderCommandAtIndex:1];
      [c1 setRenderPipelineState:mpso];
      [c1 drawMeshThreadgroups:MTLSizeMake(1,1,1) threadsPerObjectThreadgroup:MTLSizeMake(1,1,1) threadsPerMeshThreadgroup:MTLSizeMake(3,1,1)];
      printf("OK encoded cmd1=mesh\n");
    }@catch(NSException*e){printf("REJECT at=encode name=%s reason=%s\n",[[e name]UTF8String],[[e reason]UTF8String]);return 0;}

    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=target; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1); rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
    @try{
      [enc useResource:vb usage:MTLResourceUsageRead];
      [enc executeCommandsInBuffer:icb withRange:NSMakeRange(0,2)];
    }@catch(NSException*e){printf("REJECT at=execute name=%s reason=%s\n",[[e name]UTF8String],[[e reason]UTF8String]);[enc endEncoding];return 0;}
    [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld\n",(long)[cb status]);
    if([cb error]) printf("CB_ERROR %s\n",[[[cb error]localizedDescription]UTF8String]);
    if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(500000);}
    return 0;
  }

  // ---- subset mode: encode `enc` draw commands, execute range (rs,rl) ----
  MTLIndirectCommandBufferDescriptor*icbd=[MTLIndirectCommandBufferDescriptor new];
  icbd.commandTypes=MTLIndirectCommandTypeDraw;
  icbd.inheritBuffers=NO; icbd.inheritPipelineState=NO; icbd.maxVertexBufferBindCount=1;
  id<MTLIndirectCommandBuffer> icb=[dev newIndirectCommandBufferWithDescriptor:icbd maxCommandCount:(NSUInteger)enc options:0];
  for(long c=0;c<enc;c++){
    id<MTLIndirectRenderCommand> rc=[icb indirectRenderCommandAtIndex:(NSUInteger)c];
    [rc setRenderPipelineState:pso];
    [rc setVertexBuffer:vb offset:0 atIndex:0];
    // distinct vertexCount per command so we can tell which ran: cmd c -> 3+c verts (still valid tri fan clamp)
    [rc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:(NSUInteger)(c+1) baseInstance:0];
  }
  printf("OK encoded %ld cmds; executing range (%ld,%ld)\n",enc,rs,rl);
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1); rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc2=[cb renderCommandEncoderWithDescriptor:rp];
  MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc2 setViewport:vpt];
  [enc2 useResource:vb usage:MTLResourceUsageRead];
  [enc2 executeCommandsInBuffer:icb withRange:NSMakeRange((NSUInteger)rs,(NSUInteger)rl)];
  [enc2 endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT done status=%ld\n",(long)[cb status]);
  if([cb error]) printf("CB_ERROR %s\n",[[[cb error]localizedDescription]UTF8String]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(500000);}
  return 0;
 }
}
