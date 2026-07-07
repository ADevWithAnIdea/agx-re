// tvar.m — parametric OWN Metal harness for GPU TIMESTAMP / COUNTER-SAMPLE RE.
//
// Part of EXP-0027. Creates an MTLCounterSampleBuffer over the timestamp counter set
// and samples counters at dispatch/draw boundaries (sampleCountersInBuffer:...), so we
// can (a) diff the command stream WITH vs WITHOUT sampling to find the timestamp-write
// encoding, and (b) resolve the counter values and correlate GPU ticks to wall-clock to
// pin the timestamp period/format.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. No Apple binary read.
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o tvar tvar.m
//
// Usage: tvar --mode MODE [--dump]
//   MODE: none      compute dispatch, no sampling (baseline)
//         csample   compute + sampleCountersInBuffer at 2 boundaries
//         rsample   render draw + render-pass sampleBufferAttachments (stage boundaries)
//         correlate just print device timestamp correlation + counter-set info (no dump)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <time.h>
#include <mach/mach_time.h>

static void print_va(const char *l, uint64_t va){ printf("VA %-12s = 0x%016llx\n",l,(unsigned long long)va); }

static id<MTLCounterSet> find_ts_set(id<MTLDevice> dev){
  for (id<MTLCounterSet> cs in dev.counterSets){
    printf("COUNTERSET %s\n",[cs.name UTF8String]);
    for (id<MTLCounter> c in cs.counters) printf("   counter %s\n",[c.name UTF8String]);
    if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { /* prefer this */ }
  }
  for (id<MTLCounterSet> cs in dev.counterSets)
    if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) return cs;
  return nil;
}

