// texpat.m — texture memory-layout probe. Writable path: GPU-write texel(x,y)=(y<<16)|x and
// dump the backing BO to infer twiddle/Morton. Non-writable path: report allocatedSize +
// descriptor (compression aux). Clean-room: OWN MSL/API + HW-PROBE (read our own backing bytes).
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
static MTLPixelFormat pf(const char*s){
  if(!strcmp(s,"r32u"))return MTLPixelFormatR32Uint;
  if(!strcmp(s,"r8"))return MTLPixelFormatR8Unorm;
  if(!strcmp(s,"r16u"))return MTLPixelFormatR16Uint;
  if(!strcmp(s,"rg32u"))return MTLPixelFormatRG32Uint;
  if(!strcmp(s,"rgba8"))return MTLPixelFormatRGBA8Unorm;
  if(!strcmp(s,"rgba16f"))return MTLPixelFormatRGBA16Float;
  if(!strcmp(s,"rgba32f"))return MTLPixelFormatRGBA32Float;
  if(!strcmp(s,"rgba8i"))return MTLPixelFormatRGBA8Sint;
  return MTLPixelFormatR32Uint;
}
int main(int argc,char**argv){@autoreleasepool{
  const char*fmt="r32u"; long W=192,H=192; int doDump=0,write=0,mips=0,nowrite=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--write"))write=1;
    else if(!strcmp(argv[i],"--nowrite"))nowrite=1;
    else if(!strcmp(argv[i],"--mips"))mips=1;
    else if(!strcmp(argv[i],"--fmt")&&i+1<argc)fmt=argv[++i];
    else if(!strcmp(argv[i],"--w")&&i+1<argc)W=atol(argv[++i]);
    else if(!strcmp(argv[i],"--h")&&i+1<argc)H=atol(argv[++i]);
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:pf(fmt) width:W height:H mipmapped:(mips?YES:NO)];
  if(nowrite) td.usage=MTLTextureUsageShaderRead|MTLTextureUsageRenderTarget; // compression-eligible
  else td.usage=MTLTextureUsageShaderWrite|MTLTextureUsageShaderRead;         // uncompressed twiddle
  td.storageMode=MTLStorageModeShared;
  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  printf("DEVICE %s fmt=%s W=%ld H=%ld nowrite=%d mips=%d allocatedSize=0x%lx\n",
    [[dev name]UTF8String],fmt,W,H,nowrite,mips,(unsigned long)[tex allocatedSize]);
  if(write && !nowrite){
    NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void k(texture2d<uint,access::write> t[[texture(0)]],uint2 g[[thread_position_in_grid]]){t.write(uint4((g.y<<16)|g.x,0,0,0),g);}\n";
    NSError*err=nil;
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLCommandQueue> q=[dev newCommandQueue];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso];[enc setTexture:tex atIndex:0];
    [enc dispatchThreads:MTLSizeMake(W,H,1) threadsPerThreadgroup:MTLSizeMake(8,8,1)];
    [enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("STATUS=%ld\n",(long)[cb status]);
  }
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
