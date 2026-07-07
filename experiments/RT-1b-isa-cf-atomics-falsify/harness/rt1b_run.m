// rt1b_run.m -- RT-1b INDEPENDENT one-shot AGX runner (red-team 2nd pass).
//
// This is a DIFFERENT harness from RT-1a / RT-1a-FIX, which used the PERSISTENT
// runner (agxrun_persist, one long-lived MTLDevice, newLibraryWithURL reload).
// This runner is deliberately ONE-SHOT: a FRESH MTLDevice per process, so there
// is no in-process code memoization to reason about at all -- each spliced
// archive is the only code this process ever sees. If RT-1a's persistent-reload
// mechanism had a subtle memoization bug, this harness would disagree. It is my
// own independent implementation (structurally akin to the public MIT applegpu
// hwtestbed, and to tools/agxtest/agxrun.m, but written from scratch here).
//
// CLEAN-ROOM: OWN-SHADER. It loads a Metal binary archive we built from OUR OWN
// MSL (possibly with bytes we spliced), forces pipeline creation from the
// archived machine code (MTLPipelineOptionFailOnBinaryArchiveMiss), dispatches,
// reads back buffers. No Apple binary is ever disassembled or introspected.
//
// Build (device, CLT only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o rt1b_run rt1b_run.m
//
// Usage:
//   rt1b_run --archive A.bin --function k --grid N --tg T \
//            [--in IDX:FILE ...] [--out IDX:NBYTES ...] [--tgmem IDX:NBYTES ...]
// Output:
//   STATUS OK|COMPILE_FAIL|FUNCTION_MISSING|ARCHIVE_FAIL|PIPELINE_MISS|CMDBUF_ERROR
//   [GPUTIME_NS n]
//   [OUT idx hex ...]
//   [ERROR msg]

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

enum { OPT_IN = 128, OPT_OUT, OPT_TGMEM };
static const struct option longOpts[] = {
    {"archive",  required_argument, NULL, 'a'},
    {"function", required_argument, NULL, 'f'},
    {"grid",     required_argument, NULL, 'g'},
    {"tg",       required_argument, NULL, 't'},
    {"in",       required_argument, NULL, OPT_IN},
    {"out",      required_argument, NULL, OPT_OUT},
    {"tgmem",    required_argument, NULL, OPT_TGMEM},
    {NULL, 0, NULL, 0}
};

static void fail(const char *status, const char *msg, NSError *err) {
    printf("STATUS %s\n", status);
    if (err) printf("ERROR %s: %s\n", msg ? msg : "", [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    fflush(stdout);
    exit(1);
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *archive = NULL, *func = "k";
        long grid = 1, tg = 1;
        int inIdx[64], outIdx[64], tgIdx[64];
        char *inFile[64];
        long outSz[64], tgSz[64];
        int nin = 0, nout = 0, ntg = 0;

        int c;
        while ((c = getopt_long(argc, argv, "a:f:g:t:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'a': archive = optarg; break;
                case 'f': func = optarg; break;
                case 'g': grid = strtol(optarg, NULL, 0); break;
                case 't': tg = strtol(optarg, NULL, 0); break;
                case OPT_IN: {
                    char *colon = strchr(optarg, ':');
                    if (!colon) fail("BAD_REQUEST", "in want IDX:FILE", nil);
                    *colon = 0; inIdx[nin] = (int)strtol(optarg, NULL, 0);
                    inFile[nin] = strdup(colon + 1); nin++;
                    break; }
                case OPT_OUT: {
                    char *colon = strchr(optarg, ':');
                    if (!colon) fail("BAD_REQUEST", "out want IDX:NBYTES", nil);
                    *colon = 0; outIdx[nout] = (int)strtol(optarg, NULL, 0);
                    outSz[nout] = strtol(colon + 1, NULL, 0); nout++;
                    break; }
                case OPT_TGMEM: {
                    char *colon = strchr(optarg, ':');
                    if (!colon) fail("BAD_REQUEST", "tgmem want IDX:NBYTES", nil);
                    *colon = 0; tgIdx[ntg] = (int)strtol(optarg, NULL, 0);
                    tgSz[ntg] = strtol(colon + 1, NULL, 0); ntg++;
                    break; }
            }
        }
        if (!archive) fail("BAD_REQUEST", "need --archive", nil);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("NO_DEVICE", "MTLCreateSystemDefaultDevice", nil);
        id<MTLCommandQueue> q = [dev newCommandQueue];

        NSError *err = nil;
        NSURL *url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:archive]];
        // Load the library straight from the (possibly spliced) archive bytes.
        id<MTLLibrary> lib = [dev newLibraryWithURL:url error:&err];
        if (!lib) fail("COMPILE_FAIL", "newLibraryWithURL", err);
        id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:func]];
        if (!fn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

        MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
        [ad setUrl:url];
        id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:ad error:&err];
        if (!arc) fail("ARCHIVE_FAIL", "newBinaryArchive", err);

        MTLComputePipelineDescriptor *pd = [MTLComputePipelineDescriptor new];
        [pd setComputeFunction:fn];
        [pd setBinaryArchives:@[arc]];
        id<MTLComputePipelineState> pso =
            [dev newComputePipelineStateWithDescriptor:pd
                                               options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                            reflection:nil error:&err];
        if (!pso) fail("PIPELINE_MISS", "FailOnBinaryArchiveMiss (archived code did not run)", err);

        id<MTLBuffer> bufs[64] = {0};
        for (int i = 0; i < nin; i++) {
            NSData *d = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:inFile[i]]];
            if (!d) fail("BAD_REQUEST", "cannot read input file", nil);
            bufs[inIdx[i]] = [dev newBufferWithBytes:[d bytes] length:[d length]
                                             options:MTLResourceStorageModeShared];
        }
        for (int i = 0; i < nout; i++) {
            if (!bufs[outIdx[i]])
                bufs[outIdx[i]] = [dev newBufferWithLength:outSz[i]
                                                   options:MTLResourceStorageModeShared];
        }

        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        for (int i = 0; i < 64; i++) if (bufs[i]) [enc setBuffer:bufs[i] offset:0 atIndex:i];
        for (int i = 0; i < ntg; i++) [enc setThreadgroupMemoryLength:tgSz[i] atIndex:tgIdx[i]];
        [enc dispatchThreads:MTLSizeMake(grid, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];

        if ([cb status] == MTLCommandBufferStatusError)
            fail("CMDBUF_ERROR", "command buffer failed", [cb error]);

        printf("STATUS OK\n");
        printf("GPUTIME_NS %llu\n",
               (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));
        static const char H[] = "0123456789abcdef";
        for (int i = 0; i < nout; i++) {
            const unsigned char *p = (const unsigned char *)[bufs[outIdx[i]] contents];
            long n = outSz[i];
            char *hex = (char *)malloc(n * 2 + 1);
            for (long j = 0; j < n; j++) { hex[j*2] = H[p[j] >> 4]; hex[j*2+1] = H[p[j] & 0xf]; }
            hex[n*2] = 0;
            printf("OUT %d %s\n", outIdx[i], hex);
            free(hex);
        }
        fflush(stdout);
        return 0;
    }
}
