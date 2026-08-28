// EXP-0125 B-family harness (H3): fast compile-time-ceiling probe. Builds a
// pipeline from a caller-supplied .metal source and reports whether pipeline
// creation succeeds -- NO dispatch, since EXP-0107 Sec.4 already established
// the ceiling is purely a compile-time property (checked before any grid/
// threadgroup parameter is even specified), so skipping dispatch is a valid
// speedup for bisection, not a scope change. One process per trial (bisect.py
// drives this repeatedly with different --source files), each trial an
// independently timed, independently logged case -- never batched in one
// long-lived process, so a hang in one trial cannot corrupt the next.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *stage = NULL, *path = NULL;
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--stage") && i + 1 < argc) stage = argv[++i];
            else if (!strcmp(argv[i], "--source") && i + 1 < argc) path = argv[++i];
        }
        if (!stage || !path) {
            fprintf(stderr, "usage: ceiling --stage cs|vs|fs --source x.metal\n");
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
        if (!lib) {
            printf("STATUS COMPILE_FAIL\n");
            if (err) printf("ERROR %s\n", [[[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" "] UTF8String]);
            return 1;
        }
        if (!strcmp(stage, "cs")) {
            id<MTLFunction> fn = [lib newFunctionWithName:@"k_main"];
            id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
            if (!pso) {
                printf("STATUS PIPELINE_FAIL\n");
                if (err) printf("ERROR %s\n", [[[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" "] UTF8String]);
                return 1;
            }
        } else {
            id<MTLFunction> vf = [lib newFunctionWithName:@"v_main"];
            id<MTLFunction> ff = [lib newFunctionWithName:@"f_main"];
            MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
            pd.vertexFunction = vf; pd.fragmentFunction = ff;
            pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
            id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
            if (!pso) {
                printf("STATUS PIPELINE_FAIL\n");
                if (err) printf("ERROR %s\n", [[[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" "] UTF8String]);
                return 1;
            }
        }
        printf("STATUS OK\n");
    }
    return 0;
}
