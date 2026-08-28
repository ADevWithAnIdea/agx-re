// agxrun_persist.m -- clean-room OWN-SHADER PERSISTENT hardware round-trip
// runner (EXP-0005, task 1). Recommended by EXP-0003 to avoid one process
// spawn per splice during field sweeps.
//
// It holds ONE live MTLDevice + command queue + compiled library/function for
// its whole lifetime and loops over requests read from stdin, each of the form
//   (spliced-archive-path, input buffers, output requests) -> outputs
// logging-and-continuing past command-buffer faults (which EXP-0003 showed are
// contained for the illegal-ALU-op class) so a 256-value field sweep costs one
// process launch instead of 256.
//
// CLEAN-ROOM: identical technique to agxrun.m (load a binary archive we built
// from OUR OWN MSL, force pipeline creation from the archived machine code with
// MTLPipelineOptionFailOnBinaryArchiveMiss, dispatch, read back). Only our own
// compiled shader bytes are ever executed. No Apple binary is disassembled.
//
// Build (device, CLT only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o agxrun_persist agxrun_persist.m
//
// Startup args:
//   agxrun_persist --source SRC.metal --function NAME [--no-fast-math]
// Prints:  READY <device-name>       (once, when the library+function are ready)
//
// Request protocol (one request per stdin line, whitespace-delimited):
//   <reqid> <archive_path> <grid> <tg> <nin> [<idx>:<file> ...] <nout> [<idx>:<nbytes> ...]
// Response block (terminated by a DONE line, always flushed):
//   REQ <reqid>
//   STATUS OK | ARCHIVE_FAIL | PIPELINE_MISS | CMDBUF_ERROR | BAD_REQUEST
//   [GPUTIME_NS <n>]
//   [OUT <idx> <hex> ...]
//   [ERROR <msg>]
//   DONE <reqid>
// EOF on stdin -> exit 0.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

enum { OPT_NO_FAST_MATH = 128 };
static const struct option longOpts[] = {
    {"source",       required_argument, NULL, 's'},
    {"function",     required_argument, NULL, 'f'},
    {"no-fast-math", no_argument,       NULL, OPT_NO_FAST_MATH},
    {NULL, 0, NULL, 0}
};

// Globals held for the process lifetime.
static id<MTLDevice>       gDev  = nil;
static id<MTLCommandQueue> gQueue = nil;
static NSString           *gSrc  = nil;   // OUR MSL source text
static const char         *gFuncName = NULL;
static BOOL                gFastMath = YES;

// NOTE: we must NOT reuse a single cached MTLFunction across requests. Metal
// memoizes a function's compiled machine code in-process after the first
// pipeline build, so a later spliced archive (same AIR identity) would be
// ignored and the ORIGINAL code would run. We therefore compile a FRESH
// MTLLibrary+MTLFunction per request (exactly what the per-process agxrun.m
// does), which forces Metal to honor each freshly-loaded (spliced) archive.
// The device + command queue stay persistent (the expensive part we amortize).

