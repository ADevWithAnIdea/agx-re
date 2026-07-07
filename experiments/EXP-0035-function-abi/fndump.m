// fndump.m — EXP-0035 clean-room OWN-SHADER compile+serialize for FUNCTION-CALL ABI.
//
// Extends the tools/shdump idea to compute pipelines that LINK visible functions
// (MTLLinkedFunctions) so an indirect call through a visible_function_table is
// actually emitted (plain newComputePipelineStateWithFunction: DCEs the call).
// It also builds a real MTLVisibleFunctionTable and can DISPATCH the kernel so
// the function-pointer path is HW-validated.
//
// CLEAN-ROOM: uses only the PUBLIC Metal API on OUR OWN MSL. Never disassembles
// or introspects any Apple binary; only our own compiled shader bytes are read
// (out-of-band, by our own agxparse.py). Our own independent implementation.
//
// Build (device, Command Line Tools only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o fndump fndump.m
//
// Usage:
//   ./fndump -o out.bin -f kernelName [--visible fn1,fn2,...] source.metal
//   ./fndump -o out.bin -f kernelName --visible vadd,vmul --run \
//            --A a0,a1,.. --B b0,b1,.. --sel s0,s1,.. --n N       (HW dispatch)
// Prints library function names + chosen function to stderr; on --run prints
// RESULT floats read back from buffer(2).

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void die(const char *msg, NSError *err) {
    fprintf(stderr, "fndump: %s%s%s\n", msg, err ? ": " : "",
            err ? [[err localizedDescription] UTF8String] : "");
    exit(EXIT_FAILURE);
}

enum { OPT_VISIBLE = 128, OPT_RUN, OPT_A, OPT_B, OPT_SEL, OPT_N, OPT_NO_FAST_MATH };
static const struct option longOpts[] = {
    {"output",   required_argument, NULL, 'o'},
    {"function", required_argument, NULL, 'f'},
    {"visible",  required_argument, NULL, OPT_VISIBLE},
    {"run",      no_argument,       NULL, OPT_RUN},
    {"A",        required_argument, NULL, OPT_A},
    {"B",        required_argument, NULL, OPT_B},
    {"sel",      required_argument, NULL, OPT_SEL},
    {"n",        required_argument, NULL, OPT_N},
    {"no-fast-math", no_argument,   NULL, OPT_NO_FAST_MATH},
    {NULL, 0, NULL, 0}
};

