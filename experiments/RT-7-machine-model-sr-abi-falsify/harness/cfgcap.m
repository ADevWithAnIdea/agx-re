// cfgcap.m -- RT-7 minimal compute dispatcher that raises SIGUSR1 after
// waitUntilCompleted so the iotrace interposer snapshots the launch-descriptor BO
// while it is still mapped. Compiles OUR OWN MSL from source (the compiled
// register footprint -> config word is the object of study).
// CLEAN-ROOM: OWN-SHADER + DATA-TRACE (reuses the existing iotrace.dylib read-only).
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o cfgcap cfgcap.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <unistd.h>
int main(int argc,char**argv){@autoreleasepool{
    if(argc<2){fprintf(stderr,"usage: cfgcap kernel.metal\n");return 2;}
    NSError*e=0;
    id<MTLDevice>d=MTLCreateSystemDefaultDevice();
    NSString*src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[1]]
                  encoding:NSUTF8StringEncoding error:&e];
    if(!src){fprintf(stderr,"read src\n");return 1;}
    MTLCompileOptions*co=[MTLCompileOptions new];
    co.fastMathEnabled=NO;
    id<MTLLibrary>lib=[d newLibraryWithSource:src options:co error:&e];
    if(!lib){fprintf(stderr,"compile: %s\n",[[e localizedDescription] UTF8String]);return 1;}
    id<MTLFunction>fn=[lib newFunctionWithName:@"k"];
    id<MTLComputePipelineState>ps=[d newComputePipelineStateWithFunction:fn error:&e];
    if(!ps){fprintf(stderr,"pso\n");return 1;}
    id<MTLBuffer>b0=[d newBufferWithLength:4096 options:0];
    id<MTLBuffer>b1=[d newBufferWithLength:4096 options:0];
    uint32_t n=1; id<MTLBuffer>b2=[d newBufferWithBytes:&n length:4 options:0];
    id<MTLCommandQueue>q=[d newCommandQueue];
    id<MTLCommandBuffer>cb=[q commandBuffer];
    id<MTLComputeCommandEncoder>ce=[cb computeCommandEncoder];
    [ce setComputePipelineState:ps];
    [ce setBuffer:b0 offset:0 atIndex:0];
    [ce setBuffer:b1 offset:0 atIndex:1];
    [ce setBuffer:b2 offset:0 atIndex:2];
    [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    fprintf(stderr,"cfgcap: dispatched, raising SIGUSR1\n");
    kill(getpid(), SIGUSR1);
    usleep(300000);
    return 0;
}}
