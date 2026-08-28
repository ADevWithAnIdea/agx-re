// EXP-0125 I-family harness (H1/H2): walks the device/queue/pipeline
// lifecycle with a SIGUSR1 checkpoint sent at each stage, so harness/
// inittrace.c (when DYLD-loaded) can snapshot the full BO inventory BEFORE
// any spilling work exists, not just after (contrast with EXP-0041/EXP-0107,
// which only ever snapshotted once, after the pressure dispatch completed).
//
// Two variants, matched step-for-step so only the presence/absence of real
// scratch demand differs:
//   --variant nospill : both pipelines created are the TRIVIAL (K=0, no
//                        `thread` array, provably non-spilling) kernel; the
//                        dispatch runs the trivial kernel.
//   --variant spill    : the SECOND pipeline is the K=24576 array-loop
//                        kernel (~98,320 B declared per-thread scratch,
//                        EXP-0107-validated as cleanly spilling and safe at
//                        this grid); the dispatch runs it for real, with a
//                        grid large enough to guarantee genuine concurrent
//                        occupancy pressure.
//
// Checkpoints (both variants send exactly these six, in this order):
//   0 DEVICE_CREATED        -- right after MTLCreateSystemDefaultDevice
//   1 QUEUE_CREATED         -- right after newCommandQueue
//   2 PIPELINE1_CREATED     -- right after the FIRST (always trivial) pipeline
//   3 PIPELINE2_CREATED     -- right after the SECOND (variant-dependent) pipeline
//   4 PRE_DISPATCH          -- right before [commandBuffer commit]
//   5 POST_DISPATCH         -- right after waitUntilCompleted
//
// This harness itself writes checkpoints.jsonl (index, label, mach_time),
// append+fflush'd immediately after each checkpoint is sent -- the
// authoritative index->label mapping analysis/*.py joins against
// inittrace.c's own CHECKPOINT log lines by ordinal position.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <mach/mach_time.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define INPUT_WORDS 4096u

static FILE *cplog;

static void checkpoint(int idx, const char *label) {
    uint64_t mt = mach_absolute_time();
    fprintf(cplog, "{\"idx\":%d,\"label\":\"%s\",\"mach_time\":%llu}\n", idx, label, (unsigned long long)mt);
    fflush(cplog);
    kill(getpid(), SIGUSR1);
    usleep(400000); // let inittrace.c's signal thread finish its dump before we proceed
}

static void noop_handler(int sig) { (void)sig; }

