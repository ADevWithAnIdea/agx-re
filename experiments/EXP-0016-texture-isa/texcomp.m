// texcomp.m -- EXP-0016 compute texture runner. Forces a compute pipeline FROM
// OUR OWN archived (possibly spliced) machine code and binds a texture so
// texture.read / texture.write / sample(level) compute kernels can be run and
// their texel movement observed. CLEAN-ROOM: public Metal API on our own shader.
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o texcomp texcomp.m
// Usage: texcomp --archive A.bin --source S.metal --function F --mode read|write
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
enum{OPT_MODE=128,OPT_SAMP};
static const struct option lo[]={{"archive",1,0,'a'},{"source",1,0,'s'},{"function",1,0,'f'},
    {"mode",1,0,OPT_MODE},{"sampler",0,0,OPT_SAMP},{0,0,0,0}};
int main(int c,char**v){@autoreleasepool{
  const char*arch=0,*src=0,*fn=0,*mode="read";BOOL wantSamp=NO;int o;
  while((o=getopt_long(c,v,"a:s:f:",lo,0))>0){switch(o){
    case 'a':arch=optarg;break;case 's':src=optarg;break;case 'f':fn=optarg;break;
    case OPT_MODE:mode=optarg;break;case OPT_SAMP:wantSamp=YES;break;}}
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

  // 4x4 RGBA8 texture. read-mode: preload grid texels. write-mode: writable, zeroed.
  BOOL wr=(strcmp(mode,"write")==0)||(strcmp(mode,"readwrite")==0);
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:
      MTLPixelFormatRGBA8Unorm width:4 height:4 mipmapped:NO];
  td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite; td.storageMode=MTLStorageModeShared;
  id<MTLTexture>T=[dev newTextureWithDescriptor:td];
  unsigned char tb[64];
  for(int y=0;y<4;y++)for(int x=0;x<4;x++){unsigned char*p=tb+(y*4+x)*4;
      p[0]=(y*4+x)*16;p[1]=x*64;p[2]=y*64;p[3]=255;}
  [T replaceRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0 withBytes:tb bytesPerRow:16];

  id<MTLBuffer>inb=[dev newBufferWithLength:16*16 options:MTLResourceStorageModeShared]; // 16 float4
  float*inf=(float*)[inb contents];
  for(int i=0;i<16;i++){inf[i*4+0]=i/16.0f;inf[i*4+1]=(15-i)/16.0f;inf[i*4+2]=(i&3)/4.0f;inf[i*4+3]=1.0f;}
  id<MTLBuffer>outb=[dev newBufferWithLength:16*16 options:MTLResourceStorageModeShared];
  memset([outb contents],0,16*16);

  id<MTLSamplerState>smp=nil;
  if(wantSamp){MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];smp=[dev newSamplerStateWithDescriptor:sd];}

  id<MTLCommandQueue>q=[dev newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];
  id<MTLComputeCommandEncoder>en=[cb computeCommandEncoder];
  [en setComputePipelineState:ps];
  [en setTexture:T atIndex:0];
  if(smp)[en setSamplerState:smp atIndex:0];
  // write kernel reads buffer(0)=colors; read/sample kernels write buffer(0)=out.
  [en setBuffer:(wr?inb:outb) offset:0 atIndex:0];
  [en setBuffer:inb offset:0 atIndex:1];
  [en dispatchThreads:MTLSizeMake(16,1,1) threadsPerThreadgroup:MTLSizeMake(16,1,1)];
  [en endEncoding];[cb commit];[cb waitUntilCompleted];
  if([cb status]==MTLCommandBufferStatusError)fail("CMDBUF_ERROR","cb",[cb error]);

  if(wr){ // read back the texture
    unsigned char rb[64];
    [T getBytes:rb bytesPerRow:16 fromRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0];
    for(int i=0;i<16;i++){unsigned char*p=rb+i*4;
      printf("TEXEL %d %d %d rgba=%d,%d,%d,%d\n",i,i&3,i>>2,p[0],p[1],p[2],p[3]);}
  } else { // print out buffer as float4
    float*of=(float*)[outb contents];
    for(int i=0;i<16;i++)printf("OUT %d %.3f,%.3f,%.3f,%.3f\n",i,of[i*4],of[i*4+1],of[i*4+2],of[i*4+3]);
  }
  st("OK");fflush(stdout);return 0;
}}