int main(int argc,char**argv){
 @autoreleasepool{
  const char*modeS="csample"; int doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--mode")&&i+1<argc) modeS=argv[++i];
    else if(!strcmp(argv[i],"--dump")) doDump=1;
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  printf("CONFIG mode=%s\n",modeS);

  // ---- device timestamp correlation (period) ----
  MTLTimestamp c0=0,g0=0,c1=0,g1=0;
  [dev sampleTimestamps:&c0 gpuTimestamp:&g0];
  struct timespec ts={0,50*1000*1000}; nanosleep(&ts,NULL);          // 50 ms
  [dev sampleTimestamps:&c1 gpuTimestamp:&g1];
  double cpu_ns=(double)(c1-c0), gpu_d=(double)(g1-g0);
  printf("TSCORR cpu0=%llu gpu0=%llu cpu1=%llu gpu1=%llu\n",
         (unsigned long long)c0,(unsigned long long)g0,(unsigned long long)c1,(unsigned long long)g1);
  printf("TSCORR dCPU(ns~)=%.0f dGPU=%.0f  gpu_ticks_per_cpu_ns=%.6f  ns_per_gpu_tick=%.6f\n",
         cpu_ns,gpu_d, gpu_d/cpu_ns, cpu_ns/gpu_d);

  id<MTLCounterSet> tsset=find_ts_set(dev);
  if(!tsset){ printf("NO_TIMESTAMP_COUNTERSET\n"); if(!strcmp(modeS,"correlate")) return 0; }

  if(!strcmp(modeS,"correlate")) return 0;

  NSError*err=nil;
  id<MTLCommandQueue> q=[dev newCommandQueue];

  printf("SUPPORTS dispatchBoundary=%d drawBoundary=%d stageBoundary=%d\n",
         (int)[dev supportsCounterSampling:MTLCounterSamplingPointAtDispatchBoundary],
         (int)[dev supportsCounterSampling:MTLCounterSamplingPointAtDrawBoundary],
         (int)[dev supportsCounterSampling:MTLCounterSamplingPointAtStageBoundary]);

  // ---- sample buffer over timestamp set (only for sampling modes) ----
  id<MTLCounterSampleBuffer> sb=nil;
  int wantSample = (!strcmp(modeS,"csample")||!strcmp(modeS,"rsample"));
  if(tsset && wantSample){
    MTLCounterSampleBufferDescriptor*d=[MTLCounterSampleBufferDescriptor new];
    d.counterSet=tsset; d.sampleCount=4; d.storageMode=MTLStorageModeShared;
    d.label=@"tsbuf";
    sb=[dev newCounterSampleBufferWithDescriptor:d error:&err];
    if(!sb) printf("SAMPLEBUF_FAIL %s\n",[[err localizedDescription]UTF8String]);
  }

  int isRender = !strcmp(modeS,"rsample") || !strcmp(modeS,"rnone");
  if(!isRender){
    // ---- COMPUTE path ----
    NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void c_main(device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ float x=i; for(int k=0;k<64;k++) x=fma(x,1.0001f,1.0f); o[i]=x; }\n";
    id<MTLLibrary> cl=[dev newLibraryWithSource:src options:nil error:&err];
    id<MTLComputePipelineState> cps=[dev newComputePipelineStateWithFunction:[cl newFunctionWithName:@"c_main"] error:&err];
    id<MTLBuffer> ob=[dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];
    print_va("outBuf",[ob gpuAddress]);
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> ce=[cb computeCommandEncoder];
    [ce setComputePipelineState:cps]; [ce setBuffer:ob offset:0 atIndex:0];
    int sampling = !strcmp(modeS,"csample") && sb && [dev supportsCounterSampling:MTLCounterSamplingPointAtDispatchBoundary];
    if(!strcmp(modeS,"csample") && !sampling) printf("CSAMPLE_UNSUPPORTED dispatch-boundary sampling not available\n");
    if(sampling) [ce sampleCountersInBuffer:sb atSampleIndex:0 withBarrier:YES];
    [ce dispatchThreadgroups:(MTLSize){32,1,1} threadsPerThreadgroup:(MTLSize){32,1,1}];
    if(sampling) [ce sampleCountersInBuffer:sb atSampleIndex:1 withBarrier:YES];
    [ce endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld\n",(long)[cb status]);
  } else {
    // ---- RENDER path (stage-boundary sampling via sampleBufferAttachments) ----
    NSString*g=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct VO{float4 pos [[position]];};\n"
      "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]){VO o;o.pos=float4(p[vid],0,1);return o;}\n"
      "fragment float4 f_main(){return float4(1,0.5,0.25,1);}\n";
    id<MTLLibrary> gl=[dev newLibraryWithSource:g options:nil error:&err];
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[gl newFunctionWithName:@"v_main"];
    pd.fragmentFunction=[gl newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    long W=64,H=64,bpp=4; NSUInteger bpr=((W*bpp)+255)&~255UL;
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget; td.storageMode=MTLStorageModeShared;
    id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
    id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
    print_va("rtBuf",[rtb gpuAddress]);
    id<MTLBuffer> vb=[dev newBufferWithLength:24 options:MTLResourceStorageModeShared];
    float*vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
    print_va("vtxBuf",[vb gpuAddress]);
    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=target;
    rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    if(sb){
      rp.sampleBufferAttachments[0].sampleBuffer=sb;
      rp.sampleBufferAttachments[0].startOfVertexSampleIndex=0;
      rp.sampleBufferAttachments[0].endOfVertexSampleIndex=1;
      rp.sampleBufferAttachments[0].startOfFragmentSampleIndex=2;
      rp.sampleBufferAttachments[0].endOfFragmentSampleIndex=3;
    }
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso]; [enc setVertexBuffer:vb offset:0 atIndex:0];
    MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1];
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld\n",(long)[cb status]);
  }

  // ---- resolve timestamps ----
  if(sb && strcmp(modeS,"none")!=0){
    NSData*rd=[sb resolveCounterRange:NSMakeRange(0,4)];
    if(rd){
      const uint64_t*t=(const uint64_t*)[rd bytes]; NSUInteger n=[rd length]/8;
      for(NSUInteger i=0;i<n;i++) printf("TS[%lu]=%llu (0x%016llx)\n",(unsigned long)i,(unsigned long long)t[i],(unsigned long long)t[i]);
      if(n>=2 && t[1]>=t[0]) printf("TS delta(0->1)=%llu gpu-ticks\n",(unsigned long long)(t[1]-t[0]));
      if(n>=4 && t[3]>=t[0]) printf("TS delta(0->3)=%llu gpu-ticks\n",(unsigned long long)(t[3]-t[0]));
    } else printf("RESOLVE_FAIL\n");
  }
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
 }
}
