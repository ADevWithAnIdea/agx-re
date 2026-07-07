// tgcap11.m — RT-11: is 32 KiB the STATIC threadgroup-memory pipeline gate?
// Create compute pipelines declaring a static [[threadgroup]] byte array of N bytes and
// report pipeline-creation success + staticThreadgroupMemoryLength. Shows 32 KiB is the
// explicit-threadgroup/imageblock budget (distinct from the MRT color-store path which
// renders to 128 KiB). Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o tgcap11 tgcap11.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
int main(int argc,char**argv){@autoreleasepool{
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("maxThreadgroupMemoryLength=%lu\n",(unsigned long)[dev maxThreadgroupMemoryLength]);
    long sizes[]={4096,16384,32768,32800,49152,65536,131072};
    for(int i=0;i<7;i++){
        long nbytes=sizes[i]; long nfloat=nbytes/4;
        NSString*src=[NSString stringWithFormat:
          @"#include <metal_stdlib>\nusing namespace metal;\n"
           "kernel void km(device float* o [[buffer(0)]], uint tid [[thread_position_in_grid]], uint lid [[thread_position_in_threadgroup]]){\n"
           "  threadgroup float s[%ld];\n s[lid%%%ld]=float(tid); threadgroup_barrier(mem_flags::mem_threadgroup); o[tid]=s[0]; }\n",
           nfloat,nfloat];
        NSError*err=nil;
        id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
        if(!lib){ printf("bytes=%-7ld LIB_FAIL %s\n",nbytes,[[err localizedDescription]UTF8String]); continue; }
        id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"km"] error:&err];
        if(!pso){ printf("bytes=%-7ld PIPELINE_REJECTED %s\n",nbytes,[[err localizedDescription]UTF8String]); continue; }
        printf("bytes=%-7ld PIPELINE_OK staticTGmem=%lu maxTotalThreads=%lu\n",
               nbytes,(unsigned long)[pso staticThreadgroupMemoryLength],(unsigned long)[pso maxTotalThreadsPerThreadgroup]);
    }
    return 0;
}}
