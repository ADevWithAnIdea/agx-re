// agxrun.m — clean-room OWN-SHADER hardware round-trip runner (EXP-0003).
//
// Part of the A18 Pro GPU clean-room RE project. Takes a serialized Metal
// binary archive (which we produced from OUR OWN MSL, and may have byte-spliced
// out-of-band) plus the MSL source that defines the function's identity, forces
// Metal to instantiate the compute pipeline FROM THE ARCHIVE'S PRECOMPILED
// MACHINE CODE (MTLPipelineOptionFailOnBinaryArchiveMiss), dispatches it with
// caller-supplied input buffers, and dumps the output buffers.
//
// This is the "run" half of the assemble->run->observe testbed: it lets us take
// a (possibly hand-modified) _agc.main byte sequence, make it runnable on the
// real GPU, and read back what the silicon computed.
//
// CLEAN-ROOM: uses only the *public* Metal API, on OUR OWN compiled shader (the
// binary archive was built by shdump from our own MSL). It never disassembles or
// introspects any Apple binary. The technique (splice a binary archive, load it
// back with FailOnBinaryArchiveMiss) is the one used by the public MIT applegpu
// hwtestbed; this is our own independent implementation.
//
// Build (device, Command Line Tools only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o agxrun agxrun.m
//
// Usage:
//   agxrun --archive ARCH.bin --source SRC.metal --function NAME \
//          [--no-fast-math] --grid N --tg T \
//          --buf IDX=FILE ...        (input buffer, raw bytes from FILE)
//          --out IDX=NBYTES ...      (request output buffer of NBYTES)
//
// Stdout protocol (text; one field per line):
//   STATUS OK | COMPILE_FAIL | FUNCTION_MISSING | ARCHIVE_FAIL | PIPELINE_MISS |
//          PIPELINE_FAIL | CMDBUF_ERROR
//   DEVICE <name>
//   FUNCTION <name>
//   PIPELINE_SOURCE archive     (pipeline was built from the binary archive)
//   GPUTIME_NS <n>
//   OUT <idx> <hexbytes>
//   (on failure) ERROR <message>
//
// Exit status: 0 on STATUS OK, 1 on any failure.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void emit_status(const char *s) { printf("STATUS %s\n", s); }

