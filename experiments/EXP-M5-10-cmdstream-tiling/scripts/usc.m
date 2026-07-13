// usc.m — bind-grammar probe: draw with N fragment textures + M samplers + K buffers, or a
// compute dispatch with the same. Generates MSL that actually consumes each resource so the
// compiler cannot elide binds. Clean-room: own MSL/API; dumps own BOs.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
int main(int argc,char**argv){@autoreleasepool{
  int ntex=1,nsamp=1,nbuf=1,doDump=0,compute=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--compute"))compute=1;
    else if(!strcmp(argv[i],"--tex")&&i+1<argc)ntex=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--samp")&&i+1<argc)nsamp=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--buf")&&i+1<argc)nbuf=atoi(argv[++i]);
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s compute=%d tex=%d samp=%d buf=%d\n",[[dev name]UTF8String],compute,ntex,nsamp,nbuf);
  id<MTLCommandQueue> q=[dev newCommandQueue];
  NSError*err=nil;
  NSMutableString*s=[NSMutableString stringWithString:@"#include <metal_stdlib>\nusing namespace metal;\n"];
  // param lists
  NSMutableString*params=[NSMutableString string];
  for(int i=0;i<ntex;i++)[params appendFormat:@"texture2d<float> t%d[[texture(%d)]],",i,i];
  for(int i=0;i<nsamp;i++)[params appendFormat:@"sampler s%d[[sampler(%d)]],",i,i];
  for(int i=0;i<nbuf;i++)[params appendFormat:@"device float*b%d[[buffer(%d)]],",i,i+ (compute?1:2)]; // leave 0(compute:out)/vs slots
  NSMutableString*body=[NSMutableString string];
  [body appendString:@"float acc=0;"];
  for(int i=0;i<ntex;i++){int si=nsamp?(i%nsamp):0; if(nsamp)[body appendFormat:@"acc+=t%d.sample(s%d,float2(0.5)).x;",i,si]; else [body appendFormat:@"acc+=t%d.read(uint2(0)).x;",i];}
  for(int i=0;i<nbuf;i++)[body appendFormat:@"acc+=b%d[0];",i];
  if(compute){
    [s appendFormat:@"kernel void k(device float*o[[buffer(0)]],%s uint gid[[thread_position_in_grid]]){%s o[gid]=acc;}\n",[params UTF8String],[body UTF8String]];
    id<MTLLibrary> lib=[dev newLibraryWithSource:s options:nil error:&err];
    if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLBuffer> o=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso];[enc setBuffer:o offset:0 atIndex:0];
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:16 height:16 mipmapped:NO];td.usage=MTLTextureUsageShaderRead;td.storageMode=MTLStorageModeShared;
    for(int i=0;i<ntex;i++)[enc setTexture:[dev newTextureWithDescriptor:td] atIndex:i];
    for(int i=0;i<nsamp;i++){MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];[enc setSamplerState:[dev newSamplerStateWithDescriptor:sd] atIndex:i];}
    for(int i=0;i<nbuf;i++)[enc setBuffer:[dev newBufferWithLength:64 options:MTLResourceStorageModeShared] offset:0 atIndex:i+1];
    [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("STATUS=%ld\n",(long)[cb status]);
  } else {
    [s appendString:@"struct VO{float4 pos [[position]];};\n"
      "vertex VO v_main(uint vid[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid%3],0,1);return o;}\n"];
    [s appendFormat:@"fragment float4 f_main(VO in[[stage_in]],%s float4 dummy=float4(0)){%s return float4(acc);}\n",[params UTF8String],[body UTF8String]];
    id<MTLLibrary> lib=[dev newLibraryWithSource:s options:nil error:&err];
    if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[lib newFunctionWithName:@"v_main"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLTextureDescriptor*rt=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:64 height:64 mipmapped:NO];rt.usage=MTLTextureUsageRenderTarget;rt.storageMode=MTLStorageModeShared;
    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];rp.colorAttachments[0].texture=[dev newTextureWithDescriptor:rt];rp.colorAttachments[0].loadAction=MTLLoadActionClear;rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:16 height:16 mipmapped:NO];td.usage=MTLTextureUsageShaderRead;td.storageMode=MTLStorageModeShared;
    for(int i=0;i<ntex;i++)[enc setFragmentTexture:[dev newTextureWithDescriptor:td] atIndex:i];
    for(int i=0;i<nsamp;i++){MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];[enc setFragmentSamplerState:[dev newSamplerStateWithDescriptor:sd] atIndex:i];}
    for(int i=0;i<nbuf;i++)[enc setFragmentBuffer:[dev newBufferWithLength:64 options:MTLResourceStorageModeShared] offset:0 atIndex:i+2];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("STATUS=%ld\n",(long)[cb status]);
  }
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
