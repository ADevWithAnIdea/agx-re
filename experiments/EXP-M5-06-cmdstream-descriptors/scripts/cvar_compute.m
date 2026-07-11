// cvar_compute.m — parametric OWN compute harness for CDM/tgmem/occupancy probing.
// CLEAN-ROOM: own MSL, own draw, public Metal API. No Apple-code introspection.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
static void pv(const char*l,uint64_t v){printf("VA %-8s = 0x%016llx\n",l,(unsigned long long)v);}
int main(int argc,char**argv){@autoreleasepool{
  long grid=64,tg=32,tgmem=0; int heavy=0,doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--grid")&&i+1<argc)grid=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--tg")&&i+1<argc)tg=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--tgmem")&&i+1<argc)tgmem=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--heavy"))heavy=1;
    else if(!strcmp(argv[i],"--dump"))doDump=1;
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s grid=%ld tg=%ld tgmem=%ld heavy=%d\n",[[dev name]UTF8String],grid,tg,tgmem,heavy);
  NSMutableString*src=[NSMutableString stringWithString:
    @"#include <metal_stdlib>\nusing namespace metal;\n"];
  if(tgmem>0) [src appendFormat:@"kernel void k(device const float*a[[buffer(0)]],device const float*b[[buffer(1)]],device float*o[[buffer(2)]],uint i[[thread_position_in_grid]],uint li[[thread_position_in_threadgroup]]){threadgroup float sh[%ld];sh[li%%%ld]=a[i];threadgroup_barrier(mem_flags::mem_threadgroup);o[i]=sh[li%%%ld]+b[i];}\n",tgmem/4,tgmem/4,tgmem/4];
  else if(heavy) [src appendString:
    @"kernel void k(device const float*a[[buffer(0)]],device const float*b[[buffer(1)]],device float*o[[buffer(2)]],uint i[[thread_position_in_grid]]){float acc[24];for(int j=0;j<24;j++)acc[j]=a[i]*float(j+1)+b[i];float s=0;for(int j=0;j<24;j++)s+=acc[j]*acc[(j+7)%24];o[i]=s;}\n"];
  else [src appendString:
    @"kernel void k(device const float*a[[buffer(0)]],device const float*b[[buffer(1)]],device float*o[[buffer(2)]],uint i[[thread_position_in_grid]]){o[i]=a[i]+b[i];}\n"];
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
  pv("bufA",[ba gpuAddress]);pv("bufB",[bb gpuAddress]);pv("bufOut",[bo gpuAddress]);
  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setBuffer:ba offset:0 atIndex:0];[enc setBuffer:bb offset:0 atIndex:1];[enc setBuffer:bo offset:0 atIndex:2];
  [enc dispatchThreads:MTLSizeMake(grid,1,1) threadsPerThreadgroup:MTLSizeMake(tg,1,1)];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld maxTPT=%lu\n",(long)[cb status],(unsigned long)pso.maxTotalThreadsPerThreadgroup);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