static void fail(const char *status, const char *msg, NSError *err) {
    emit_status(status);
    if (err)
        printf("ERROR %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else if (msg)
        printf("ERROR %s\n", msg);
    fflush(stdout);
    exit(1);
}

// A single input buffer request: index + path to raw bytes.
typedef struct { int index; const char *path; } InBuf;
// A single output buffer request: index + size in bytes.
typedef struct { int index; long size; } OutBuf;

enum { OPT_NO_FAST_MATH = 128 };

static const struct option longOpts[] = {
    {"archive",      required_argument, NULL, 'a'},
    {"source",       required_argument, NULL, 's'},
    {"function",     required_argument, NULL, 'f'},
    {"grid",         required_argument, NULL, 'g'},
    {"tg",           required_argument, NULL, 't'},
    {"buf",          required_argument, NULL, 'b'},
    {"out",          required_argument, NULL, 'o'},
    {"no-fast-math", no_argument,       NULL, OPT_NO_FAST_MATH},
    {NULL, 0, NULL, 0}
};

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *archivePath = NULL, *sourcePath = NULL, *funcName = NULL;
        long grid = 1, tg = 1;
        BOOL fastMath = YES;
        InBuf ins[64]; int nins = 0;
        OutBuf outs[64]; int nouts = 0;
        int c;
        while ((c = getopt_long(argc, argv, "a:s:f:g:t:b:o:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'a': archivePath = optarg; break;
                case 's': sourcePath = optarg; break;
                case 'f': funcName = optarg; break;
                case 'g': grid = strtol(optarg, NULL, 0); break;
                case 't': tg = strtol(optarg, NULL, 0); break;
                case OPT_NO_FAST_MATH: fastMath = NO; break;
                case 'b': {
                    char *eq = strchr(optarg, '=');
                    if (!eq) fail("PIPELINE_FAIL", "bad --buf (want IDX=FILE)", nil);
                    *eq = 0;
                    ins[nins].index = (int)strtol(optarg, NULL, 0);
                    ins[nins].path = eq + 1; nins++;
                    break;
                }
                case 'o': {
                    char *eq = strchr(optarg, '=');
                    if (!eq) fail("PIPELINE_FAIL", "bad --out (want IDX=NBYTES)", nil);
                    *eq = 0;
                    outs[nouts].index = (int)strtol(optarg, NULL, 0);
                    outs[nouts].size = strtol(eq + 1, NULL, 0); nouts++;
                    break;
                }
                default:
                    fprintf(stderr, "usage: see header\n");
                    return 1;
            }
        }
        if (!archivePath || !sourcePath || !funcName)
            fail("PIPELINE_FAIL", "need --archive --source --function", nil);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
        printf("DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err = nil;

        // --- 1. Compile OUR source -> library -> function (the identity). ------
        // This gives Metal the AIR-level function whose hash keys the archive
        // lookup. It is the same source shdump compiled to build the archive, so
        // the hash matches the archive entry (same source + same options).
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                  encoding:NSUTF8StringEncoding error:&err];
        if (!src) fail("COMPILE_FAIL", "read source", err);
        MTLCompileOptions *copts = [MTLCompileOptions new];
        [copts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:copts error:&err];
        if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
        id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:funcName]];
        if (!fn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

        // --- 2. Load the (possibly spliced) binary archive from URL. -----------
        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        [adesc setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
        id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!archive) fail("ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);

        // --- 3. Build the pipeline, FORCING use of the archive's binary. -------
        // MTLPipelineOptionFailOnBinaryArchiveMiss makes pipeline creation fail
        // (rather than silently recompiling from AIR) if the archive does not
        // supply the compiled code -> so success proves the *archived* (spliced)
        // machine code was used.
        MTLComputePipelineDescriptor *pdesc = [MTLComputePipelineDescriptor new];
        [pdesc setComputeFunction:fn];
        [pdesc setBinaryArchives:@[archive]];
        id<MTLComputePipelineState> pso =
            [dev newComputePipelineStateWithDescriptor:pdesc
                                               options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                            reflection:nil
                                                 error:&err];
        if (!pso) {
            // A "miss" means the archive did not contain a matching precompiled
            // entry; distinguish it so the caller knows the splice/identity path.
            fail("PIPELINE_MISS", "newComputePipelineStateWithDescriptor (FailOnBinaryArchiveMiss)", err);
        }
        printf("FUNCTION %s\n", funcName);
        printf("PIPELINE_SOURCE archive\n");

        // --- 4. Set up buffers. ------------------------------------------------
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        // Track buffers by index (0..63).
        id<MTLBuffer> bufs[64] = {0};
        for (int i = 0; i < nins; i++) {
            NSData *d = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:ins[i].path]];
            if (!d) fail("PIPELINE_FAIL", "read input buffer file", nil);
            id<MTLBuffer> b = [dev newBufferWithBytes:[d bytes] length:[d length]
                                              options:MTLResourceStorageModeShared];
            bufs[ins[i].index] = b;
        }
        for (int i = 0; i < nouts; i++) {
            int idx = outs[i].index;
            if (!bufs[idx]) {
                id<MTLBuffer> b = [dev newBufferWithLength:outs[i].size
                                                  options:MTLResourceStorageModeShared];
                bufs[idx] = b;
            }
        }

        // --- 5. Dispatch. ------------------------------------------------------
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        for (int i = 0; i < 64; i++)
            if (bufs[i]) [enc setBuffer:bufs[i] offset:0 atIndex:i];
        [enc dispatchThreads:MTLSizeMake(grid, 1, 1)
      threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];

        if ([cb status] == MTLCommandBufferStatusError) {
            fail("CMDBUF_ERROR", "command buffer failed", [cb error]);
        }
        printf("GPUTIME_NS %llu\n",
               (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));

        // --- 6. Dump output buffers as hex (text-only). ------------------------
        for (int i = 0; i < nouts; i++) {
            int idx = outs[i].index;
            const unsigned char *p = (const unsigned char *)[bufs[idx] contents];
            long n = outs[i].size;
            // hex-encode
            char *hex = (char *)malloc(n * 2 + 1);
            static const char H[] = "0123456789abcdef";
            for (long j = 0; j < n; j++) {
                hex[j * 2]     = H[p[j] >> 4];
                hex[j * 2 + 1] = H[p[j] & 0xf];
            }
            hex[n * 2] = 0;
            printf("OUT %d %s\n", idx, hex);
            free(hex);
        }

        emit_status("OK");
        fflush(stdout);
        return 0;
    }
}
