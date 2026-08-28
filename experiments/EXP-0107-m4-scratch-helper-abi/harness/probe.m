// EXP-0107 OWN-SHADER live CS/VS/FS scratch-pressure probe, public Metal APIs only.
//
// Differs from EXP-0041's harness/probe.m in two respects, both driven by
// this experiment's much higher pressure range (K up to 49152 elements,
// declared scratch up to ~197 KiB/thread) and occupancy range (up to
// 1,048,576 dispatched threads):
//   1. The compute-stage input buffer is a FIXED 4096 floats (16 KiB),
//      independent of K and grid -- kernels/generate.py's kernels index it
//      modulo 4096, so a naive grid*K-sized input allocation (which would
//      reach tens of GiB at this experiment's high end) is never needed.
//   2. `--n` selects the runtime pass count (default 1 = degenerate
//      init+reduce correctness check, matching EXP-0020/EXP-0041; >1 drives
//      genuine repeated spill/fill traffic for the "hot" cases).
// Every outcome (compile reject, pipeline-creation reject, non-finite
// output, non-completed command buffer) is reported on stdout as a
// `STATUS <KIND>` line and a nonzero exit, rather than a hard abort, so a
// fault at the top of an escalation ladder is a captured result, not a
// silent process death indistinguishable from a timeout.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define INPUT_WORDS 4096u

