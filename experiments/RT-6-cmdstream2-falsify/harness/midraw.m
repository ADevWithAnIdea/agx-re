// midraw.m — RT-6 adversarial: multiple indirect draws in ONE render pass, distinct argBufs.
// Clean-room: OWN-SHADER + public Metal API. Verify each indirect draw gets its own 0x6404
// record with its own args pointer (low32 correlated to distinct argBuf VAs).
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o midraw midraw.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <signal.h>
#include <unistd.h>
static void pv(const char*l,uint64_t v){printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)v);}
int main(int argc,char**argv){
 @autoreleasepool{
  int doDump=0; for(int i=1;i<argc;i++) if(!strcmp(argv[i],"--dump")) doDump=1;
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); NSError*err=nil;
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  NSString*g=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]){VO o;o.pos=float4(p[vid],0,1);o.col=float4(0.25,0.5,0.75,1);return o;}\n"
    "fragment float4 f_main(VO in [[stage_in]]){return in.col;}\n";
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
  // two distinct arg buffers
  id<MTLBuffer> a0=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
  id<MTLBuffer> a1=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
  uint32_t*A0=(uint32_t*)[a0 contents]; uint32_t*A1=(uint32_t*)[a1 contents];
  A0[0]=3;A0[1]=1;A0[2]=0;A0[3]=0;  A1[0]=3;A1[1]=2;A1[2]=0;A1[3]=0;
  pv("argBuf0",[a0 gpuAddress]); pv("argBuf1",[a1 gpuAddress]);
  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1); rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
  [enc setRenderPipelineState:pso]; [enc setVertexBuffer:vb offset:0 atIndex:0];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle indirectBuffer:a0 indirectBufferOffset:0];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle indirectBuffer:a1 indirectBufferOffset:0];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT done status=%ld\n",(long)[cb status]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
 }
}
