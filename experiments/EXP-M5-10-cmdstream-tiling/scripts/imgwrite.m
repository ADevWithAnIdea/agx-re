// imgwrite.m — OWN compute kernel binding a texture as access::write / read_write / read,
// to capture the PBE (storage-image) descriptor vs the sampled descriptor. Clean-room own MSL/API.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
static MTLPixelFormat pf(const char*s){
  if(!strcmp(s,"rgba8"))return MTLPixelFormatRGBA8Unorm;
  if(!strcmp(s,"bgra8"))return MTLPixelFormatBGRA8Unorm;
  if(!strcmp(s,"r32f"))return MTLPixelFormatR32Float;
  if(!strcmp(s,"r32u"))return MTLPixelFormatR32Uint;
  if(!strcmp(s,"rgba16f"))return MTLPixelFormatRGBA16Float;
  if(!strcmp(s,"rgba32f"))return MTLPixelFormatRGBA32Float;
  if(!strcmp(s,"r8"))return MTLPixelFormatR8Unorm;
  if(!strcmp(s,"rg32f"))return MTLPixelFormatRG32Float;
  return MTLPixelFormatRGBA8Unorm;
}
int main(int argc,char**argv){@autoreleasepool{
  const char*fmt="rgba8",*mode="write"; long W=64,H=64; int doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--fmt")&&i+1<argc)fmt=argv[++i];
    else if(!strcmp(argv[i],"--mode")&&i+1<argc)mode=argv[++i];
    else if(!strcmp(argv[i],"--w")&&i+1<argc)W=atol(argv[++i]);
    else if(!strcmp(argv[i],"--h")&&i+1<argc)H=atol(argv[++i]);
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s fmt=%s mode=%s W=%ld H=%ld\n",[[dev name]UTF8String],fmt,mode,W,H);
  const char*acc = !strcmp(mode,"readwrite")?"access::read_write":(!strcmp(mode,"read")?"access::read":"access::write");
  NSString*src=[NSString stringWithFormat:@"#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(texture2d<float,%s> t[[texture(0)]],device float*o[[buffer(0)]],uint2 g[[thread_position_in_grid]]){\n"
    "%s"
    "}\n", acc,
    !strcmp(mode,"read")? "o[g.x]=t.read(g).x;\n" :
    !strcmp(mode,"readwrite")? "float4 v=t.read(g); t.write(v+1.0,g); o[g.x]=v.x;\n" :
    "t.write(float4(g.x,g.y,1,1),g);\n" ];
  NSError*err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:pf(fmt) width:W height:H mipmapped:NO];
  td.usage=MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead;td.storageMode=MTLStorageModeShared;
  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  id<MTLBuffer> bo=[dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];
  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setTexture:tex atIndex:0];[enc setBuffer:bo offset:0 atIndex:0];
  [enc dispatchThreads:MTLSizeMake(W,H,1) threadsPerThreadgroup:MTLSizeMake(8,8,1)];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
