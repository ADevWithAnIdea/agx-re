// tvcmp.m -- EXP-0034 compute harness for texture VARIANTS: depth sample_compare
// (shadow/PCF), gather_compare, and LOD query. Forces a (possibly spliced) compute
// pipeline FROM OUR OWN archived machine code (MTLPipelineOptionFailOnBinaryArchiveMiss)
// and binds a depth OR rgba texture + a configurable (compare) sampler, then reads
// back the result buffer. CLEAN-ROOM: public Metal API on our own compiled shader.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o tvcmp tvcmp.m
// Usage: tvcmp --archive A.bin --source S.metal --function F
//    [--texfmt depth|rgba]         depth32float 4x4 (default) or rgba8 4x4 grid
//    [--compare NAME]              never|less|lessequal|greater|greaterequal|equal|notequal|always (default lessequal)
//    [--filter nearest|linear]     sampler min/mag filter (default nearest)
//    [--mips]                      create a mipmapped rgba texture (for LOD query)
//    [--out float|float4]          read back N floats or N float4 (default float4)
//    [--depthpat i16|half]         depth[texel]: i/16 (default) or 0.5 constant
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif
static void st(const char*s){printf("STATUS %s\n",s);}
static void fail(const char*s,const char*m,NSError*e){st(s);
  if(e)printf("ERROR %s: %s\n",m,[[e localizedDescription]UTF8String]);else if(m)printf("ERROR %s\n",m);
  fflush(stdout);exit(1);}
static MTLCompareFunction cmpByName(const char*n){
  if(!strcmp(n,"never"))return MTLCompareFunctionNever;
  if(!strcmp(n,"less"))return MTLCompareFunctionLess;
  if(!strcmp(n,"lessequal"))return MTLCompareFunctionLessEqual;
  if(!strcmp(n,"greater"))return MTLCompareFunctionGreater;
  if(!strcmp(n,"greaterequal"))return MTLCompareFunctionGreaterEqual;
  if(!strcmp(n,"equal"))return MTLCompareFunctionEqual;
  if(!strcmp(n,"notequal"))return MTLCompareFunctionNotEqual;
  if(!strcmp(n,"always"))return MTLCompareFunctionAlways;
  return MTLCompareFunctionLessEqual;
}
enum{OPT_FMT=128,OPT_CMP,OPT_FILT,OPT_MIPS,OPT_OUT,OPT_DP};
static const struct option lo[]={{"archive",1,0,'a'},{"source",1,0,'s'},{"function",1,0,'f'},
  {"texfmt",1,0,OPT_FMT},{"compare",1,0,OPT_CMP},{"filter",1,0,OPT_FILT},
  {"mips",0,0,OPT_MIPS},{"out",1,0,OPT_OUT},{"depthpat",1,0,OPT_DP},{0,0,0,0}};
