// desc7.m — DESC-7: (a) plain device-buffer out-of-bounds READ behavior (there is no
// length/format word in the buffer binding, so is there ANY HW bounds check?), and
// (b) the texture_buffer (typed/texel buffer) descriptor shape. Clean-room: OWN-SHADER
// + HW-PROBE + DATA-TRACE. Build: clang -arch arm64e -fobjc-arc -framework Metal
//   -framework Foundation -o desc7 desc7.m
//
// Usage: desc7 [--oob IDX] [--texbuf] [--dump]
//   default: read a[IDX] from a 16-element buffer and report value + cb status.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char*l,uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }

int main(int argc,char**argv){ @autoreleasepool {
  long oob=-1; int texbuf=0, doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--oob")&&i+1<argc) oob=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--texbuf")) texbuf=1;
    else if(!strcmp(argv[i],"--dump")) doDump=1;
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name] UTF8String]);
  id<MTLCommandQueue> q=[dev newCommandQueue];
  NSError* err=nil;

  if(texbuf){
    // texture_buffer<float> — a typed buffer bound as a texture. Capture its descriptor.
    const int N=256;
    id<MTLBuffer> src=[dev newBufferWithLength:N*4 options:MTLResourceStorageModeShared];
    float* sp=(float*)[src contents]; for(int i=0;i<N;i++) sp[i]=(float)i;
    print_va("srcBuf",[src gpuAddress]);
    MTLTextureDescriptor* td=[MTLTextureDescriptor new];
    td.textureType=MTLTextureTypeTextureBuffer; td.pixelFormat=MTLPixelFormatR32Float;
    td.width=N; td.height=1; td.usage=MTLTextureUsageShaderRead;
    td.storageMode=MTLStorageModeShared; td.resourceOptions=MTLResourceStorageModeShared;
    id<MTLTexture> tb=[src newTextureWithDescriptor:td offset:0 bytesPerRow:N*4];
    if(!tb){ printf("TEXBUF_FAIL\n"); return 1; }
    printf("TEXBUF ok width=%d gpuResourceID=0x%llx\n",N,(unsigned long long)tb.gpuResourceID._impl);
    NSString* src2=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "kernel void k(texture_buffer<float,access::read> t [[texture(0)]],\n"
      "  device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){ o[i]=t.read(i).x; }\n";
    id<MTLLibrary> lib=[dev newLibraryWithSource:src2 options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
    id<MTLBuffer> obuf=[dev newBufferWithLength:64*4 options:MTLResourceStorageModeShared];
    print_va("obuf",obuf.gpuAddress);
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso]; [enc setTexture:tb atIndex:0]; [enc setBuffer:obuf offset:0 atIndex:0];
    [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
    [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
    printf("TEXBUF SUBMIT status=%ld\n",(long)[cb status]);
    float* op=(float*)[obuf contents];
    printf("TEXBUF readback: %.1f %.1f %.1f %.1f\n",op[0],op[1],op[2],op[3]);
    if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    return 0;
  }

  // OOB read: small buffer, read a[oob].
  const int N=16;
  id<MTLBuffer> a=[dev newBufferWithLength:N*4 options:MTLResourceStorageModeShared];
  float* ap=(float*)[a contents]; for(int i=0;i<N;i++) ap[i]=100.0f+i;
  print_va("aBuf",[a gpuAddress]);
  printf("aBuf length=%d bytes; reading index=%ld (byte off=0x%lx)\n",N*4,oob,oob*4);
  id<MTLBuffer> obuf=[dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
  float* op=(float*)[obuf contents]; op[0]=-1.0f;
  uint32_t idx=(uint32_t)(oob<0?0:oob);
  id<MTLBuffer> ib=[dev newBufferWithBytes:&idx length:4 options:MTLResourceStorageModeShared];
  NSString* s=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]], constant uint& idx [[buffer(1)]],\n"
    "  device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]){ if(i==0) o[0]=a[idx]; }\n";
  id<MTLLibrary> lib=[dev newLibraryWithSource:s options:nil error:&err];
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
  if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setBuffer:a offset:0 atIndex:0]; [enc setBuffer:ib offset:0 atIndex:1]; [enc setBuffer:obuf offset:0 atIndex:2];
  [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("OOB SUBMIT status=%ld err=%s\n",(long)[cb status],[cb error]?[[[cb error] localizedDescription] UTF8String]:"none");
  printf("OOB result a[%u] = %.3f (in-bounds would be %.1f)\n",idx,op[0], idx<(uint32_t)N?100.0f+idx:-999.0f);
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
}}