static void respond_fail(const char *reqid, const char *status, const char *msg, NSError *err) {
    printf("REQ %s\n", reqid);
    printf("STATUS %s\n", status);
    if (err)      printf("ERROR %s: %s\n", msg ? msg : "", [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    printf("DONE %s\n", reqid);
    fflush(stdout);
}

// Handle exactly one request line (mutates a mutable copy). Returns void; all
// outcomes are reported on stdout. Never exits on a per-request failure.
static void handle_request(char *line) {
    @autoreleasepool {
        // tokenize
        char *save = NULL;
        char *reqid = strtok_r(line, " \t\r\n", &save);
        if (!reqid) return; // blank line
        char *archive = strtok_r(NULL, " \t\r\n", &save);
        char *sgrid   = strtok_r(NULL, " \t\r\n", &save);
        char *stg     = strtok_r(NULL, " \t\r\n", &save);
        char *snin    = strtok_r(NULL, " \t\r\n", &save);
        if (!archive || !sgrid || !stg || !snin) {
            respond_fail(reqid, "BAD_REQUEST", "want: id archive grid tg nin ... nout ...", nil);
            return;
        }
        long grid = strtol(sgrid, NULL, 0);
        long tg   = strtol(stg,   NULL, 0);
        int  nin  = (int)strtol(snin, NULL, 0);

        id<MTLBuffer> bufs[64] = {0};
        for (int i = 0; i < nin; i++) {
            char *spec = strtok_r(NULL, " \t\r\n", &save);
            if (!spec) { respond_fail(reqid, "BAD_REQUEST", "missing input spec", nil); return; }
            char *colon = strchr(spec, ':');
            if (!colon) { respond_fail(reqid, "BAD_REQUEST", "input want IDX:FILE", nil); return; }
            *colon = 0;
            int idx = (int)strtol(spec, NULL, 0);
            NSData *d = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:colon + 1]];
            if (!d) { respond_fail(reqid, "BAD_REQUEST", "cannot read input file", nil); return; }
            bufs[idx] = [gDev newBufferWithBytes:[d bytes] length:[d length]
                                        options:MTLResourceStorageModeShared];
        }
        char *snout = strtok_r(NULL, " \t\r\n", &save);
        int nout = snout ? (int)strtol(snout, NULL, 0) : 0;
        int outIdx[64]; long outSz[64];
        for (int i = 0; i < nout; i++) {
            char *spec = strtok_r(NULL, " \t\r\n", &save);
            if (!spec) { respond_fail(reqid, "BAD_REQUEST", "missing output spec", nil); return; }
            char *colon = strchr(spec, ':');
            if (!colon) { respond_fail(reqid, "BAD_REQUEST", "output want IDX:NBYTES", nil); return; }
            *colon = 0;
            outIdx[i] = (int)strtol(spec, NULL, 0);
            outSz[i]  = strtol(colon + 1, NULL, 0);
            if (!bufs[outIdx[i]])
                bufs[outIdx[i]] = [gDev newBufferWithLength:outSz[i]
                                                   options:MTLResourceStorageModeShared];
        }

        NSError *err = nil;
        NSURL *archiveURL = [NSURL fileURLWithPath:[NSString stringWithUTF8String:archive]];
        // Load a FRESH MTLLibrary from the (spliced) archive DATA per request.
        // This is the crux (see note above and the public hwtestbed): a library
        // compiled from *source* has a fixed AIR hash whose native code the
        // device memoizes in-process, so a separately-loaded spliced archive is
        // ignored on the 2nd+ request. Loading the library from the spliced
        // archive's own bytes makes each request's library distinct, so the
        // spliced machine code actually runs.
        id<MTLLibrary> lib = [gDev newLibraryWithURL:archiveURL error:&err];
        if (!lib) { respond_fail(reqid, "COMPILE_FAIL", "newLibraryWithURL(archive)", err); return; }
        id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:gFuncName]];
        if (!fn) { respond_fail(reqid, "FUNCTION_MISSING", "newFunctionWithName", nil); return; }

        // Also bind the archive so pipeline creation uses its precompiled
        // (spliced) native code rather than recompiling AIR.
        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        [adesc setUrl:archiveURL];
        id<MTLBinaryArchive> arc = [gDev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!arc) { respond_fail(reqid, "ARCHIVE_FAIL", "newBinaryArchive", err); return; }

        MTLComputePipelineDescriptor *pdesc = [MTLComputePipelineDescriptor new];
        [pdesc setComputeFunction:fn];
        [pdesc setBinaryArchives:@[arc]];
        id<MTLComputePipelineState> pso =
            [gDev newComputePipelineStateWithDescriptor:pdesc
                                                options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                             reflection:nil error:&err];
        if (!pso) { respond_fail(reqid, "PIPELINE_MISS", "pipeline (FailOnBinaryArchiveMiss)", err); return; }

        id<MTLCommandBuffer> cb = [gQueue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        for (int i = 0; i < 64; i++) if (bufs[i]) [enc setBuffer:bufs[i] offset:0 atIndex:i];
        [enc dispatchThreads:MTLSizeMake(grid, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];

        if ([cb status] == MTLCommandBufferStatusError) {
            respond_fail(reqid, "CMDBUF_ERROR", "command buffer failed", [cb error]);
            // Refresh the queue: a faulted submission can leave the queue in a
            // bad state for subsequent work. Cheap insurance.
            gQueue = [gDev newCommandQueue];
            return;
        }

        printf("REQ %s\n", reqid);
        printf("STATUS OK\n");
        printf("GPUTIME_NS %llu\n",
               (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));
        for (int i = 0; i < nout; i++) {
            const unsigned char *p = (const unsigned char *)[bufs[outIdx[i]] contents];
            long n = outSz[i];
            char *hex = (char *)malloc(n * 2 + 1);
            static const char H[] = "0123456789abcdef";
            for (long j = 0; j < n; j++) { hex[j*2] = H[p[j] >> 4]; hex[j*2+1] = H[p[j] & 0xf]; }
            hex[n*2] = 0;
            printf("OUT %d %s\n", outIdx[i], hex);
            free(hex);
        }
        printf("DONE %s\n", reqid);
        fflush(stdout);
    }
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *sourcePath = NULL, *funcName = NULL;
        BOOL fastMath = YES;
        int c;
        while ((c = getopt_long(argc, argv, "s:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 's': sourcePath = optarg; break;
                case 'f': funcName = optarg; break;
                case OPT_NO_FAST_MATH: fastMath = NO; break;
            }
        }
        if (!sourcePath || !funcName) {
            fprintf(stderr, "usage: agxrun_persist --source SRC --function NAME [--no-fast-math]\n");
            return 2;
        }
        gDev = MTLCreateSystemDefaultDevice();
        if (!gDev) { fprintf(stderr, "no Metal device\n"); return 1; }
        gQueue = [gDev newCommandQueue];
        gFuncName = funcName;
        gFastMath = fastMath;

        NSError *err = nil;
        gSrc = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                         encoding:NSUTF8StringEncoding error:&err];
        if (!gSrc) { fprintf(stderr, "read source failed\n"); return 1; }
        // Sanity-compile once at startup so a bad source fails fast.
        MTLCompileOptions *copts = [MTLCompileOptions new];
        [copts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib = [gDev newLibraryWithSource:gSrc options:copts error:&err];
        if (!lib) { fprintf(stderr, "compile failed: %s\n", [[err localizedDescription] UTF8String]); return 1; }
        if (![lib newFunctionWithName:[NSString stringWithUTF8String:funcName]]) {
            fprintf(stderr, "function %s missing\n", funcName); return 1;
        }

        printf("READY %s\n", [[gDev name] UTF8String]);
        fflush(stdout);

        // Request loop.
        char *line = NULL;
        size_t cap = 0;
        ssize_t len;
        while ((len = getline(&line, &cap, stdin)) > 0) {
            char *copy = strdup(line);
            handle_request(copy);
            free(copy);
        }
        free(line);
        return 0;
    }
}
