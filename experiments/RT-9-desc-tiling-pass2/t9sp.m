// t9sp.m -- RT-9 sampler + PBE (storage-image) descriptor re-confirmation.
// Sampler: binds texture + ONE sampler (config from CLI) + a reference "never" sampler so
//   the 8-byte sampler descriptors are captured & localizable in the dump.
// PBE: binds a texture with a chosen MSL access qualifier (sample/read/write/readwrite) to
//   capture the sampled vs PBE(write) descriptors and the read_write TWO-descriptor case.
// CLEAN-ROOM: OWN-SHADER + public Metal API + HW-PROBE. No Apple binary disassembled.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o t9sp t9sp.m
// Usage: t9sp --mode samp --cmp less --s repeat --t mirror --r edge --border owhite --dump
//        t9sp --mode pbe  --access readwrite --w 96 --h 48 --dump

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static MTLSamplerAddressMode addr(const char*s){
  if(!strcmp(s,"repeat"))return MTLSamplerAddressModeRepeat;
  if(!strcmp(s,"mirror"))return MTLSamplerAddressModeMirrorRepeat;
  if(!strcmp(s,"clampzero"))return MTLSamplerAddressModeClampToZero;
  if(!strcmp(s,"border"))return MTLSamplerAddressModeClampToBorderColor;
  if(!strcmp(s,"mirroredge"))return MTLSamplerAddressModeMirrorClampToEdge;
  return MTLSamplerAddressModeClampToEdge;
}
static MTLCompareFunction cmpf(const char*s){
  if(!strcmp(s,"less"))return MTLCompareFunctionLess;
  if(!strcmp(s,"lequal"))return MTLCompareFunctionLessEqual;
  if(!strcmp(s,"greater"))return MTLCompareFunctionGreater;
  if(!strcmp(s,"gequal"))return MTLCompareFunctionGreaterEqual;
  if(!strcmp(s,"equal"))return MTLCompareFunctionEqual;
  if(!strcmp(s,"nequal"))return MTLCompareFunctionNotEqual;
  if(!strcmp(s,"always"))return MTLCompareFunctionAlways;
  return MTLCompareFunctionNever;
}
static MTLSamplerBorderColor bord(const char*s){
  if(!strcmp(s,"oblack"))return MTLSamplerBorderColorOpaqueBlack;
  if(!strcmp(s,"owhite"))return MTLSamplerBorderColorOpaqueWhite;
  return MTLSamplerBorderColorTransparentBlack;
}

int main(int argc,char**argv){ @autoreleasepool{
  const char*mode="samp",*cmp="never",*sA="edge",*tA="edge",*rA="edge",*border="tblack",*access="write";
  long W=96,H=48; int doDump=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    #define ARG(f) (!strcmp(a,f)&&i+1<argc)
    if(ARG("--mode"))mode=argv[++i]; else if(ARG("--cmp"))cmp=argv[++i];
    else if(ARG("--s"))sA=argv[++i]; else if(ARG("--t"))tA=argv[++i]; else if(ARG("--r"))rA=argv[++i];
    else if(ARG("--border"))border=argv[++i]; else if(ARG("--access"))access=argv[++i];
    else if(ARG("--w"))W=atol(argv[++i]); else if(ARG("--h"))H=atol(argv[++i]);
    else if(!strcmp(a,"--dump"))doDump=1;
    #undef ARG
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\nMODE %s cmp=%s addr=%s/%s/%s border=%s access=%s %ldx%ld\n",
    [[dev name]UTF8String],mode,cmp,sA,tA,rA,border,access,W,H);
  id<MTLCommandQueue> q=[dev newCommandQueue]; NSError*err=nil;

  if(!strcmp(mode,"samp")){
    // reference "never" sampler + test sampler, both bound; descriptor blocks captured.
    MTLSamplerDescriptor*ref=[MTLSamplerDescriptor new];
    MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];
    sd.sAddressMode=addr(sA); sd.tAddressMode=addr(tA); sd.rAddressMode=addr(rA);
    sd.borderColor=bord(border);
    MTLCompareFunction cf=cmpf(cmp);
    if(cf!=MTLCompareFunctionNever) sd.compareFunction=cf;
    id<MTLSamplerState> sref=[dev newSamplerStateWithDescriptor:ref];
    id<MTLSamplerState> stest=[dev newSamplerStateWithDescriptor:sd];
    NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void k(texture2d<float> t [[texture(0)]], sampler sref [[sampler(0)]], sampler stest [[sampler(1)]],"
      " device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){"
      " o[i]=t.sample(sref,float2(0.5,0.5)).x + t.sample(stest,float2(0.2,0.7)).x; }\n";
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:32 height:32 mipmapped:NO];
    td.usage=MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
    id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
    id<MTLBuffer> ob=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb=[q commandBuffer]; id<MTLComputeCommandEncoder> e=[cb computeCommandEncoder];
    [e setComputePipelineState:pso]; [e setTexture:tex atIndex:0];
    [e setSamplerState:sref atIndex:0]; [e setSamplerState:stest atIndex:1];
    [e setBuffer:ob offset:0 atIndex:0];
    [e dispatchThreads:MTLSizeMake(8,1,1) threadsPerThreadgroup:MTLSizeMake(8,1,1)];
    [e endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("SAMP status=%ld\n",(long)[cb status]);
  } else { // pbe
    NSString*qual = !strcmp(access,"sample")?@"access::sample": !strcmp(access,"read")?@"access::read":
                    !strcmp(access,"readwrite")?@"access::read_write":@"access::write";
    NSString*rd = !strcmp(access,"sample")?
       @"kernel void k(texture2d<float,access::sample> t [[texture(0)]], device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ o[i]=t.read(uint2(i,0)).x; }\n" :
       [NSString stringWithFormat:@"#include <metal_stdlib>\nusing namespace metal;\n"
        "kernel void k(texture2d<float,%@> t [[texture(0)]], device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){"
        " %@ }\n", qual,
        !strcmp(access,"write")?@"t.write(float4(float(i)),uint2(i,0));":
        !strcmp(access,"readwrite")?@"float4 v=t.read(uint2(i,0)); t.write(v+float4(1),uint2(i,0));":
        @"o[i]=t.read(uint2(i,0)).x;"];
    NSString*src=[NSString stringWithFormat:@"#include <metal_stdlib>\nusing namespace metal;\n%@",rd];
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
    if(!pso){printf("PIPE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
    td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite; td.storageMode=MTLStorageModeShared;
    id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
    id<MTLBuffer> ob=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb=[q commandBuffer]; id<MTLComputeCommandEncoder> e=[cb computeCommandEncoder];
    [e setComputePipelineState:pso]; [e setTexture:tex atIndex:0]; [e setBuffer:ob offset:0 atIndex:0];
    [e dispatchThreads:MTLSizeMake(8,1,1) threadsPerThreadgroup:MTLSizeMake(8,1,1)];
    [e endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("PBE status=%ld\n",(long)[cb status]);
  }
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(600000); }
  return 0;
}}
