// heaparg.m — OWN program for O2-B task #4: bindless sampler-heap (argument buffer) layout.
// Builds an argument buffer holding an ARRAY of K sampler states (each with a distinct
// descriptor), then (a) hexdumps the Shared argument buffer directly from the CPU to reveal
// the per-slot encoding + stride, (b) also writes each sampler's gpuResourceID directly into
// a buffer (the Metal-3 manual-bindless form), and (c) runs a compute dispatch that indexes
// heap.samps[idx] to sample a gradient texture — HW-validating that a shader-computed index
// selects the right sampler. Extends the Tier-2 argument-buffer model (EXP-0011/0015).
//
// CLEAN-ROOM: OWN-SHADER + public Metal API + HW-PROBE. Our MSL/resources. No Apple binary
// introspected. Build: clang -fobjc-arc -framework Metal -framework Foundation -o heaparg heaparg.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void hexdump(const char* label, const void* p, size_t n, uint64_t base){
  const unsigned char* b=(const unsigned char*)p;
  printf("%s (%zu bytes @ gpu_va 0x%llx):\n",label,n,(unsigned long long)base);
  for(size_t o=0;o<n;o+=16){
    printf("  +%04zx:",o);
    for(size_t i=0;i<16 && o+i<n;i++) printf(" %02x",b[o+i]);
    printf("\n");
  }
}

int main(int argc,char**argv){ @autoreleasepool {
  long K=8;
  for(int i=1;i<argc;i++){ if(!strcmp(argv[i],"--k")&&i+1<argc) K=strtol(argv[++i],0,0); }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\nK=%ld maxArgBufSamplers=%lu\n",[[dev name] UTF8String],K,
    (unsigned long)[dev maxArgumentBufferSamplerCount]);

  // K distinct sampler states (vary filter + address so descriptors differ), arg-buffer capable.
  NSMutableArray* smps=[NSMutableArray array];
  for(long k=0;k<K;k++){
    MTLSamplerDescriptor* sd=[MTLSamplerDescriptor new];
    sd.supportArgumentBuffers=YES;
    sd.minFilter=(k&1)?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;
    sd.magFilter=(k&2)?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;
    sd.sAddressMode=(k&4)?MTLSamplerAddressModeRepeat:MTLSamplerAddressModeClampToEdge;
    sd.tAddressMode=MTLSamplerAddressModeClampToEdge;
    id<MTLSamplerState> s=[dev newSamplerStateWithDescriptor:sd];
    [smps addObject:s];
    printf("SAMP[%ld] gpuResourceID=0x%llx  (min=%s mag=%s s=%s)\n",k,
      (unsigned long long)s.gpuResourceID._impl,
      (k&1)?"lin":"near",(k&2)?"lin":"near",(k&4)?"rep":"edge");
  }

  // MSL: argument buffer struct with an array of samplers, indexed dynamically.
  NSString* src=[NSString stringWithFormat:
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "struct SHeap { array<sampler,%ld> samps; };\n"
     "kernel void k(constant SHeap& heap [[buffer(0)]], texture2d<float> t [[texture(0)]],\n"
     "  device float* o [[buffer(1)]], constant uint& idx [[buffer(2)]],\n"
     "  uint i [[thread_position_in_grid]]) {\n"
     "  uint j = (idx + i) %% %ld;\n"
     "  o[i] = t.sample(heap.samps[j], float2(0.5,0.5)).x; }\n", K, K];
  NSError* err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
  id<MTLFunction> fn=[lib newFunctionWithName:@"k"];
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:fn error:&err];
  if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

  // (a) Argument-encoder path: encode the K samplers into a Shared arg buffer, then hexdump it.
  id<MTLArgumentEncoder> ae=[fn newArgumentEncoderWithBufferIndex:0];
  NSUInteger aeLen=[ae encodedLength];
  printf("ARGENC encodedLength=%lu  (=> per-sampler stride=%lu)\n",(unsigned long)aeLen,(unsigned long)(aeLen/(K?K:1)));
  id<MTLBuffer> argbuf=[dev newBufferWithLength:aeLen options:MTLResourceStorageModeShared];
  memset([argbuf contents],0xAB,aeLen);
  [ae setArgumentBuffer:argbuf offset:0];
  for(long k=0;k<K;k++) [ae setSamplerState:smps[k] atIndex:k];
  printf("ARGBUF gpuAddress=0x%llx\n",(unsigned long long)[argbuf gpuAddress]);
  hexdump("ARGBUF (argument-encoder, array<sampler,K>)",[argbuf contents], aeLen, [argbuf gpuAddress]);

  // (b) Manual-bindless path: write each sampler's gpuResourceID directly into a buffer.
  id<MTLBuffer> ridbuf=[dev newBufferWithLength:K*sizeof(uint64_t) options:MTLResourceStorageModeShared];
  uint64_t* rp=(uint64_t*)[ridbuf contents];
  for(long k=0;k<K;k++) rp[k]=((id<MTLSamplerState>)smps[k]).gpuResourceID._impl;
  hexdump("RIDBUF (raw gpuResourceID array)",[ridbuf contents], K*sizeof(uint64_t), [ridbuf gpuAddress]);

  // (c) HW-validate indexing: gradient texture, dispatch, read back.
  MTLTextureDescriptor* td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float width:2 height:2 mipmapped:NO];
  td.usage=MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  float row0[2]={0.0f,1.0f}, row1[2]={2.0f,3.0f};
  [tex replaceRegion:MTLRegionMake2D(0,0,2,1) mipmapLevel:0 withBytes:row0 bytesPerRow:8];
  [tex replaceRegion:MTLRegionMake2D(0,1,2,1) mipmapLevel:0 withBytes:row1 bytesPerRow:8];

  id<MTLBuffer> obuf=[dev newBufferWithLength:64*4 options:MTLResourceStorageModeShared];
  id<MTLBuffer> idxbuf=[dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
  *(uint32_t*)[idxbuf contents]=0;
  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setBuffer:argbuf offset:0 atIndex:0];
  // Samplers are NOT MTLResources; they live in the device-global sampler table addressed by
  // gpuResourceID and need no per-encoder residency call.
  [enc setTexture:tex atIndex:0];
  [enc setBuffer:obuf offset:0 atIndex:1];
  [enc setBuffer:idxbuf offset:0 atIndex:2];
  [enc dispatchThreads:MTLSizeMake(K,1,1) threadsPerThreadgroup:MTLSizeMake(K<32?K:32,1,1)];
  [enc endEncoding];
  [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld\n",(long)[cb status]);
  if([cb status]!=MTLCommandBufferStatusCompleted && [cb error])
    printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
  float* o=(float*)[obuf contents];
  // sampler j is linear iff (j&1); center sample of [0,1;2,3] => nearest=3.0, linear=1.5
  printf("SAMPLES(center, idx=i):");
  for(long k=0;k<K;k++) printf(" s%ld=%.3f",k,o[k]);
  printf("\n(expect nearest slots ~3.000, linear slots ~1.500)\n");
  return 0;
}}
