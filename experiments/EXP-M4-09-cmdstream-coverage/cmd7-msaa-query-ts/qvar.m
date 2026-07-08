// qvar.m — parametric OWN Metal DRAW for OCCLUSION / VISIBILITY QUERY RE.
//
// Part of EXP-0027. setVisibilityResultMode:offset: with a visibilityResultBuffer on
// the render pass. Change-one-parameter: run with mode Disabled / Boolean / Counting
// and various offsets, capture the registered GPU BOs under iotrace, byte-diff to find
//  (1) the visibility-result-buffer pointer in the control stream,
//  (2) the per-draw query enable/mode field in the VDM draw command,
//  (3) the per-draw counter offset.
// Readback of the visibility buffer confirms the HW actually accumulates samples.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Our own MSL. No Apple binary read.
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o qvar qvar.m
//
// Usage: qvar --mode MODE [--off N] [--off2 N] [--w W --h H] [--dump]
//   MODE: none | bool | count | two   (two = two draws, modes/offsets via --mode2/--off2)
//   --mode2: bool|count for the 2nd draw (mode=two)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *l, uint64_t va){ printf("VA %-12s = 0x%016llx\n",l,(unsigned long long)va); }

static NSString *gsrc(void){
  return @"#include <metal_stdlib>\nusing namespace metal;\n"
          "struct VO { float4 pos [[position]]; float4 col; };\n"
          "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]) {\n"
          "  VO o; o.pos=float4(p[vid],0,1); o.col=float4(0.25,0.5,0.75,1); return o; }\n"
          "fragment float4 f_main(VO in [[stage_in]]) { return in.col; }\n";
}
static MTLVisibilityResultMode parse_mode(const char*s){
  if(!strcmp(s,"bool")) return MTLVisibilityResultModeBoolean;
  if(!strcmp(s,"count"))return MTLVisibilityResultModeCounting;
  return MTLVisibilityResultModeDisabled;
}

int main(int argc,char**argv){
 @autoreleasepool{
  const char *modeS="none",*mode2S="count"; long off=0,off2=8,W=64,H=64; int doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--mode")&&i+1<argc) modeS=argv[++i];
    else if(!strcmp(argv[i],"--mode2")&&i+1<argc) mode2S=argv[++i];
    else if(!strcmp(argv[i],"--off")&&i+1<argc) off=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--off2")&&i+1<argc) off2=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--w")&&i+1<argc) W=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--h")&&i+1<argc) H=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--dump")) doDump=1;
  }
  int isTwo=!strcmp(modeS,"two");
  MTLVisibilityResultMode m1 = isTwo?MTLVisibilityResultModeCounting:parse_mode(modeS);
  MTLVisibilityResultMode m2 = parse_mode(mode2S);
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  printf("CONFIG mode=%s mode2=%s off=%ld off2=%ld w=%ld h=%ld two=%d\n",modeS,mode2S,off,off2,W,H,isTwo);
  NSError*err=nil;
  id<MTLLibrary> gl=[dev newLibraryWithSource:gsrc() options:nil error:&err];
  if(!gl){printf("LIB_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[gl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[gl newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PSO_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}

  long bpp=4; NSUInteger bpr=((W*bpp)+255)&~255UL;
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
  id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
  id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
  print_va("rtBuf",[rtb gpuAddress]);

  id<MTLBuffer> vb=[dev newBufferWithLength:24 options:MTLResourceStorageModeShared];
  float*vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
  print_va("vtxBuf",[vb gpuAddress]);

  // visibility result buffer: distinctive poison so a write is obvious on readback.
  // Size to accommodate the largest offset used (offset must be 8-aligned per Metal).
  long maxoff = off>off2?off:off2;
  long vlen = maxoff+256; if(vlen<256) vlen=256; vlen=(vlen+255)&~255L;
  id<MTLBuffer> visb=[dev newBufferWithLength:(NSUInteger)vlen options:MTLResourceStorageModeShared];
  uint64_t*vq=(uint64_t*)[visb contents]; long nslots=vlen/8;
  for(long i=0;i<nslots;i++) vq[i]=0xdeadbeef00000000ULL|(uint64_t)(i&0xffffffff);
  printf("VISBUF len=%ld nslots=%ld\n",vlen,nslots);
  print_va("visBuf",[visb gpuAddress]);

  int useVis = strcmp(modeS,"none")!=0;
  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target;
  rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
  rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  if(useVis) rp.visibilityResultBuffer=visb;
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
  [enc setRenderPipelineState:pso];
  [enc setVertexBuffer:vb offset:0 atIndex:0];
  if(useVis) [enc setVisibilityResultMode:m1 offset:(NSUInteger)off];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1];
  if(isTwo){
    [enc setVisibilityResultMode:m2 offset:(NSUInteger)off2];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1];
  }
  if(useVis) [enc setVisibilityResultMode:MTLVisibilityResultModeDisabled offset:0];
  [enc endEncoding];
  [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT done status=%ld\n",(long)[cb status]);
  // readback the visibility buffer AT the actual offsets used (offset/8 slot), plus slot 0.
  long s1=off/8, s2=off2/8;
  printf("VIS[slot=%ld off=%ld] = 0x%016llx (%llu)  <- draw1\n",s1,off,(unsigned long long)vq[s1],(unsigned long long)vq[s1]);
  if(isTwo) printf("VIS[slot=%ld off=%ld] = 0x%016llx (%llu)  <- draw2\n",s2,off2,(unsigned long long)vq[s2],(unsigned long long)vq[s2]);
  printf("VIS[slot=0 off=0] = 0x%016llx (%llu)\n",(unsigned long long)vq[0],(unsigned long long)vq[0]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
 }
}
