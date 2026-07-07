// a_occ.m -- RT-12 Part A: independent re-verify of occlusion-query cmdstream fields.
//   result-buffer base ptr @0x10000100000+0x00 ; mode = bit14 of 0x58000+0x8c
//   (Boolean=1 / Counting=0) ; per-draw offset = 0x58000+0xa0 = byteOffset<<14.
// DIFFERENT byte offsets than RT-6 (0/8/16/4096): here 24 and 40. Reads back the counter too.
//   --mode none|bool|count   --off BYTES
// CLEAN-ROOM: OWN-SHADER + public Metal API + DATA-TRACE (read-only iotrace). See ../../CLAUDE.md.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o a_occ a_occ.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
static void pv(const char*l,uint64_t v){printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)v);}
int main(int argc,char**argv){ @autoreleasepool{
  const char*mode="count"; long off=24; int doDump=0;
  for(int i=1;i<argc;i++){ if(!strcmp(argv[i],"--mode")&&i+1<argc) mode=argv[++i];
    else if(!strcmp(argv[i],"--off")&&i+1<argc) off=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--dump")) doDump=1; }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); NSError*err=nil;
  printf("DEVICE %s MODE %s OFF %ld\n",[[dev name]UTF8String],mode,off);
  NSString*g=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];};\n"
    "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]){VO o;o.pos=float4(p[vid],0,1);return o;}\n"
    "fragment float4 f_main(VO in [[stage_in]]){return float4(1,0.5,0,1);}\n";
  id<MTLLibrary> gl=[dev newLibraryWithSource:g options:nil error:&err];
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[gl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[gl newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  long W=64,H=64; NSUInteger bpr=((W*4)+255)&~255UL;
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget; td.storageMode=MTLStorageModeShared;
  id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
  id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
  id<MTLBuffer> vb=[dev newBufferWithLength:24 options:MTLResourceStorageModeShared];
  float*vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
  pv("vtxBuf",[vb gpuAddress]);
  id<MTLBuffer> vis=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
  memset([vis contents],0,256); pv("visBuf",[vis gpuAddress]);
  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1); rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  rp.visibilityResultBuffer=vis;
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
  [enc setRenderPipelineState:pso]; [enc setVertexBuffer:vb offset:0 atIndex:0];
  MTLVisibilityResultMode vm=MTLVisibilityResultModeDisabled;
  if(!strcmp(mode,"bool")) vm=MTLVisibilityResultModeBoolean;
  else if(!strcmp(mode,"count")) vm=MTLVisibilityResultModeCounting;
  if(vm!=MTLVisibilityResultModeDisabled) [enc setVisibilityResultMode:vm offset:(NSUInteger)off];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
  if(vm!=MTLVisibilityResultModeDisabled) [enc setVisibilityResultMode:MTLVisibilityResultModeDisabled offset:(NSUInteger)off];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld\n",(long)[cb status]);
  uint64_t*V=(uint64_t*)[vis contents];
  printf("VIS[at off/8=%ld]=%llu  VIS[0]=%llu VIS[1]=%llu VIS[2]=%llu\n",off/8,
    (unsigned long long)V[off/8],(unsigned long long)V[0],(unsigned long long)V[1],(unsigned long long)V[2]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(500000);}
  return 0;
}}
