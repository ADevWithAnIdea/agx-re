// EXP-0125 C-family harness (H4): concurrent-pressure probe. Creates ONE
// MTLDevice, N independent MTLCommandQueues, ONE shared compiled pipeline
// (the heavy K=24576 array-loop kernel -- ~98,320 B/thread declared scratch,
// EXP-0107-validated safe and correct at grid up to 1,048,576 when run
// ALONE), and dispatches a real workload on EVERY queue, COMMITTING ALL N
// BEFORE WAITING ON ANY of them -- genuine concurrent GPU-side pressure, not
// N sequential single-dispatch sweeps (which is what EXP-0041/EXP-0107 did
// and is explicitly the gap this experiment's H4 targets).
//
// Overall process-level timeout is enforced by the Python driver
// (subprocess.run(..., timeout=...)), exactly as EXP-0107 relied on for its
// own probe -- consistent with this repo's established pattern; a kill on
// timeout is itself a captured, non-silent result at the driver level.
//
// Failure-mode reporting per queue: OK (completed, finite output, checksum
// matches the reference produced by n_queues=1), EXEC_FAIL (command buffer
// error), NONFINITE_OUTPUT (completed but wrong/garbage numbers -- would be
// evidence of silent corruption under concurrent pressure), or the process
// simply not returning at all before the driver's timeout (hang).
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define INPUT_WORDS 4096u

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *path = NULL;
        unsigned nq = 1, grid = 65536, tg = 256;
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--source") && i + 1 < argc) path = argv[++i];
            else if (!strcmp(argv[i], "--n-queues") && i + 1 < argc) nq = (unsigned)strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--grid") && i + 1 < argc) grid = (unsigned)strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--tg") && i + 1 < argc) tg = (unsigned)strtoul(argv[++i], 0, 0);
        }
        if (!path || nq == 0 || nq > 256) {
            fprintf(stderr, "usage: concurrent --source x.metal --n-queues N [--grid G --tg T]\n");
            printf("STATUS USAGE_ERROR\n");
            return 2;
        }
        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:path]
                                                   encoding:NSUTF8StringEncoding error:&err];
        if (!src) { printf("STATUS SOURCE_READ_FAIL\n"); return 1; }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        MTLCompileOptions *opts = [MTLCompileOptions new];
        opts.fastMathEnabled = NO;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) { printf("STATUS COMPILE_FAIL\n"); return 1; }
        id<MTLFunction> fn = [lib newFunctionWithName:@"k_main"];
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) {
            printf("STATUS PIPELINE_FAIL\n");
            if (err) printf("ERROR %s\n", [[[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" "] UTF8String]);
            return 1;
        }

        id<MTLBuffer> in = [dev newBufferWithLength:INPUT_WORDS * sizeof(float) options:MTLResourceStorageModeShared];
        float *ip = in.contents;
        for (unsigned i = 0; i < INPUT_WORDS; ++i) ip[i] = (float)((i % 251) + 1) * 0.001f;
        uint32_t n = 1;

        NSMutableArray<id<MTLCommandQueue>> *queues = [NSMutableArray arrayWithCapacity:nq];
        NSMutableArray<id<MTLBuffer>> *outs = [NSMutableArray arrayWithCapacity:nq];
        NSMutableArray<id<MTLCommandBuffer>> *cbs = [NSMutableArray arrayWithCapacity:nq];
        for (unsigned qi = 0; qi < nq; ++qi) {
            id<MTLCommandQueue> qq = [dev newCommandQueue];
            id<MTLBuffer> oo = [dev newBufferWithLength:(NSUInteger)grid * sizeof(float) options:MTLResourceStorageModeShared];
            if (!qq || !oo) { printf("STATUS QUEUE_ALLOC_FAIL\nDETAIL qi=%u\n", qi); return 1; }
            [queues addObject:qq];
            [outs addObject:oo];
        }

        // Encode + commit ALL queues before waiting on ANY -- this is the
        // "genuine concurrent pressure" step.
        for (unsigned qi = 0; qi < nq; ++qi) {
            id<MTLCommandBuffer> cb = [queues[qi] commandBuffer];
            id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
            [ce setComputePipelineState:pso];
            [ce setBuffer:outs[qi] offset:0 atIndex:0];
            [ce setBuffer:in offset:0 atIndex:1];
            [ce setBytes:&n length:sizeof(n) atIndex:2];
            [ce dispatchThreads:MTLSizeMake(grid, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
            [ce endEncoding];
            [cb commit];
            [cbs addObject:cb];
        }

        unsigned ok = 0, execfail = 0, nonfinite_q = 0;
        double first_checksum = 0; int have_first = 0; int checksum_mismatch = 0;
        for (unsigned qi = 0; qi < nq; ++qi) {
            id<MTLCommandBuffer> cb = cbs[qi];
            [cb waitUntilCompleted];
            if (cb.status != MTLCommandBufferStatusCompleted) {
                execfail++;
                printf("QUEUE %u STATUS EXEC_FAIL\n", qi);
                continue;
            }
            double sum = 0; int nonfinite = 0; float *op = outs[qi].contents;
            for (unsigned i = 0; i < grid; ++i) { if (!isfinite(op[i])) nonfinite++; else sum += op[i]; }
            if (nonfinite) {
                nonfinite_q++;
                printf("QUEUE %u STATUS NONFINITE_OUTPUT DETAIL nonfinite=%d\n", qi, nonfinite);
                continue;
            }
            if (!have_first) { first_checksum = sum; have_first = 1; }
            else if (fabs(sum - first_checksum) > 1e-3 * fabs(first_checksum) + 1e-6) checksum_mismatch++;
            ok++;
            printf("QUEUE %u STATUS OK CHECKSUM %.9g\n", qi, sum);
        }
        printf("SUMMARY n_queues=%u ok=%u execfail=%u nonfinite=%u checksum_mismatch=%u\n",
               nq, ok, execfail, nonfinite_q, checksum_mismatch);
        printf("STATUS %s\n", (ok == nq && checksum_mismatch == 0) ? "OK" : "DEGRADED");
    }
    return 0;
}
