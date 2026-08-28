// fencelitmus.m -- EXP-0093 authored compute device-fence litmus runner for the
// msg_pairs_* family (kernels/litmus_devfence_pairs.metal). Dispatches PAIRS
// independent producer/consumer threadgroup pairs (threadgroup 2k=producer,
// 2k+1=consumer for mailbox k) in one compute command, to test ATOM-07/ATOM-08
// (relaxed-only vs device-scope-fenced message passing) at much larger
// concurrency than EXP-0051's 1-2 threadgroup mailboxes.
//
// PLAIN mode (no --archive): normal newLibraryWithSource: compile.
// SPLICE mode (--archive given): identical technique to roglitmus.m/agxrun.m --
// force the compute pipeline from a (possibly byte-patched) archive via
// MTLPipelineOptionFailOnBinaryArchiveMiss; splicing itself is done by the
// Python caller (harness/splice.py) on a scratch copy of the archive.
//
// Buffers: 0 = Mailbox array (PAIRS * 24 bytes, zero-init), 1 = out (4 uint32,
// zero-init: [0]=mismatch count [1]=producer timeouts [2]=consumer timeouts
// [3]=messages completed), 2 = iterations (uint32 constant), 3 = spinBound
// (uint32 constant).
//
// CLEAN-ROOM: only the public Metal API on OUR OWN compiled shader. No Apple
// binary is disassembled or introspected.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -o fencelitmus fencelitmus.m
//
// Stdout protocol:
//   STATUS OK | COMPILE_FAIL | FUNCTION_MISSING | ARCHIVE_FAIL | PIPELINE_MISS |
//          PIPELINE_FAIL | CMDBUF_ERROR
//   DEVICE <name>
//   PIPELINE_SOURCE plain|archive
//   GPUTIME_NS <n>
//   OUT mismatch=<n> producer_timeouts=<n> consumer_timeouts=<n> completed=<n>

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
    if (err)      printf("ERROR %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    if (fflush(NULL) != 0) { perror("fflush"); }
    if (ferror(stdout)) { fprintf(stderr, "stdout error\n"); }
    exit(1);
}

enum { OPT_PAIRS = 256, OPT_ITER, OPT_SPIN, OPT_TGSIZE };
static const struct option longOpts[] = {
    {"archive",     required_argument, NULL, 'a'},
    {"source",      required_argument, NULL, 's'},
    {"function",    required_argument, NULL, 'f'},
    {"pairs",       required_argument, NULL, OPT_PAIRS},
    {"iterations",  required_argument, NULL, OPT_ITER},
    {"spin-bound",  required_argument, NULL, OPT_SPIN},
    {"tg-size",     required_argument, NULL, OPT_TGSIZE},
    {NULL, 0, NULL, 0}
};

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *archivePath = NULL, *sourcePath = NULL, *fName = NULL;
        long pairs = 8, iterations = 100, spinBound = 1000000, tgSize = 32;
        int c;
        while ((c = getopt_long(argc, argv, "a:s:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'a': archivePath = optarg; break;
                case 's': sourcePath = optarg; break;
                case 'f': fName = optarg; break;
                case OPT_PAIRS: pairs = strtol(optarg, NULL, 0); break;
                case OPT_ITER:  iterations = strtol(optarg, NULL, 0); break;
                case OPT_SPIN:  spinBound = strtol(optarg, NULL, 0); break;
                case OPT_TGSIZE: tgSize = strtol(optarg, NULL, 0); break;
                default: fprintf(stderr, "usage: see header\n"); return 1;
            }
        }
        if (!sourcePath || !fName) fail("PIPELINE_FAIL", "need --source --function", nil);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
        printf("DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                  encoding:NSUTF8StringEncoding error:&err];
        if (!src) fail("COMPILE_FAIL", "read source", err);
        MTLCompileOptions *copts = [MTLCompileOptions new];
        [copts setFastMathEnabled:YES];   // match tools/shdump/shdump.m's default
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:copts error:&err];
        if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
        id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
        if (!fn) fail("FUNCTION_MISSING", "newFunctionWithName", nil);

        id<MTLComputePipelineState> pso = nil;
        const char *pipelineSource = "plain";
        if (archivePath) {
            MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
            [adesc setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
            id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
            if (!archive) fail("ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);
            MTLComputePipelineDescriptor *pdesc = [MTLComputePipelineDescriptor new];
            pdesc.computeFunction = fn;
            pdesc.binaryArchives = @[archive];
            pso = [dev newComputePipelineStateWithDescriptor:pdesc
                                                       options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                                    reflection:nil
                                                         error:&err];
            if (!pso) fail("PIPELINE_MISS",
                           "newComputePipelineStateWithDescriptor (FailOnBinaryArchiveMiss)", err);
            pipelineSource = "archive";
        } else {
            pso = [dev newComputePipelineStateWithFunction:fn error:&err];
            if (!pso) fail("PIPELINE_FAIL", "newComputePipelineStateWithFunction (plain)", err);
        }
        printf("PIPELINE_SOURCE %s\n", pipelineSource);

        // Mailbox = {uint payload[4]; atomic_uint ready; atomic_uint ack;} = 24 bytes.
        NSUInteger mailboxBytes = (NSUInteger)pairs * 24;
        id<MTLBuffer> boxes = [dev newBufferWithLength:mailboxBytes options:MTLResourceStorageModeShared];
        memset([boxes contents], 0, (size_t)mailboxBytes);
        id<MTLBuffer> out = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
        memset([out contents], 0, 16);
        uint32_t iterU = (uint32_t)iterations;
        uint32_t spinU = (uint32_t)spinBound;
        id<MTLBuffer> iterBuf = [dev newBufferWithBytes:&iterU length:4 options:MTLResourceStorageModeShared];
        id<MTLBuffer> spinBuf = [dev newBufferWithBytes:&spinU length:4 options:MTLResourceStorageModeShared];

        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        [enc setBuffer:boxes offset:0 atIndex:0];
        [enc setBuffer:out offset:0 atIndex:1];
        [enc setBuffer:iterBuf offset:0 atIndex:2];
        [enc setBuffer:spinBuf offset:0 atIndex:3];
        NSUInteger totalThreads = (NSUInteger)(2 * pairs) * (NSUInteger)tgSize;
        [enc dispatchThreads:MTLSizeMake(totalThreads, 1, 1)
      threadsPerThreadgroup:MTLSizeMake((NSUInteger)tgSize, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError)
            fail("CMDBUF_ERROR", "command buffer failed", [cb error]);
        printf("GPUTIME_NS %llu\n",
               (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));

        uint32_t *o = (uint32_t *)[out contents];
        printf("OUT mismatch=%u producer_timeouts=%u consumer_timeouts=%u completed=%u\n",
               o[0], o[1], o[2], o[3]);

        emit_status("OK");
        if (fflush(NULL) != 0) { perror("fflush"); return 1; }
        if (ferror(stdout)) { fprintf(stderr, "stdout error\n"); return 1; }
        return 0;
    }
}