int main(int argc, char **argv) {
    struct sigaction sa = {0}; sa.sa_handler = noop_handler; sigaction(SIGUSR1, &sa, NULL);
    @autoreleasepool {
        const char *variant = NULL, *trivial_path = NULL, *spill_path = NULL, *cplog_path = NULL;
        unsigned grid = 65536, tg = 256, k = 24576;
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--variant") && i + 1 < argc) variant = argv[++i];
            else if (!strcmp(argv[i], "--trivial") && i + 1 < argc) trivial_path = argv[++i];
            else if (!strcmp(argv[i], "--spill") && i + 1 < argc) spill_path = argv[++i];
            else if (!strcmp(argv[i], "--checkpoints-log") && i + 1 < argc) cplog_path = argv[++i];
            else if (!strcmp(argv[i], "--grid") && i + 1 < argc) grid = (unsigned)strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--tg") && i + 1 < argc) tg = (unsigned)strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--k") && i + 1 < argc) k = (unsigned)strtoul(argv[++i], 0, 0);
        }
        if (!variant || !trivial_path || !cplog_path || (!strcmp(variant, "spill") && !spill_path)) {
            fprintf(stderr, "usage: initprobe --variant nospill|spill --trivial x.metal "
                    "[--spill y.metal --k K] --checkpoints-log path.jsonl [--grid G --tg T]\n");
            printf("STATUS USAGE_ERROR\n");
            return 2;
        }
        cplog = fopen(cplog_path, "w");
        if (!cplog) { printf("STATUS LOG_OPEN_FAIL\n"); return 1; }

        NSError *err = nil;
        NSString *trivialSrc = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:trivial_path]
                                                          encoding:NSUTF8StringEncoding error:&err];
        if (!trivialSrc) { printf("STATUS SOURCE_READ_FAIL\nDETAIL trivial\n"); return 1; }
        NSString *spillSrc = nil;
        if (spill_path) {
            spillSrc = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:spill_path]
                                                  encoding:NSUTF8StringEncoding error:&err];
            if (!spillSrc) { printf("STATUS SOURCE_READ_FAIL\nDETAIL spill\n"); return 1; }
        }

        // --- checkpoint 0: device ---
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { printf("STATUS NO_DEVICE\n"); return 1; }
        checkpoint(0, "DEVICE_CREATED");

        // --- checkpoint 1: queue ---
        id<MTLCommandQueue> q = [dev newCommandQueue];
        if (!q) { printf("STATUS QUEUE_FAIL\n"); return 1; }
        checkpoint(1, "QUEUE_CREATED");

        MTLCompileOptions *opts = [MTLCompileOptions new];
        opts.fastMathEnabled = NO;

        // --- checkpoint 2: first (always trivial) pipeline ---
        id<MTLLibrary> lib1 = [dev newLibraryWithSource:trivialSrc options:opts error:&err];
        if (!lib1) { printf("STATUS COMPILE_FAIL\nDETAIL pipeline1\n"); return 1; }
        id<MTLFunction> fn1 = [lib1 newFunctionWithName:@"k_main"];
        id<MTLComputePipelineState> pso1 = [dev newComputePipelineStateWithFunction:fn1 error:&err];
        if (!pso1) { printf("STATUS PIPELINE_FAIL\nDETAIL pipeline1\n"); return 1; }
        checkpoint(2, "PIPELINE1_CREATED");

        // --- checkpoint 3: second (variant-dependent) pipeline ---
        NSString *src2 = (!strcmp(variant, "spill")) ? spillSrc : trivialSrc;
        id<MTLLibrary> lib2 = [dev newLibraryWithSource:src2 options:opts error:&err];
        if (!lib2) { printf("STATUS COMPILE_FAIL\nDETAIL pipeline2\n"); return 1; }
        id<MTLFunction> fn2 = [lib2 newFunctionWithName:@"k_main"];
        id<MTLComputePipelineState> pso2 = [dev newComputePipelineStateWithFunction:fn2 error:&err];
        if (!pso2) { printf("STATUS PIPELINE_FAIL\nDETAIL pipeline2\n"); return 1; }
        checkpoint(3, "PIPELINE2_CREATED");

        // --- dispatch pso2 for real (both variants dispatch; only the
        // kernel differs) ---
        id<MTLBuffer> out = [dev newBufferWithLength:(NSUInteger)grid * sizeof(float) options:MTLResourceStorageModeShared];
        id<MTLBuffer> in = [dev newBufferWithLength:INPUT_WORDS * sizeof(float) options:MTLResourceStorageModeShared];
        if (!out || !in) { printf("STATUS BUFFER_ALLOC_FAIL\n"); return 1; }
        float *ip = in.contents;
        for (unsigned i = 0; i < INPUT_WORDS; ++i) ip[i] = (float)((i % 251) + 1) * 0.001f;
        uint32_t n = 1;
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
        [ce setComputePipelineState:pso2];
        [ce setBuffer:out offset:0 atIndex:0];
        [ce setBuffer:in offset:0 atIndex:1];
        [ce setBytes:&n length:sizeof(n) atIndex:2];
        [ce dispatchThreads:MTLSizeMake(grid, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [ce endEncoding];

        // --- checkpoint 4: immediately before commit ---
        checkpoint(4, "PRE_DISPATCH");

        [cb commit];
        [cb waitUntilCompleted];

        // --- checkpoint 5: after completion ---
        checkpoint(5, "POST_DISPATCH");

        if (cb.status != MTLCommandBufferStatusCompleted) {
            printf("STATUS EXEC_FAIL\n");
            if (cb.error) printf("ERROR %s\n", [[[cb.error localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" "] UTF8String]);
            fclose(cplog);
            return 1;
        }
        double sum = 0; int nonfinite = 0; float *op = out.contents;
        for (unsigned i = 0; i < grid; ++i) { if (!isfinite(op[i])) nonfinite++; else sum += op[i]; }
        printf("STATUS %s\n", nonfinite ? "NONFINITE_OUTPUT" : "OK");
        printf("RESULT checksum=%.9g nonfinite=%d\n", sum, nonfinite);
        fclose(cplog);
    }
    return 0;
}
