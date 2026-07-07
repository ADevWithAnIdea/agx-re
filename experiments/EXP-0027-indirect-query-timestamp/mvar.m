// mvar.m — OWN Metal MSAA probe: sample interleave / per-sample addressability.
//
// Part of EXP-0027 (stretch). Extends EXP-0021 (MSAA sample-count field, tile budget).
// Renders to an N-sample MSAA target where the fragment shader writes a DISTINCT value
// per sample_id, then (a) resolves (average of samples), and (b) stores the raw MSAA
// texture and reads each sample back via texture.read(coord,sample) into a linear buffer
// -> proves N independent samples are maintained and their sample-id ordering. Also
// prints VAs + optional --dump for a cmdstream diff of the MSAA attachment descriptor.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API + HW-PROBE. No Apple binary read.
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o mvar mvar.m
//
// Usage: mvar --samples N [--dump]      N in {1,2,4}

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *l, uint64_t va){ printf("VA %-12s = 0x%016llx\n",l,(unsigned long long)va); }

int main(int argc,char**argv){
 @autoreleasepool{
  long S=4; int doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--samples")&&i+1<argc) S=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--dump")) doDump=1;
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  printf("CONFIG samples=%ld supports2=%d supports4=%d\n",S,
    (int)[dev supportsTextureSampleCount:2],(int)[dev supportsTextureSampleCount:4]);
  NSError*err=nil;
  // pass 1: render, fragment writes sample_id as the red channel (distinct per sample)
  NSString*g=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];};\n"
    "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]){VO o;o.pos=float4(p[vid],0,1);return o;}\n"
    "fragment float4 f_main(uint sid [[sample_id]]){ float v=(float)sid/255.0f; return float4(v, v, v, 1); }\n";
  id<MTLLibrary> gl=[dev newLibraryWithSource:g options:nil error:&err];
  if(!gl){printf("LIB_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[gl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[gl newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
  if(S>1){ pd.rasterSampleCount=(NSUInteger)S; }
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PSO_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}

  long W=8,H=8;
  // MSAA color texture (private/memoryless-ish; we Store it to read samples)
  MTLTextureDescriptor*md=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
  if(S>1){ md.textureType=MTLTextureType2DMultisample; md.sampleCount=(NSUInteger)S; }
  md.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; md.storageMode=MTLStorageModePrivate;
  id<MTLTexture> msaa=[dev newTextureWithDescriptor:md];

  // resolve target (1 sample, shared so we can read the average)
  long bpp=4; NSUInteger bpr=((W*bpp)+255)&~255UL;
  MTLTextureDescriptor*rd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
  rd.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; rd.storageMode=MTLStorageModeShared;
  id<MTLBuffer> rvb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
  id<MTLTexture> resolve=[rvb newTextureWithDescriptor:rd offset:0 bytesPerRow:bpr];
  print_va("resolveBuf",[rvb gpuAddress]);

  id<MTLBuffer> vb=[dev newBufferWithLength:24 options:MTLResourceStorageModeShared];
  float*vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
  print_va("vtxBuf",[vb gpuAddress]);

  // per-sample readback buffer: [sample][pixel0.rgba]
  id<MTLBuffer> sampOut=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
  print_va("sampOut",[sampOut gpuAddress]);

  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture= (S>1)?msaa:resolve;
  rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
  if(S>1){ rp.colorAttachments[0].storeAction=MTLStoreActionStoreAndMultisampleResolve;
           rp.colorAttachments[0].resolveTexture=resolve; }
  else   { rp.colorAttachments[0].storeAction=MTLStoreActionStore; }
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
  [enc setRenderPipelineState:pso]; [enc setVertexBuffer:vb offset:0 atIndex:0];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1];
  [enc endEncoding];

  // pass 2 (compute): read each sample of the stored MSAA texture into sampOut
  if(S>1){
    NSString*c=[NSString stringWithFormat:@"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void k(texture2d_ms<float> t [[texture(0)]], device uint* o [[buffer(0)]], uint s [[thread_position_in_grid]]){\n"
      "  if(s>=%ld) return; float4 c=t.read(uint2(4,4), s); o[s]=uint(round(c.r*255.0));\n}\n",S];
    id<MTLLibrary> cl=[dev newLibraryWithSource:c options:nil error:&err];
    id<MTLComputePipelineState> cps=[dev newComputePipelineStateWithFunction:[cl newFunctionWithName:@"k"] error:&err];
    if(cps){ id<MTLComputeCommandEncoder> ce=[cb computeCommandEncoder];
      [ce setComputePipelineState:cps]; [ce setTexture:msaa atIndex:0]; [ce setBuffer:sampOut offset:0 atIndex:0];
      [ce dispatchThreads:(MTLSize){(NSUInteger)S,1,1} threadsPerThreadgroup:(MTLSize){(NSUInteger)S,1,1}];
      [ce endEncoding]; }
    else printf("CPS_FAIL %s\n",[[err localizedDescription]UTF8String]);
  }
  [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT done status=%ld\n",(long)[cb status]);

  unsigned char px[4]={0}; [resolve getBytes:px bytesPerRow:bpr fromRegion:MTLRegionMake2D(4,4,1,1) mipmapLevel:0];
  printf("RESOLVE px(4,4) r=%d g=%d b=%d a=%d  (expect avg of sample_ids)\n",px[0],px[1],px[2],px[3]);
  if(S>1){ uint32_t*so=(uint32_t*)[sampOut contents];
    printf("PERSAMPLE read(4,4): "); for(long s=0;s<S;s++) printf("s%ld=%u ",s,so[s]); printf(" (expect s==sample_id)\n"); }
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
 }
}
