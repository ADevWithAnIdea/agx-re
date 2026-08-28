// compute_probe.m — EXP-0109 HW-PROBE compute harness (OWN-SHADER + HW-PROBE).
//
// Compiles OUR OWN MSL (kernels/cs_probe.metal) ONCE per process, builds ONE
// MTLComputePipelineState, then dispatches it MULTIPLE times with different
// setThreadgroupMemoryLength:atIndex:/threadgroup-size pairs — the SAME
// compiled bytecode across every case — and reads back the result buffer.
// Prints one JSON object per dispatched size to stdout (JSON Lines), plus a
// final summary line.
//
// CLEAN-ROOM: public Metal API only, on our own MSL source. Never
// disassembles or introspects any Apple binary.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation \
//          -o compute_probe compute_probe.m
// Usage: compute_probe --source kernels/cs_probe.metal --sizes 4,8,16,32

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void die(const char *m, NSError *e) {
    fprintf(stderr, "compute_probe: %s%s%s\n", m, e ? ": " : "",
            e ? [[e localizedDescription] UTF8String] : "");
    exit(1);
}

int main(int argc, char **argv) { @autoreleasepool {
    const char *srcp = 0, *sizesArg = "4,8,16,32";
    static struct option L[] = {
        {"source", required_argument, 0, 's'},
        {"sizes",  required_argument, 0, 'z'},
        {0,0,0,0}
    };
    int c;
    while ((c = getopt_long(argc, argv, "", L, 0)) > 0) {
        if (c == 's') srcp = optarg;
        if (c == 'z') sizesArg = optarg;
    }
    if (!srcp) die("need --source", nil);

    NSError *err = nil;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) die("no device", nil);
    id<MTLCommandQueue> q = [dev newCommandQueue];
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp]
                                               encoding:NSUTF8StringEncoding error:&err];
    if (!src) die("read src", err);
    MTLCompileOptions *co = [MTLCompileOptions new];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) die("compile", err);
    id<MTLFunction> fn = [lib newFunctionWithName:@"cs_tgmem_probe"];
    if (!fn) die("function missing", nil);
    id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
    if (!pso) die("pipeline", err);

    // Parse comma-separated threadgroup sizes (== float-element count for buf).
    NSMutableArray<NSNumber *> *sizes = [NSMutableArray array];
    char *dup = strdup(sizesArg), *tok = strtok(dup, ",");
    while (tok) { [sizes addObject:@(atoi(tok))]; tok = strtok(NULL, ","); }
    free(dup);

    printf("[");
    BOOL first = YES;
    for (NSNumber *nn in sizes) {
        int N = [nn intValue];
        id<MTLBuffer> out = [dev newBufferWithLength:(NSUInteger)N * 4 options:MTLResourceStorageModeShared];
        memset(out.contents, 0, (NSUInteger)N * 4);

        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        [enc setBuffer:out offset:0 atIndex:0];
        [enc setThreadgroupMemoryLength:(NSUInteger)N * 4 atIndex:0];
        [enc dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(N,1,1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];

        NSMutableString *rec = [NSMutableString string];
        if (cb.error) {
            [rec appendFormat:@"{\"N\":%d,\"status\":\"FAIL\",\"error\":\"%@\"}", N,
                [[cb.error localizedDescription] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"]];
        } else {
            float *op = (float *)out.contents;
            NSMutableString *vals = [NSMutableString string];
            for (int i = 0; i < N; i++) [vals appendFormat:@"%s%.4f", i?",":"", op[i]];
            [rec appendFormat:@"{\"N\":%d,\"status\":\"OK\",\"out\":[%@]}", N, vals];
        }
        printf("%s%s", first ? "" : ",", [rec UTF8String]);
        first = NO;
    }
    printf("]\n");
    return 0;
}}