int main(int c,char**v){@autoreleasepool{
  const char*arch=0,*src=0,*fn=0,*fmt="depth",*cmp="lessequal",*filt="nearest",*out="float4",*dp="i16";
  BOOL mips=NO;int o;
  while((o=getopt_long(c,v,"a:s:f:",lo,0))>0){switch(o){
    case 'a':arch=optarg;break;case 's':src=optarg;break;case 'f':fn=optarg;break;
    case OPT_FMT:fmt=optarg;break;case OPT_CMP:cmp=optarg;break;case OPT_FILT:filt=optarg;break;
    case OPT_MIPS:mips=YES;break;case OPT_OUT:out=optarg;break;case OPT_DP:dp=optarg;break;}}
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

  // ---- texture ----
  BOOL depth=(strcmp(fmt,"depth")==0);
  id<MTLTexture>T;
  int MIP = mips?3:1;   // 4x4 -> mips 0(4x4),1(2x2),2(1x1)
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:
      depth?MTLPixelFormatDepth32Float:MTLPixelFormatRGBA8Unorm width:4 height:4 mipmapped:mips];
  td.usage=MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared; td.mipmapLevelCount=MIP;
  T=[dev newTextureWithDescriptor:td];
  if(depth){
    float db[16];
    for(int i=0;i<16;i++) db[i]= (strcmp(dp,"half")==0)?0.5f:(i/16.0f);
    [T replaceRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0 withBytes:db bytesPerRow:16];
    printf("DEPTHTEX pat=%s\n",dp);
  } else {
    unsigned char tb[64];
    for(int y=0;y<4;y++)for(int x=0;x<4;x++){unsigned char*p=tb+(y*4+x)*4;
      p[0]=(y*4+x)*16;p[1]=x*64;p[2]=y*64;p[3]=255;}
    [T replaceRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0 withBytes:tb bytesPerRow:16];
    for(int m=1;m<MIP;m++){int w=4>>m; unsigned char mb[64];
      for(int k=0;k<w*w;k++){mb[k*4]=200;mb[k*4+1]=200;mb[k*4+2]=200;mb[k*4+3]=255;}
      [T replaceRegion:MTLRegionMake2D(0,0,w,w) mipmapLevel:m withBytes:mb bytesPerRow:w*4];}
  }

  // ---- sampler ----
  MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];
  BOOL lin=(strcmp(filt,"linear")==0);
  sd.minFilter=lin?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;
  sd.magFilter=lin?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;
  sd.mipFilter=mips?MTLSamplerMipFilterNearest:MTLSamplerMipFilterNotMipmapped;
  if(strcmp(cmp,"none")!=0){ sd.compareFunction=cmpByName(cmp); }
  printf("SAMPLER compare=%s filter=%s\n",cmp,filt);
  id<MTLSamplerState>smp=[dev newSamplerStateWithDescriptor:sd];

  // ---- buffers ----
  id<MTLBuffer>outb=[dev newBufferWithLength:16*16 options:MTLResourceStorageModeShared];
  memset([outb contents],0,16*16);
  // buffer(1): ref floats (sc_ref) / uv float2 (LOD query) / slice uint / dir float3
  id<MTLBuffer>b1=[dev newBufferWithLength:16*16 options:MTLResourceStorageModeShared];
  { float*f=(float*)[b1 contents];
    for(int i=0;i<16;i++){ // interpret as needed by the kernel
      f[i*4+0]=(i%4)/4.0f; f[i*4+1]=(i/4)/4.0f; f[i*4+2]=0.0f; f[i*4+3]=0.0f; }
    // also a plausible scalar ref pattern in the first N floats for sc_ref
  }
  // scalar-ref buffer overlay for sc_ref: ref[i]=i/16 (so pass/fail sweeps across texels)
  id<MTLBuffer>refb=[dev newBufferWithLength:16*4 options:MTLResourceStorageModeShared];
  { float*f=(float*)[refb contents]; for(int i=0;i<16;i++) f[i]=i/16.0f; }

  id<MTLCommandQueue>q=[dev newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];
  id<MTLComputeCommandEncoder>en=[cb computeCommandEncoder];
  [en setComputePipelineState:ps];
  [en setTexture:T atIndex:0];
  [en setSamplerState:smp atIndex:0];
  [en setBuffer:outb offset:0 atIndex:0];
  // choose buffer(1): sc_ref wants scalar refb; LOD/dir kernels want b1
  if(strncmp(fn,"sc_ref",6)==0) [en setBuffer:refb offset:0 atIndex:1];
  else [en setBuffer:b1 offset:0 atIndex:1];
  [en dispatchThreads:MTLSizeMake(16,1,1) threadsPerThreadgroup:MTLSizeMake(16,1,1)];
  [en endEncoding];[cb commit];[cb waitUntilCompleted];
  if([cb status]==MTLCommandBufferStatusError)fail("CMDBUF_ERROR","cb",[cb error]);

  if(strcmp(out,"float")==0){ float*f=(float*)[outb contents];
    for(int i=0;i<16;i++)printf("OUT %d %.4f\n",i,f[i]);
  } else { float*f=(float*)[outb contents];
    for(int i=0;i<16;i++)printf("OUT %d %.4f,%.4f,%.4f,%.4f\n",i,f[i*4],f[i*4+1],f[i*4+2],f[i*4+3]);
  }
  st("OK");fflush(stdout);return 0;
}}
