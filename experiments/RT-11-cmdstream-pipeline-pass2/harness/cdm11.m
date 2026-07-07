// cdm11.m — RT-11 compute-launch (CDM) probe: effective-vs-API threadgroup mapping,
// and the threadgroup-memory (32 KiB) budget as a DIFFERENT resource from MRT color.
//
// Purpose:
//  (a) NEW HOLE: decode the CDM effective/driver-chosen threadgroup (RT-2a caveat) by
//      dispatching many threadsPerThreadgroup values and capturing CDM record
//      +0x1c/+0x20/+0x24 (0x100000b0000). Print pipeline threadExecutionWidth +
//      maxTotalThreadsPerThreadgroup so the mapping can be explained.
//  (b) Confirm 32 KiB is the explicit-threadgroup-memory budget: sweep dynamic
//      threadgroup memory and report accept/reject + the shader-BO tgmem field
//      ((bytes<<2)|0x80 @ shaderBO+0x40, per EXP-0024).
//
// CLEAN-ROOM: OWN-SHADER + public Metal API. Our own MSL compiled at runtime.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o cdm11 cdm11.m
//
// Usage: cdm11 [--gx N --gy N --gz N] [--tgx N --tgy N --tgz N] [--tgmem BYTES] [--dump]

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void pva(const char*l,uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }

int main(int argc,char**argv){@autoreleasepool{
    long gx=64,gy=1,gz=1,tgx=32,tgy=1,tgz=1,tgmem=0; int doDump=0;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--gx")&&i+1<argc) gx=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--gy")&&i+1<argc) gy=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--gz")&&i+1<argc) gz=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--tgx")&&i+1<argc) tgx=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--tgy")&&i+1<argc) tgy=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--tgz")&&i+1<argc) tgz=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--tgmem")&&i+1<argc) tgmem=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--dump")) doDump=1;
    }
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name]UTF8String]);
    printf("CONFIG grid=(%ld,%ld,%ld) tg=(%ld,%ld,%ld) tgmem=%ld maxTGmem=%lu\n",
           gx,gy,gz,tgx,tgy,tgz,tgmem,(unsigned long)[dev maxThreadgroupMemoryLength]);

    NSString*src;
    if(tgmem>0){
        src=@"#include <metal_stdlib>\nusing namespace metal;\n"
          "kernel void km(device float* o [[buffer(0)]], threadgroup float* s [[threadgroup(0)]],\n"
          "  uint tid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]){\n"
          "  s[lid%16]=float(tid); threadgroup_barrier(mem_flags::mem_threadgroup); o[tid]=s[lid%16]; }\n";
    } else {
        src=@"#include <metal_stdlib>\nusing namespace metal;\n"
          "kernel void km(device float* o [[buffer(0)]], uint tid [[thread_position_in_grid]]){ o[tid]=float(tid)*0.5; }\n";
    }
    NSError*err=nil;
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    if(!lib){printf("SHADER_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"km"] error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    printf("PSO threadExecutionWidth=%lu maxTotalThreadsPerThreadgroup=%lu staticTGmem=%lu\n",
           (unsigned long)[pso threadExecutionWidth],(unsigned long)[pso maxTotalThreadsPerThreadgroup],
           (unsigned long)[pso staticThreadgroupMemoryLength]);

    id<MTLBuffer> out=[dev newBufferWithLength:1<<20 options:MTLResourceStorageModeShared];
    pva("outBuf",[out gpuAddress]);
    id<MTLCommandQueue> q=[dev newCommandQueue];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setBuffer:out offset:0 atIndex:0];
    if(tgmem>0) [enc setThreadgroupMemoryLength:(NSUInteger)tgmem atIndex:0];
    [enc dispatchThreads:MTLSizeMake(gx,gy,gz) threadsPerThreadgroup:MTLSizeMake(tgx,tgy,tgz)];
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld err=%s\n",(long)[cb status],[cb error]?[[[cb error]localizedDescription]UTF8String]:"none");
    if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    return 0;
}}
