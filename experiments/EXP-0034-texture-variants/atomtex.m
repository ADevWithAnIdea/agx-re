// atomtex.m -- EXP-0034 texture-atomics HW validator. Binds an r32uint texture with
// atomic usage, forces our own archived compute pipeline, dispatches N threads, and
// reads the texel values back. CLEAN-ROOM: public Metal API on our own compiled shader.
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o atomtex atomtex.m
// Usage: atomtex --archive A.bin --source S.metal --function F [--threads N]
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif
static void st(const char*s){printf("STATUS %s\n",s);}
static void fail(const char*s,const char*m,NSError*e){st(s);
  if(e)printf("ERROR %s: %s\n",m,[[e localizedDescription]UTF8String]);else if(m)printf("ERROR %s\n",m);
  fflush(stdout);exit(1);}
enum{OPT_TH=128};
static const struct option lo[]={{"archive",1,0,'a'},{"source",1,0,'s'},{"function",1,0,'f'},
  {"threads",1,0,OPT_TH},{0,0,0,0}};
int main(int c,char**v){@autoreleasepool{
  const char*arch=0,*src=0,*fn=0;long TH=16;int o;
  while((o=getopt_long(c,v,"a:s:f:",lo,0))>0){switch(o){
    case 'a':arch=optarg;break;case 's':src=optarg;break;case 'f':fn=optarg;break;
    case OPT_TH:TH=strtol(optarg,0,0);break;}}
  if(!arch||!src||!fn)fail("FAIL","need --archive --source --function",0);
  id<MTLDevice>dev=MTLCreateSystemDefaultDevice();if(!dev)fail("FAIL","no device",0);
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  NSError*e=0;
  NSString*S=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:src]
      encoding:NSUTF8StringEncoding error:&e];if(!S)fail("COMPILE_FAIL","read",e);
  MTLCompileOptions*co=[MTLCompileOptions new];[co setFastMathEnabled:YES];
  id<MTLLibrary>lib=[dev newLibraryWithSource:S options:co error:&e];if(!lib)fail("COMPILE_FAIL","lib",e);
  id<MTLFunction>F=[lib newFunctionWithName:[NSString stringWithUTF8String:fn]];
  if(!F)fail("FUNCTION_MISSING","fn",0);
  MTLBinaryArchiveDescriptor*ad=[MTLBinaryArchiveDescriptor new];
  [ad setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:arch]]];
  id<MTLBinaryArchive>ar=[dev newBinaryArchiveWithDescriptor:ad error:&e];if(!ar)fail("ARCHIVE_FAIL","ar",e);
  MTLComputePipelineDescriptor*pd=[MTLComputePipelineDescriptor new];[pd setComputeFunction:F];
  [pd setBinaryArchives:@[ar]];
  id<MTLComputePipelineState>ps=[dev newComputePipelineStateWithDescriptor:pd
      options:MTLPipelineOptionFailOnBinaryArchiveMiss reflection:nil error:&e];
  if(!ps)fail("PIPELINE_MISS","pso",e);
  printf("FUNCTION %s\nPIPELINE_SOURCE archive\n",fn);

  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:
      MTLPixelFormatR32Uint width:4 height:4 mipmapped:NO];
  td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;
#ifdef MTLTextureUsageShaderAtomic
  td.usage|=MTLTextureUsageShaderAtomic;
#endif
  td.storageMode=MTLStorageModeShared;
  id<MTLTexture>T=[dev newTextureWithDescriptor:td];
  unsigned int zb[16]; memset(zb,0,sizeof zb);
  [T replaceRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0 withBytes:zb bytesPerRow:16];

  id<MTLCommandQueue>q=[dev newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];
  id<MTLComputeCommandEncoder>en=[cb computeCommandEncoder];
  [en setComputePipelineState:ps];
  [en setTexture:T atIndex:0];
  [en dispatchThreads:MTLSizeMake(TH,1,1) threadsPerThreadgroup:MTLSizeMake(TH<64?TH:64,1,1)];
  [en endEncoding];[cb commit];[cb waitUntilCompleted];
  if([cb status]==MTLCommandBufferStatusError)fail("CMDBUF_ERROR","cb",[cb error]);

  unsigned int rb[16];
  [T getBytes:rb bytesPerRow:16 fromRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0];
  printf("THREADS %ld\n",TH);
  for(int i=0;i<16;i++)printf("TEXEL %d %u\n",i,rb[i]);
  st("OK");fflush(stdout);return 0;
}}
