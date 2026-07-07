// a_ts.m -- RT-12 Part A: independent re-verify of GPU-timestamp claims.
//   timestampPeriod = 1.0 (cpu==gpu ns) ; sampling supported ONLY at stage boundary
//   (dispatch- and draw-boundary sampling unsupported -> resolve all-zero).
// CLEAN-ROOM: OWN-SHADER + public Metal API. No iotrace needed. See ../../CLAUDE.md.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o a_ts a_ts.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <unistd.h>
static id<MTLCounterSet> tsSet(id<MTLDevice> dev){
  for(id<MTLCounterSet> cs in [dev counterSets]) if([[cs name] isEqualToString:MTLCommonCounterSetTimestamp]) return cs;
  return nil;
}
int main(int argc,char**argv){ @autoreleasepool{
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  // period / clock correlation
  MTLTimestamp c0=0,g0=0,c1=0,g1=0;
  [dev sampleTimestamps:&c0 gpuTimestamp:&g0];
  usleep(60000);
  [dev sampleTimestamps:&c1 gpuTimestamp:&g1];
  double dc=(double)(c1-c0), dg=(double)(g1-g0);
  printf("TSCORR cpu0=%llu gpu0=%llu dCPU=%.0f dGPU=%.0f ratio_gpu_per_cpu=%.6f\n",
    (unsigned long long)c0,(unsigned long long)g0,dc,dg,dg/dc);
  // sampling-point support
  BOOL sStage=[dev supportsCounterSampling:MTLCounterSamplingPointAtStageBoundary];
  BOOL sDraw =[dev supportsCounterSampling:MTLCounterSamplingPointAtDrawBoundary];
  BOOL sDisp =[dev supportsCounterSampling:MTLCounterSamplingPointAtDispatchBoundary];
  BOOL sBlit =[dev supportsCounterSampling:MTLCounterSamplingPointAtBlitBoundary];
  printf("SUPPORTS stageBoundary=%d drawBoundary=%d dispatchBoundary=%d blitBoundary=%d\n",sStage,sDraw,sDisp,sBlit);

  id<MTLCounterSet> cs=tsSet(dev);
  if(!cs){printf("NO_TIMESTAMP_COUNTERSET\n");return 0;}
  MTLCounterSampleBufferDescriptor*d=[MTLCounterSampleBufferDescriptor new];
  d.counterSet=cs; d.storageMode=MTLStorageModeShared; d.sampleCount=4;
  NSError*err=nil; id<MTLCounterSampleBuffer> sb=[dev newCounterSampleBufferWithDescriptor:d error:&err];
  if(!sb){printf("SAMPLEBUF_FAIL %s\n",[[err localizedDescription]UTF8String]);return 0;}
  id<MTLCommandQueue> q=[dev newCommandQueue];

  // (1) COMPUTE with dispatch-boundary sampling attempt -> expect all-zero (unsupported)
  {
    NSString*k=@"#include <metal_stdlib>\nusing namespace metal;\nkernel void kk(device float*o [[buffer(0)]],uint i [[thread_position_in_grid]]){o[i]=float(i)*1e-9;}\n";
    id<MTLLibrary> lib=[dev newLibraryWithSource:k options:nil error:&err];
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"kk"] error:&err];
    id<MTLBuffer> ob=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    MTLComputePassDescriptor*cpd=[MTLComputePassDescriptor new];
    MTLComputePassSampleBufferAttachmentDescriptor*sa=cpd.sampleBufferAttachments[0];
    sa.sampleBuffer=sb; sa.startOfEncoderSampleIndex=0; sa.endOfEncoderSampleIndex=1;
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoderWithDescriptor:cpd];
    [enc setComputePipelineState:pso]; [enc setBuffer:ob offset:0 atIndex:0];
    [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
    [enc endEncoding];
    id<MTLBlitCommandEncoder> bl=[cb blitCommandEncoder];
    id<MTLBuffer> res=[dev newBufferWithLength:32 options:MTLResourceStorageModeShared];
    [bl resolveCounters:sb inRange:NSMakeRange(0,4) destinationBuffer:res destinationOffset:0];
    [bl endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    uint64_t*T=(uint64_t*)[res contents];
    printf("COMPUTE_DISPATCH_SAMPLE status=%ld TS[0..3]=%llu %llu %llu %llu\n",(long)[cb status],
      (unsigned long long)T[0],(unsigned long long)T[1],(unsigned long long)T[2],(unsigned long long)T[3]);
  }
  // (2) RENDER with stage-boundary sampling -> expect real nanoseconds
  {
    NSString*g=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct VO{float4 pos [[position]];};\n"
      "vertex VO v_main(uint vid [[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid],0,1);return o;}\n"
      "fragment float4 f_main(VO in [[stage_in]]){return float4(1,1,1,1);}\n";
    id<MTLLibrary> gl=[dev newLibraryWithSource:g options:nil error:&err];
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[gl newFunctionWithName:@"v_main"]; pd.fragmentFunction=[gl newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    long W=64,H=64; NSUInteger bpr=((W*4)+255)&~255UL;
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget; td.storageMode=MTLStorageModeShared;
    id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
    id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=target; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1); rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    rp.sampleBufferAttachments[0].sampleBuffer=sb;
    rp.sampleBufferAttachments[0].startOfVertexSampleIndex=0;
    rp.sampleBufferAttachments[0].endOfVertexSampleIndex=1;
    rp.sampleBufferAttachments[0].startOfFragmentSampleIndex=2;
    rp.sampleBufferAttachments[0].endOfFragmentSampleIndex=3;
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
    [enc setRenderPipelineState:pso]; [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    id<MTLBlitCommandEncoder> bl=[cb blitCommandEncoder];
    id<MTLBuffer> res=[dev newBufferWithLength:32 options:MTLResourceStorageModeShared];
    [bl resolveCounters:sb inRange:NSMakeRange(0,4) destinationBuffer:res destinationOffset:0];
    [bl endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    uint64_t*T=(uint64_t*)[res contents];
    printf("RENDER_STAGE_SAMPLE status=%ld TS[0..3]=%llu %llu %llu %llu (vtxDelta=%lld fragDelta=%lld)\n",(long)[cb status],
      (unsigned long long)T[0],(unsigned long long)T[1],(unsigned long long)T[2],(unsigned long long)T[3],
      (long long)(T[1]-T[0]),(long long)(T[3]-T[2]));
  }
  return 0;
}}
