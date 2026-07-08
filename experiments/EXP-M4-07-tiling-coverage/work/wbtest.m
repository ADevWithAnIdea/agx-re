#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
static void test(id<MTLDevice>dev,id<MTLCommandQueue>q,MTLPixelFormat pf,MTLTextureType tt,const char*tn,const char*wtt,const char*rtt,int is3d){
 @autoreleasepool{
  MTLTextureDescriptor*td=[MTLTextureDescriptor new];
  td.pixelFormat=pf; td.width=16; td.height=16; td.depth=is3d?4:1; td.arrayLength=is3d?1:4;
  td.textureType=tt; td.storageMode=MTLStorageModeShared;
  td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite;
  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  if(!tex){printf("%-10s TEX_FAIL\n",tn);return;}
  NSError*e=nil;
  NSString*ws=[NSString stringWithFormat:@"#include <metal_stdlib>\nusing namespace metal;\n"
   "kernel void wr(%s<uint,access::write> t [[texture(0)]], uint3 g [[thread_position_in_grid]]){\n"
   " uint v=0xA000u|((g.z&0xf)<<8)|((g.y&0xf)<<4)|(g.x&0xf); t.write(uint4(v,0,0,0), %s); }\n",
   wtt, is3d?"g":"g.xy,g.z"];
  id<MTLLibrary>wl=[dev newLibraryWithSource:ws options:nil error:&e];
  if(!wl){printf("%-10s WCOMPILE_FAIL %s\n",tn,[[e localizedDescription]UTF8String]);return;}
  id<MTLComputePipelineState>wp=[dev newComputePipelineStateWithFunction:[wl newFunctionWithName:@"wr"] error:&e];
  id<MTLCommandBuffer>cb=[q commandBuffer]; id<MTLComputeCommandEncoder>en=[cb computeCommandEncoder];
  [en setComputePipelineState:wp]; [en setTexture:tex atIndex:0];
  [en dispatchThreads:MTLSizeMake(16,16,is3d?4:4) threadsPerThreadgroup:MTLSizeMake(8,8,1)];
  [en endEncoding]; [cb commit]; [cb waitUntilCompleted];
  // read back texel (3,5,2)
  NSString*rs=[NSString stringWithFormat:@"#include <metal_stdlib>\nusing namespace metal;\n"
   "kernel void rd(%s<uint,access::read> t [[texture(0)]], device uint*o [[buffer(0)]], uint i [[thread_position_in_grid]]){ o[0]=t.read(%s).x; }\n",
   rtt, is3d?"uint3(3,5,2)":"uint2(3,5),2"];
  id<MTLLibrary>rl=[dev newLibraryWithSource:rs options:nil error:&e];
  id<MTLComputePipelineState>rp=rl?[dev newComputePipelineStateWithFunction:[rl newFunctionWithName:@"rd"] error:&e]:nil;
  if(!rp){printf("%-10s RCOMPILE_FAIL %s\n",tn,[[e localizedDescription]UTF8String]);return;}
  id<MTLBuffer>ob=[dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
  cb=[q commandBuffer]; en=[cb computeCommandEncoder]; [en setComputePipelineState:rp];
  [en setTexture:tex atIndex:0]; [en setBuffer:ob offset:0 atIndex:0];
  [en dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
  [en endEncoding]; [cb commit]; [cb waitUntilCompleted];
  uint32_t got=((uint32_t*)[ob contents])[0]; uint32_t exp=0xA000|(2<<8)|(5<<4)|3;
  printf("%-10s readback(3,5,2)=0x%04x exp=0x%04x %s\n",tn,got,exp,got==exp?"OK":"MISMATCH");
 }
}
int main(){@autoreleasepool{
 id<MTLDevice>dev=MTLCreateSystemDefaultDevice(); id<MTLCommandQueue>q=[dev newCommandQueue];
 printf("DEV %s\n",[[dev name]UTF8String]);
 test(dev,q,MTLPixelFormatR8Uint,  MTLTextureType3D,"r8-3d",  "texture3d","texture3d",1);
 test(dev,q,MTLPixelFormatR16Uint, MTLTextureType3D,"r16-3d", "texture3d","texture3d",1);
 test(dev,q,MTLPixelFormatR32Uint, MTLTextureType3D,"r32-3d", "texture3d","texture3d",1);
 test(dev,q,MTLPixelFormatR8Uint,  MTLTextureType2DArray,"r8-arr", "texture2d_array","texture2d_array",0);
 test(dev,q,MTLPixelFormatR16Uint, MTLTextureType2DArray,"r16-arr","texture2d_array","texture2d_array",0);
 return 0;}}
