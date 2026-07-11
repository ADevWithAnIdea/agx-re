// tvar.m — parametric OWN texture/sampler descriptor probe. Clean-room: own MSL/API.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
static MTLPixelFormat pf(const char*s){
  if(!strcmp(s,"rgba8"))return MTLPixelFormatRGBA8Unorm;
  if(!strcmp(s,"bgra8"))return MTLPixelFormatBGRA8Unorm;
  if(!strcmp(s,"r8"))return MTLPixelFormatR8Unorm;
  if(!strcmp(s,"rg8"))return MTLPixelFormatRG8Unorm;
  if(!strcmp(s,"r32f"))return MTLPixelFormatR32Float;
  if(!strcmp(s,"rgba32f"))return MTLPixelFormatRGBA32Float;
  if(!strcmp(s,"rgba16f"))return MTLPixelFormatRGBA16Float;
  if(!strcmp(s,"r16u"))return MTLPixelFormatR16Uint;
  if(!strcmp(s,"rgba8i"))return MTLPixelFormatRGBA8Sint;
  if(!strcmp(s,"rgb10a2"))return MTLPixelFormatRGB10A2Unorm;
  return MTLPixelFormatRGBA8Unorm;
}
int main(int argc,char**argv){@autoreleasepool{
  const char*fmt="rgba8"; long W=64,H=64; int doDump=0,mips=0,arr=0;
  const char*saddr="edge"; int sfilt=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--fmt")&&i+1<argc)fmt=argv[++i];
    else if(!strcmp(argv[i],"--w")&&i+1<argc)W=atol(argv[++i]);
    else if(!strcmp(argv[i],"--h")&&i+1<argc)H=atol(argv[++i]);
    else if(!strcmp(argv[i],"--mips"))mips=1;
    else if(!strcmp(argv[i],"--arr")&&i+1<argc)arr=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--saddr")&&i+1<argc)saddr=argv[++i];
    else if(!strcmp(argv[i],"--sfilt"))sfilt=1;
    else if(!strcmp(argv[i],"--dump"))doDump=1;
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s fmt=%s W=%ld H=%ld mips=%d arr=%d saddr=%s sfilt=%d\n",[[dev name]UTF8String],fmt,W,H,mips,arr,saddr,sfilt);
  NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(texture2d<float> t[[texture(0)]],sampler s[[sampler(0)]],device float*o[[buffer(0)]],uint i[[thread_position_in_grid]]){o[i]=t.sample(s,float2(0.5,0.5)).x;}\n";
  NSError*err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLTextureDescriptor*td;
  if(arr>0){td=[MTLTextureDescriptor new];td.textureType=MTLTextureType2DArray;td.pixelFormat=pf(fmt);td.width=W;td.height=H;td.arrayLength=arr;}
  else td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:pf(fmt) width:W height:H mipmapped:(mips?YES:NO)];
  td.usage=MTLTextureUsageShaderRead;td.storageMode=MTLStorageModeShared;
  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];
  MTLSamplerAddressMode am=MTLSamplerAddressModeClampToEdge;
  if(!strcmp(saddr,"repeat"))am=MTLSamplerAddressModeRepeat;
  else if(!strcmp(saddr,"mirror"))am=MTLSamplerAddressModeMirrorRepeat;
  else if(!strcmp(saddr,"border"))am=MTLSamplerAddressModeClampToBorderColor;
  sd.sAddressMode=am;sd.tAddressMode=am;sd.rAddressMode=am;
  if(sfilt){sd.minFilter=MTLSamplerMinMagFilterLinear;sd.magFilter=MTLSamplerMinMagFilterLinear;sd.mipFilter=MTLSamplerMipFilterLinear;sd.maxAnisotropy=4;}
  id<MTLSamplerState> smp=[dev newSamplerStateWithDescriptor:sd];
  id<MTLBuffer> bo=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setTexture:tex atIndex:0];[enc setSamplerState:smp atIndex:0];[enc setBuffer:bo offset:0 atIndex:0];
  [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
