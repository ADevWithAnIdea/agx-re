// compute_callret.m -- EXP-0129 H2 dedicated dispatch+readback for
// kernels/split_callret.metal's k_callret (OWN-SHADER + HW-PROBE). Real
// dispatch + real readback, no splicing.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o compute_callret compute_callret.m
// Usage: compute_callret --source S.metal --n N

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void usageDie(const char *m) { fprintf(stderr, "compute_callret: %s\n", m); exit(1); }

enum { O_SRC=128, O_N };
static const struct option L[] = {
    {"source", required_argument, 0, O_SRC}, {"n", required_argument, 0, O_N}, {0,0,0,0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *srcp=0; unsigned n=8;
    int c;
    while ((c = getopt_long(argc, argv, "", L, 0)) > 0) {
        switch (c) { case O_SRC: srcp=optarg; break; case O_N: n=(unsigned)strtoul(optarg,0,0); break; }
    }
    if (!srcp) usageDie("need --source");

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
    id<MTLFunction> fn = [lib newFunctionWithName:@"k_callret"];
    if (!fn) { printf("{\"status\":\"FAIL\",\"stage\":\"function\",\"error\":\"not found\"}\n"); return 0; }
    id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
    if (!pso) { printf("{\"status\":\"FAIL\",\"stage\":\"pipeline\",\"error\":\"%s\"}\n",
                        [[[err localizedDescription] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] UTF8String]); return 0; }

    float *inv = malloc(n*4);
    for (unsigned i = 0; i < n; i++) inv[i] = (float)i * 1.5f + 0.25f;
    id<MTLBuffer> inbuf = [dev newBufferWithBytes:inv length:(NSUInteger)n*4 options:MTLResourceStorageModeShared];
    id<MTLBuffer> outbuf = [dev newBufferWithLength:(NSUInteger)n*16 options:MTLResourceStorageModeShared];
    memset(outbuf.contents, 0xAA, (NSUInteger)n*16);

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setBuffer:inbuf offset:0 atIndex:0];
    [enc setBuffer:outbuf offset:0 atIndex:1];
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
    float *op = (float*)outbuf.contents;
    NSMutableString *arr = [NSMutableString string];
    for (unsigned i=0;i<n;i++) {
        [arr appendFormat:@"%s[%.8g,%.8g,%.8g,%.8g]", i?",":"", op[i*4],op[i*4+1],op[i*4+2],op[i*4+3]];
    }
    NSMutableString *iarr = [NSMutableString string];
    for (unsigned i=0;i<n;i++) [iarr appendFormat:@"%s%.8g", i?",":"", inv[i]];
    free(inv);
    printf("{\"status\":\"OK\",\"n\":%u,\"in\":[%s],\"out\":[%s]}\n", n, [iarr UTF8String], [arr UTF8String]);
    return 0;
}}
