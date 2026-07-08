// iohello_compute.m — minimal OWN Metal compute dispatch for iotrace capture.
//
// Part of EXP-0009 (ROADMAP 0.5). A deliberately tiny compute program we run
// under the iotrace interposer to capture exactly what userspace hands the
// kernel to submit GPU work. It prints the GPU virtual addresses of its OWN
// resources (buffers) and the dispatch dimensions, in both hex and
// little-endian byte form, so we can grep the captured IOKit struct payloads /
// mapped-memory snapshots for them and locate where our work is encoded.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. The kernel is our own MSL,
// compiled at runtime. Nothing here disassembles any Apple binary.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o iohello_compute iohello_compute.m
// Usage:          [--iters N] [--grid G] [--tg T]  (defaults: 1, 64, 32)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *label, uint64_t va) {
    // hex plus the little-endian byte string to grep for in captures.
    unsigned char b[8];
    for (int i = 0; i < 8; i++) b[i] = (va >> (8 * i)) & 0xff;
    printf("VA %-10s = 0x%016llx  le=", label, (unsigned long long)va);
    for (int i = 0; i < 8; i++) printf("%02x", b[i]);
    printf("\n");
}

int main(int argc, char **argv) {
    @autoreleasepool {
        long iters = 1, grid = 64, tg = 32; int doDump = 0;
        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--iters") && i + 1 < argc) iters = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--grid") && i + 1 < argc) grid = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--tg") && i + 1 < argc) tg = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--dump")) doDump = 1;
        }

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("DISPATCH grid=%ld tg=%ld iters=%ld\n", grid, tg, iters);

        // Our own trivial kernel: out[i] = a[i] + b[i].
        NSString *src = @"#include <metal_stdlib>\n"
                         "using namespace metal;\n"
                         "kernel void k(device const float* a [[buffer(0)]],\n"
                         "              device const float* b [[buffer(1)]],\n"
                         "              device float* o       [[buffer(2)]],\n"
                         "              uint i [[thread_position_in_grid]]) {\n"
                         "  o[i] = a[i] + b[i];\n"
                         "}\n";
        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
        if (!lib) { printf("COMPILE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 1; }
        id<MTLFunction> fn = [lib newFunctionWithName:@"k"];
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) { printf("PIPELINE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 1; }

        size_t n = (size_t)grid;
        id<MTLBuffer> ba = [dev newBufferWithLength:n * 4 options:MTLResourceStorageModeShared];
        id<MTLBuffer> bb = [dev newBufferWithLength:n * 4 options:MTLResourceStorageModeShared];
        id<MTLBuffer> bo = [dev newBufferWithLength:n * 4 options:MTLResourceStorageModeShared];
        // Distinctive magic contents (so the buffers themselves are greppable too).
        float *pa = (float *)[ba contents], *pb = (float *)[bb contents];
        for (size_t i = 0; i < n; i++) { pa[i] = 1000.0f + i; pb[i] = 0.5f; }

        print_va("bufA", [ba gpuAddress]);
        print_va("bufB", [bb gpuAddress]);
        print_va("bufOut", [bo gpuAddress]);

        id<MTLCommandQueue> q = [dev newCommandQueue];

        for (long it = 0; it < iters; it++) {
            printf("SUBMIT iter=%ld begin\n", it);
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
            [enc setComputePipelineState:pso];
            [enc setBuffer:ba offset:0 atIndex:0];
            [enc setBuffer:bb offset:0 atIndex:1];
            [enc setBuffer:bo offset:0 atIndex:2];
            [enc dispatchThreads:MTLSizeMake(grid, 1, 1)
          threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            printf("SUBMIT iter=%ld done status=%ld\n", it, (long)[cb status]);
            // On the LAST iter, ask the interposer (if loaded) to snapshot every
            // registered BO now, while the just-built command stream is still in
            // memory. kill() is process-directed so the interposer's dedicated
            // SIGUSR1 thread services it. Harmless no-op if nothing handles it
            // (only sent under --dump, which we pass only with the interposer).
            if (doDump && it == iters - 1) {
                fflush(stdout);
                kill(getpid(), SIGUSR1);
                usleep(400000); // give the dump thread time to finish
            }
        }

        float *po = (float *)[bo contents];
        printf("RESULT o[0]=%.1f o[1]=%.1f (expect 1000.5 1001.5)\n", po[0], po[1]);
        return 0;
    }
}
