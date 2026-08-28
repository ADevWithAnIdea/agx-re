// containerdispatch.m -- EXP-0110 P0.7: dispatch an authored MSL kernel
// (arbitrary source file + function name, buffer count told via --nbuf so
// the harness can bind exactly that many owned buffers at buffer(0..N-1))
// under the read-only tools/iotrace interposer, to test whether specific
// __GPU_METADATA field VALUES (surveyed separately by analysis/metadata.py
// from the same compiled archive) reappear verbatim in the LIVE CDM launch
// record / compute-preamble BO -- the firmware-consumed vs Metal-archive-
// bookkeeping distinction the P0.7 row requires.
//
// CLEAN ROOM: public Metal API + OWN-SHADER only (the .metal source is
// authored by kernels/gen_container_kernels.py). No Apple binary is
// inspected.
//
// Build:
//   xcrun clang -fobjc-arc -Wno-deprecated-declarations -o containerdispatch \
//       containerdispatch.m -framework Metal -framework Foundation

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void request_dump(useconds_t wait_us)
{
    fflush(stdout);
    kill(getpid(), SIGUSR1);
    usleep(wait_us);
}

int main(int argc, char **argv)
{
    @autoreleasepool {
        const char *source_path = NULL, *function_name = NULL;
        long nbuf = 0;
        useconds_t dump_wait_us = 800000;
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--source") && i + 1 < argc) source_path = argv[++i];
            else if (!strcmp(argv[i], "--function") && i + 1 < argc) function_name = argv[++i];
            else if (!strcmp(argv[i], "--nbuf") && i + 1 < argc) nbuf = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--dump-wait-us") && i + 1 < argc) dump_wait_us = (useconds_t)strtoul(argv[++i], NULL, 0);
            else { fprintf(stderr, "usage: %s --source PATH --function NAME --nbuf N [--dump-wait-us N]\n", argv[0]); return 2; }
        }
        if (!source_path || !function_name || nbuf < 0) { fprintf(stderr, "missing required args\n"); return 2; }

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:source_path]
                                                    encoding:NSUTF8StringEncoding error:&err];
        if (!src) { fprintf(stderr, "read source failed: %s\n", err ? [[err localizedDescription] UTF8String] : "?"); return 1; }

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "no Metal device\n"); return 1; }
        printf("DEVICE %s\n", [[dev name] UTF8String]);

        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
        if (!lib) { fprintf(stderr, "compile failed: %s\n", err ? [[err localizedDescription] UTF8String] : "?"); return 1; }
        id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:function_name]];
        if (!fn) { fprintf(stderr, "function not found: %s\n", function_name); return 1; }
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) { fprintf(stderr, "pipeline creation failed: %s\n", err ? [[err localizedDescription] UTF8String] : "?"); return 1; }

        NSMutableArray *buffers = [NSMutableArray array];
        for (long i = 0; i < nbuf; ++i) {
            id<MTLBuffer> b = [dev newBufferWithLength:64 * sizeof(float) options:MTLResourceStorageModeShared];
            float *p = (float *)b.contents;
            for (int j = 0; j < 64; ++j) p[j] = 1.0f + (float)i;
            [buffers addObject:b];
            printf("VA buf[%ld] = 0x%016llx\n", i, (unsigned long long)b.gpuAddress);
        }

        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        for (long i = 0; i < nbuf; ++i)
            [enc setBuffer:buffers[i] offset:0 atIndex:(NSUInteger)i];
        [enc dispatchThreads:MTLSizeMake(64, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        printf("COMPLETE status=%ld error=%s\n", (long)cb.status,
               cb.error ? [[cb.error localizedDescription] UTF8String] : "NONE");
        if (nbuf > 0) {
            float *p = (float *)((id<MTLBuffer>)buffers[0]).contents;
            printf("READBACK buf0[0]=%f\n", p[0]);
        }
        request_dump(dump_wait_us);
        printf("VERDICT completed=%d\n", cb.status == MTLCommandBufferStatusCompleted ? 1 : 0);
        return cb.status == MTLCommandBufferStatusCompleted ? 0 : 1;
    }
}
