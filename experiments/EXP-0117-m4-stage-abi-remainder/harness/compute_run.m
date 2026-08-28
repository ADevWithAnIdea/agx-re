// compute_run.m -- EXP-0117 generic compute dispatch+readback harness
// (OWN-SHADER + HW-PROBE). Compiles OUR OWN MSL, builds a compute pipeline
// for a named kernel of the shape `kernel void FN(device float *out
// [[buffer(0)]], uint gid [[thread_position_in_grid]])`, dispatches N
// threads, reads back the float array. Used for the CALL-nesting-depth
// sweep (kernels/callchain.metal): a REAL execution + readback is what
// finds a silently-wrong result, not just a structural compile.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o compute_run compute_run.m
// Usage: compute_run --source S.metal --function FN --n N

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void usageDie(const char *m) { fprintf(stderr, "compute_run: %s\n", m); exit(1); }

enum { O_SRC=128, O_FN, O_N };
static const struct option L[] = {
    {"source", required_argument, 0, O_SRC}, {"function", required_argument, 0, O_FN},
    {"n", required_argument, 0, O_N}, {0,0,0,0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *srcp=0, *fnname=0; unsigned n=8;
    int c;
    while ((c = getopt_long(argc, argv, "", L, 0)) > 0) {
        switch (c) { case O_SRC: srcp=optarg; break; case O_FN: fnname=optarg; break; case O_N: n=(unsigned)strtoul(optarg,0,0); break; }
    }
    if (!srcp || !fnname) usageDie("need --source and --function");

    NSError *err=nil;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) usageDie("no device");
    id<MTLCommandQueue> q = [dev newCommandQueue];
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp] encoding:NSUTF8StringEncoding error:&err];
    if (!src) usageDie("read src");
    MTLCompileOptions *co = [MTLCompileOptions new];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) { printf("{\"status\":\"FAIL\",\"stage\":\"compile\",\"error\":\"%s\"}\n",
                        [[[err localizedDescription] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] UTF8String]); return 0; }
    id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:fnname]];
    if (!fn) { printf("{\"status\":\"FAIL\",\"stage\":\"function\",\"error\":\"not found\"}\n"); return 0; }
    id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
    if (!pso) { printf("{\"status\":\"FAIL\",\"stage\":\"pipeline\",\"error\":\"%s\"}\n",
                        [[[err localizedDescription] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] UTF8String]); return 0; }

    id<MTLBuffer> outbuf = [dev newBufferWithLength:(NSUInteger)n*4 options:MTLResourceStorageModeShared];
    memset(outbuf.contents, 0xAA, (NSUInteger)n*4);
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setBuffer:outbuf offset:0 atIndex:0];
    NSUInteger tew = pso.threadExecutionWidth;
    MTLSize grid = MTLSizeMake(n,1,1);
    MTLSize tg = MTLSizeMake(MIN(n, tew), 1, 1);
    [enc dispatchThreads:grid threadsPerThreadgroup:tg];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if (cb.error) {
        printf("{\"status\":\"FAIL\",\"stage\":\"cmdbuf\",\"error\":\"%s\"}\n",
               [[[cb.error localizedDescription] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] UTF8String]);
        return 0;
    }
    float *fp = (float*)outbuf.contents;
    NSMutableString *arr = [NSMutableString string];
    for (unsigned i=0;i<n;i++) [arr appendFormat:@"%s%.8g", i?",":"", fp[i]];
    printf("{\"status\":\"OK\",\"function\":\"%s\",\"n\":%u,\"values\":[%s]}\n", fnname, n, [arr UTF8String]);
    return 0;
}}