static NSArray<NSString*> *splitCsv(const char *s) {
    NSMutableArray *a = [NSMutableArray array];
    if (!s) return a;
    for (NSString *p in [[NSString stringWithUTF8String:s] componentsSeparatedByString:@","])
        if ([p length]) [a addObject:p];
    return a;
}
static float *parseFloats(const char *s, NSUInteger *cnt) {
    NSArray *p = splitCsv(s); *cnt = [p count];
    float *v = malloc(sizeof(float) * (*cnt ? *cnt : 1));
    for (NSUInteger i = 0; i < *cnt; i++) v[i] = strtof([p[i] UTF8String], NULL);
    return v;
}
static uint32_t *parseUints(const char *s, NSUInteger *cnt) {
    NSArray *p = splitCsv(s); *cnt = [p count];
    uint32_t *v = malloc(sizeof(uint32_t) * (*cnt ? *cnt : 1));
    for (NSUInteger i = 0; i < *cnt; i++) v[i] = (uint32_t)strtoul([p[i] UTF8String], NULL, 0);
    return v;
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *output = NULL, *want_fn = NULL, *visibleCsv = NULL;
        const char *aCsv = NULL, *bCsv = NULL, *selCsv = NULL;
        BOOL fastMath = YES, doRun = NO;
        NSUInteger n = 0;
        int c;
        while ((c = getopt_long(argc, argv, "o:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'o': output = optarg; break;
                case 'f': want_fn = optarg; break;
                case OPT_VISIBLE: visibleCsv = optarg; break;
                case OPT_RUN: doRun = YES; break;
                case OPT_A: aCsv = optarg; break;
                case OPT_B: bCsv = optarg; break;
                case OPT_SEL: selCsv = optarg; break;
                case OPT_N: n = (NSUInteger)strtoul(optarg, NULL, 0); break;
                case OPT_NO_FAST_MATH: fastMath = NO; break;
                default: die("bad args", nil);
            }
        }
        if (!output || !want_fn || optind >= argc) die("usage: -o out.bin -f fn [--visible a,b] src.metal", nil);

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[optind]]
                                                  encoding:NSUTF8StringEncoding error:&err];
        if (!src) die("read source", err);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) die("no Metal device", nil);
        fprintf(stderr, "fndump: device = %s\n", [[dev name] UTF8String]);

        MTLCompileOptions *opts = [MTLCompileOptions new];
        [opts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) die("compile failed", err);

        fprintf(stderr, "fndump: functions =");
        for (NSString *nm in [lib functionNames]) fprintf(stderr, " %s", [nm UTF8String]);
        fprintf(stderr, "\n");

        id<MTLFunction> kfn = [lib newFunctionWithName:[NSString stringWithUTF8String:want_fn]];
        if (!kfn) die("kernel not found", nil);

        // Collect the visible functions to LINK into the pipeline.
        NSMutableArray<id<MTLFunction>> *vis = [NSMutableArray array];
        for (NSString *vn in splitCsv(visibleCsv)) {
            id<MTLFunction> vf = [lib newFunctionWithName:vn];
            if (!vf) die("visible function not found", nil);
            [vis addObject:vf];
        }

        MTLComputePipelineDescriptor *cdesc = [MTLComputePipelineDescriptor new];
        cdesc.computeFunction = kfn;
        if ([vis count]) {
            MTLLinkedFunctions *lf = [MTLLinkedFunctions new];
            lf.functions = vis;
            cdesc.linkedFunctions = lf;
            fprintf(stderr, "fndump: linked %lu visible function(s)\n", (unsigned long)[vis count]);
        }

        MTLAutoreleasedComputePipelineReflection refl = nil;
        id<MTLComputePipelineState> pso =
            [dev newComputePipelineStateWithDescriptor:cdesc
                                               options:MTLPipelineOptionNone
                                            reflection:&refl error:&err];
        if (!pso) die("compute pipeline creation failed", err);
        fprintf(stderr, "fndump: pipeline OK  tew=%lu maxT=%lu\n",
                (unsigned long)[pso threadExecutionWidth],
                (unsigned long)[pso maxTotalThreadsPerThreadgroup]);

        // Serialize the machine code into an archive for out-of-band extraction.
        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!arc) die("archive creation failed", err);
        if (![arc addComputePipelineFunctionsWithDescriptor:cdesc error:&err])
            die("addComputePipelineFunctions failed", err);
        NSURL *url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:output]];
        if (![arc serializeToURL:url error:&err]) die("serializeToURL failed", err);
        fprintf(stderr, "fndump: wrote %s\n", output);

        if (!doRun) return 0;

        // ---- HW dispatch: build the visible_function_table and run -----------
        id<MTLCommandQueue> q = [dev newCommandQueue];
        NSUInteger na, nb, ns;
        float *A = parseFloats(aCsv, &na);
        float *B = parseFloats(bCsv, &nb);
        uint32_t *SEL = parseUints(selCsv, &ns);
        if (!n) n = na;
        id<MTLBuffer> bA = [dev newBufferWithBytes:A length:sizeof(float)*n options:0];
        id<MTLBuffer> bB = [dev newBufferWithBytes:B length:sizeof(float)*n options:0];
        id<MTLBuffer> bO = [dev newBufferWithLength:sizeof(float)*n options:0];
        id<MTLBuffer> bSel = [dev newBufferWithBytes:SEL length:sizeof(uint32_t)*n options:0];

        // Visible function table sized to the number of linked functions.
        id<MTLVisibleFunctionTable> vft = nil;
        if ([vis count]) {
            MTLVisibleFunctionTableDescriptor *vd = [MTLVisibleFunctionTableDescriptor new];
            vd.functionCount = [vis count];
            vft = [pso newVisibleFunctionTableWithDescriptor:vd];
            for (NSUInteger i = 0; i < [vis count]; i++) {
                id<MTLFunctionHandle> h = [pso functionHandleWithFunction:vis[i]];
                if (!h) die("functionHandleWithFunction returned nil", nil);
                [vft setFunction:h atIndex:i];
            }
        }

        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        [enc setBuffer:bA offset:0 atIndex:0];
        [enc setBuffer:bB offset:0 atIndex:1];
        [enc setBuffer:bO offset:0 atIndex:2];
        if (vft) [enc setVisibleFunctionTable:vft atBufferIndex:3];
        [enc setBuffer:bSel offset:0 atIndex:4];
        [enc dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(n<32?n:32,1,1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if (cb.error) die("dispatch error", cb.error);

        // Trigger the iotrace BO snapshot while every buffer is still mapped
        // (process-directed, serviced on the interposer's sigwait thread).
        // Guarded: only when tracing, else default SIGUSR1 would terminate us.
        if (getenv("FNDUMP_SIGUSR1")) { kill(getpid(), SIGUSR1); usleep(500000); }

        float *O = (float*)[bO contents];
        printf("RESULT");
        for (NSUInteger i = 0; i < n; i++) printf(" %g", O[i]);
        printf("\nSTATUS OK\n");
        return 0;
    }
}
