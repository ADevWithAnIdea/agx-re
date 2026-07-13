// occ_probe.m — parametric OWN compute harness to correlate the launch-descriptor
// config word (+0x00 bit23 occupancy tier) with register footprint on M5.
// Builds a kernel holding N cross-dependent live float accumulators (so the allocator
// cannot collapse them), optionally emits the exact MSL it used (--emit PATH, so the SAME
// source can be fed to shdump to read f0), dispatches, and on --dump raises SIGUSR1 so the
// iotrace interposer snapshots the command-stream BOs.
// CLEAN-ROOM: own MSL, public Metal API. No Apple-code introspection.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
int main(int argc,char**argv){@autoreleasepool{
  long acc=1, grid=64, tg=32; int doDump=0; const char*emit=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--acc")&&i+1<argc)acc=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--grid")&&i+1<argc)grid=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--tg")&&i+1<argc)tg=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--emit")&&i+1<argc)emit=argv[++i];
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  NSMutableString*src=[NSMutableString stringWithString:
    @"#include <metal_stdlib>\nusing namespace metal;\n"];
  [src appendFormat:
    @"kernel void k(device const float*a[[buffer(0)]],device const float*b[[buffer(1)]],"
     "device float*o[[buffer(2)]],uint i[[thread_position_in_grid]]){"
     "float acc[%ld];for(int j=0;j<%ld;j++)acc[j]=a[i]*float(j+1)+b[i];"
     "float s=0;for(int j=0;j<%ld;j++)s+=acc[j]*acc[(j+7)%%%ld];o[i]=s;}\n",
     acc,acc,acc,acc];
  if(emit){FILE*f=fopen(emit,"w");if(f){fputs([src UTF8String],f);fclose(f);}}
  NSError*err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"k"] error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  size_t n=(size_t)grid;
  id<MTLBuffer> ba=[dev newBufferWithLength:n*4 options:MTLResourceStorageModeShared];
  id<MTLBuffer> bb=[dev newBufferWithLength:n*4 options:MTLResourceStorageModeShared];
  id<MTLBuffer> bo=[dev newBufferWithLength:n*4 options:MTLResourceStorageModeShared];
  float*pa=(float*)[ba contents],*pb=(float*)[bb contents];
  for(size_t i=0;i<n;i++){pa[i]=1000.0f+i;pb[i]=0.5f;}
  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setBuffer:ba offset:0 atIndex:0];[enc setBuffer:bb offset:0 atIndex:1];[enc setBuffer:bo offset:0 atIndex:2];
  [enc dispatchThreads:MTLSizeMake(grid,1,1) threadsPerThreadgroup:MTLSizeMake(tg,1,1)];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("acc=%ld STATUS=%ld\n",acc,(long)[cb status]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
