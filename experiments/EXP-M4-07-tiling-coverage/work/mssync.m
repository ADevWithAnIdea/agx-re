#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <signal.h>
#include <unistd.h>
static uint32_t hh(uint32_t x,uint32_t y,uint32_t s,uint32_t k){uint32_t h=2166136261u;h=(h^x)*16777619u;h=(h^y)*16777619u;h=(h^s)*16777619u;h=(h^k)*16777619u;return h;}
int main(int argc,char**argv){@autoreleasepool{
 const char*fmt=argc>1?argv[1]:"r16uint"; long W=argc>2?atol(argv[2]):192,H=W,N=argc>3?atol(argv[3]):4;
 int doDump=argc>4;
 id<MTLDevice>dev=MTLCreateSystemDefaultDevice(); id<MTLCommandQueue>q=[dev newCommandQueue];
 MTLPixelFormat pf=MTLPixelFormatR16Uint; if(!strcmp(fmt,"r8uint"))pf=MTLPixelFormatR8Uint; else if(!strcmp(fmt,"r32uint"))pf=MTLPixelFormatR32Uint;
 const char*rt="uint";
 for(int mgd=0;mgd<2;mgd++){
  MTLTextureDescriptor*td=[MTLTextureDescriptor new];
  td.pixelFormat=pf;td.width=W;td.height=H;td.sampleCount=N;td.textureType=MTLTextureType2DMultisample;
  td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
  td.storageMode = mgd?MTLStorageModeManaged:MTLStorageModeShared;
  id<MTLTexture>tex=nil; @try{tex=[dev newTextureWithDescriptor:td];}@catch(NSException*e){printf("%s storage=%d CREATE_FAIL %s\n",fmt,mgd,[[e reason]UTF8String]);continue;}
  if(!tex){printf("%s storage=%d nil\n",fmt,mgd);continue;}
  NSError*e=nil;
  NSString*s=[NSString stringWithFormat:@"#include <metal_stdlib>\nusing namespace metal;\n"
    "static inline uint hh(uint x,uint y,uint s,uint k){uint h=2166136261u;h=(h^x)*16777619u;h=(h^y)*16777619u;h=(h^s)*16777619u;h=(h^k)*16777619u;return h;}\n"
    "struct VO{float4 p [[position]];};\n"
    "vertex VO v(uint i [[vertex_id]]){float2 q[3]={float2(-1,-3),float2(-1,1),float2(3,1)};VO o;o.p=float4(q[i],0,1);return o;}\n"
    "fragment %s f(VO in [[stage_in]],uint sid [[sample_id]]){uint x=uint(in.p.x),y=uint(in.p.y);return hh(x,y,sid,0);}\n",rt];
  id<MTLLibrary>lib=[dev newLibraryWithSource:s options:nil error:&e];
  MTLRenderPipelineDescriptor*rpd=[MTLRenderPipelineDescriptor new];
  rpd.vertexFunction=[lib newFunctionWithName:@"v"];rpd.fragmentFunction=[lib newFunctionWithName:@"f"];
  rpd.colorAttachments[0].pixelFormat=pf;rpd.rasterSampleCount=N;
  id<MTLRenderPipelineState>rps=[dev newRenderPipelineStateWithDescriptor:rpd error:&e];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor renderPassDescriptor];
  rp.colorAttachments[0].texture=tex;rp.colorAttachments[0].loadAction=MTLLoadActionClear;rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLRenderCommandEncoder>en=[cb renderCommandEncoderWithDescriptor:rp];
  [en setRenderPipelineState:rps];[en drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[en endEncoding];
  if(mgd){ id<MTLBlitCommandEncoder>bl=[cb blitCommandEncoder]; [bl synchronizeResource:tex]; [bl endEncoding]; }
  [cb commit];[cb waitUntilCompleted];
  printf("%s storage=%s render status=%ld\n",fmt,mgd?"Managed":"Shared",(long)[cb status]);
  if(doDump && mgd){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(500000);}   // dump only Managed
 }
 return 0;}}
