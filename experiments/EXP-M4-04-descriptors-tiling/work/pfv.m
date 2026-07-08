// pfv.m — check that MTLTextureUsagePixelFormatView disables lossless compression.
// OWN-SHADER + DATA-TRACE. Creates a 64x64 rgba8 optimal texture with ShaderRead(+opt
// PixelFormatView), binds it read via our own compute kernel, dumps the arg buffer.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
int main(int argc,char**argv){@autoreleasepool{
  int pfv = (argc>1 && !strcmp(argv[1],"--pfv"));
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  MTLTextureDescriptor* td=[MTLTextureDescriptor new];
  td.pixelFormat=MTLPixelFormatRGBA8Unorm; td.width=64; td.height=64; td.textureType=MTLTextureType2D;
  td.usage=MTLTextureUsageShaderRead | (pfv?MTLTextureUsagePixelFormatView:0);
  td.storageMode=MTLStorageModeShared;
  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  printf("DEVICE %s pfv=%d TEX_ok=%d\n",[[dev name] UTF8String],pfv,(tex!=nil));
  NSString* rk=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void rd(texture2d<float,access::read> t [[texture(0)]], device float* o [[buffer(0)]],"
    " uint i [[thread_position_in_grid]]){ o[i]=t.read(uint2(i&7,i>>3)).x; }";
  NSError*e=nil; id<MTLLibrary> lib=[dev newLibraryWithSource:rk options:nil error:&e];
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"rd"] error:&e];
  id<MTLBuffer> ob=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
  id<MTLCommandQueue> q=[dev newCommandQueue]; id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso]; [enc setTexture:tex atIndex:0]; [enc setBuffer:ob offset:0 atIndex:0];
  [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld\n",(long)[cb status]);
  fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000);
  return 0;
}}