static void report(const char *kind, const char *what, NSError *err) {
    printf("STATUS %s\n", kind);
    if (what) printf("DETAIL %s\n", what);
    if (err) printf("ERROR %s\n", [[[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" "] UTF8String]);
}

static void noop_handler(int sig) { (void)sig; }

int main(int argc, char **argv) {
    // SIGUSR1 is used only to signal harness/maptrace.c's interposer (when
    // DYLD-loaded) to snapshot mapped BOs while they are still valid; its
    // constructor blocks SIGUSR1 on this (the only, at that point) thread
    // and services it on a dedicated sigwait() thread. A real (no-op)
    // handler is installed -- NOT SIG_IGN -- because POSIX lets an
    // implementation discard a SIG_IGN'd signal at generation time even
    // while blocked, which would make it un-sigwait-able; a handler is
    // never invoked for a signal that stays blocked in every thread, so
    // this is inert when maptrace is loaded and only prevents the default
    // terminate action (which would drop buffered stdout) when this probe
    // is run standalone without it.
    struct sigaction sa = {0}; sa.sa_handler = noop_handler; sigaction(SIGUSR1, &sa, NULL);
    @autoreleasepool {
        const char *stage = NULL, *path = NULL;
        unsigned k = 0, requestedGrid = 64, requestedTg = 32, passN = 1;
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--stage") && i + 1 < argc) stage = argv[++i];
            else if (!strcmp(argv[i], "--source") && i + 1 < argc) path = argv[++i];
            else if (!strcmp(argv[i], "--k") && i + 1 < argc) k = (unsigned)strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--grid") && i + 1 < argc) requestedGrid = (unsigned)strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--tg") && i + 1 < argc) requestedTg = (unsigned)strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--n") && i + 1 < argc) passN = (unsigned)strtoul(argv[++i], 0, 0);
        }
        if (!stage || !path || !k) {
            fprintf(stderr, "usage: probe --stage cs|vs|fs --source x.metal --k K [--grid G --tg T --n N]\n");
            printf("STATUS USAGE_ERROR\n");
            return 2;
        }
        // Defense-in-depth safety caps, independent of the case matrix's own
        // pre-registered limits: reject anything that would allocate an
        // unreasonably large *host*-side buffer regardless of what the
        // shader itself declares.
        if ((unsigned long long)requestedGrid * requestedTg > 0) { /* no-op: dispatchThreads grid is absolute thread count */ }
        if (requestedGrid > 4194304u) { printf("STATUS REFUSED_GRID_TOO_LARGE\n"); return 3; }

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:path]
                                                   encoding:NSUTF8StringEncoding error:&err];
        if (!src) { report("SOURCE_READ_FAIL", path, err); return 1; }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s STAGE %s K %u GRID %u TG %u N %u\n",
               [[dev name] UTF8String], stage, k, requestedGrid, requestedTg, passN);
        MTLCompileOptions *opts = [MTLCompileOptions new];
        opts.fastMathEnabled = NO;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) { report("COMPILE_FAIL", "newLibraryWithSource", err); return 1; }
        id<MTLCommandQueue> q = [dev newCommandQueue];
        uint32_t n = passN;
        if (!strcmp(stage, "cs")) {
            id<MTLFunction> fn = [lib newFunctionWithName:@"k_main"];
            id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
            if (!pso) { report("PIPELINE_FAIL", "newComputePipelineStateWithFunction", err); return 1; }
            const unsigned grid = requestedGrid;
            id<MTLBuffer> out = [dev newBufferWithLength:(NSUInteger)grid * sizeof(float) options:MTLResourceStorageModeShared];
            id<MTLBuffer> in = [dev newBufferWithLength:INPUT_WORDS * sizeof(float) options:MTLResourceStorageModeShared];
            if (!out || !in) { report("BUFFER_ALLOC_FAIL", "compute in/out", nil); return 1; }
            float *ip = in.contents;
            for (unsigned i = 0; i < INPUT_WORDS; ++i) ip[i] = (float)((i % 251) + 1) * 0.001f;
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
            [ce setComputePipelineState:pso];
            [ce setBuffer:out offset:0 atIndex:0];
            [ce setBuffer:in offset:0 atIndex:1];
            [ce setBytes:&n length:sizeof(n) atIndex:2];
            [ce dispatchThreads:MTLSizeMake(grid, 1, 1) threadsPerThreadgroup:MTLSizeMake(requestedTg, 1, 1)];
            [ce endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            if (cb.status != MTLCommandBufferStatusCompleted) { report("EXEC_FAIL", "compute", cb.error); return 1; }
            double sum = 0; int nonfinite = 0; float *op = out.contents;
            for (unsigned i = 0; i < grid; ++i) { if (!isfinite(op[i])) nonfinite++; else sum += op[i]; }
            if (nonfinite) { printf("STATUS NONFINITE_OUTPUT\nDETAIL nonfinite_count=%d of %u\n", nonfinite, grid); return 1; }
            printf("STATUS OK\n");
            printf("RESULT checksum=%.9g\n", sum);
        } else {
            id<MTLFunction> vf = [lib newFunctionWithName:@"v_main"];
            id<MTLFunction> ff = [lib newFunctionWithName:@"f_main"];
            MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
            pd.vertexFunction = vf; pd.fragmentFunction = ff;
            pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
            id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
            if (!pso) { report("PIPELINE_FAIL", "newRenderPipelineStateWithDescriptor", err); return 1; }
            const unsigned width = 8, height = 8;
            id<MTLBuffer> in = [dev newBufferWithLength:INPUT_WORDS * sizeof(float) options:MTLResourceStorageModeShared];
            if (!in) { report("BUFFER_ALLOC_FAIL", "render in", nil); return 1; }
            float *ip = in.contents;
            for (unsigned i = 0; i < INPUT_WORDS; ++i) ip[i] = (float)((i % 251) + 1) * 0.001f;
            NSUInteger bpr = 256;
            id<MTLBuffer> rt = [dev newBufferWithLength:bpr * height options:MTLResourceStorageModeShared];
            MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:width height:height mipmapped:NO];
            td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
            id<MTLTexture> tex = [rt newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
            rp.colorAttachments[0].texture = tex; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
            rp.colorAttachments[0].storeAction = MTLStoreActionStore; rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
            [re setRenderPipelineState:pso];
            if (!strcmp(stage, "vs")) { [re setVertexBuffer:in offset:0 atIndex:0]; [re setVertexBytes:&n length:sizeof(n) atIndex:1]; }
            else { [re setFragmentBuffer:in offset:0 atIndex:0]; [re setFragmentBytes:&n length:sizeof(n) atIndex:1]; }
            [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [re endEncoding]; [cb commit]; [cb waitUntilCompleted];
            if (cb.status != MTLCommandBufferStatusCompleted) { report("EXEC_FAIL", "render", cb.error); return 1; }
            unsigned long checksum = 0; unsigned char *p = rt.contents;
            for (unsigned y = 0; y < height; ++y) for (unsigned x = 0; x < width * 4; ++x) checksum += p[y * bpr + x];
            printf("STATUS OK\n");
            printf("RESULT checksum=%lu\n", checksum);
        }
        fflush(stdout);
        kill(getpid(), SIGUSR1); usleep(750000);
    }
    return 0;
}
