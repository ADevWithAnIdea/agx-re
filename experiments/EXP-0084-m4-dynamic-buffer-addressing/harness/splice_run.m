// EXP-0084 splice_run.m — dynamic-address-specific splice/execute runner.
//
// `tools/agxtest/agxrun.m` (read-only; reused here as the load-a-possibly-
// spliced-archive-and-force-it-to-run technique, EXP-0003/EXP-0005) accepts
// only literal-bytes-from-file input buffers via --buf IDX=FILE. That cannot
// express this experiment's `splice_target` kernel's actual input: a buffer
// of REAL `.gpuAddress` values for OTHER buffers this same process allocates
// -- an address is only known after the buffer exists, inside this same
// process, so no external file can supply it. This file is therefore steps
// 1-3 of `agxrun.m` (compile our source for AIR identity, load the archive,
// force the pipeline to instantiate from the archive's machine code with
// MTLPipelineOptionFailOnBinaryArchiveMiss) combined with `harness/probe.m`'s
// custom two-tagged-buffer + gpuAddress-array setup, in one process so the
// addresses are real and valid for the dispatch that dereferences them.
//
// CLEAN-ROOM: public Metal API only, on OUR OWN compiled+possibly-spliced
// shader bytes (the archive is produced by tools/shdump from our own MSL,
// spliced out-of-band by analysis/splice_case.py, exactly the technique
// documented in tools/agxtest/README.md). No Apple binary is introspected.
//
// Usage:
//   splice_run --archive ARCH.bin --source SRC.metal --function NAME
// Buffer layout is FIXED (matches kernels/probes.metal's splice_target):
//   backing[0] = 32 x TAG_A (0x5A0000AA), backing[1] = 32 x TAG_B (0x5A0000BB)
//   addrs[0]=backing[0].gpuAddress, addrs[1]=backing[1].gpuAddress
//   buffer(0)=addrs, buffer(1)=out (32 words), buffer(2)=outb (32 words)
// Stdout: one JSON line: {"status","pipeline_source","cb_status","error",
//                         "out_hex","outb_hex"}  -- no addresses printed.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TAG_A 0x5A0000AAu
#define TAG_B 0x5A0000BBu

static void js(NSString *s) {
    NSData *d = [NSJSONSerialization dataWithJSONObject:(s ?: @"") options:NSJSONWritingFragmentsAllowed error:nil];
    fwrite(d.bytes, 1, d.length, stdout);
}
static void hex32(const uint32_t *w, NSUInteger n) {
    printf("\""); for (NSUInteger i = 0; i < n; i++) printf("%08x", w[i]); printf("\"");
}
static void emit(const char *status, NSString *pipeline_source, long cb_status, NSString *err,
                  const uint32_t *out_w, NSUInteger out_n, const uint32_t *outb_w, NSUInteger outb_n) {
    printf("{\"status\":\"%s\",\"pipeline_source\":", status); js(pipeline_source ?: @"");
    printf(",\"cb_status\":%ld,\"error\":", cb_status); js(err ?: @"");
    printf(",\"out_hex\":"); if (out_w) hex32(out_w, out_n); else printf("\"\"");
    printf(",\"outb_hex\":"); if (outb_w) hex32(outb_w, outb_n); else printf("\"\"");
    printf("}\n");
    fflush(stdout);
}

int main(int argc, const char **argv) { @autoreleasepool {
    const char *archivePath = NULL, *sourcePath = NULL, *funcName = NULL;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--archive") && i + 1 < argc) archivePath = argv[++i];
        else if (!strcmp(argv[i], "--source") && i + 1 < argc) sourcePath = argv[++i];
        else if (!strcmp(argv[i], "--function") && i + 1 < argc) funcName = argv[++i];
    }
    if (!archivePath || !sourcePath || !funcName) { fprintf(stderr, "ARGS_FAIL\n"); return 2; }

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { fprintf(stderr, "DEVICE_FAIL\n"); return 3; }
    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:@(sourcePath) encoding:NSUTF8StringEncoding error:&err];
    if (!src) { emit("SOURCE_FAIL", @"", -1, @"read source failed", NULL, 0, NULL, 0); return 0; }
    MTLCompileOptions *copts = [MTLCompileOptions new];
    copts.mathMode = MTLMathModeSafe;
    copts.fastMathEnabled = NO;
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:copts error:&err];
    if (!lib) { emit("COMPILE_FAIL", @"", -1, err.localizedDescription, NULL, 0, NULL, 0); return 0; }
    id<MTLFunction> fn = [lib newFunctionWithName:@(funcName)];
    if (!fn) { emit("FUNCTION_MISSING", @"", -1, @"newFunctionWithName", NULL, 0, NULL, 0); return 0; }

    MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
    adesc.url = [NSURL fileURLWithPath:@(archivePath)];
    id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
    if (!archive) { emit("ARCHIVE_FAIL", @"", -1, err.localizedDescription, NULL, 0, NULL, 0); return 0; }

    MTLComputePipelineDescriptor *pdesc = [MTLComputePipelineDescriptor new];
    pdesc.computeFunction = fn;
    pdesc.binaryArchives = @[archive];
    id<MTLComputePipelineState> pso =
        [dev newComputePipelineStateWithDescriptor:pdesc
                                           options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                        reflection:nil error:&err];
    if (!pso) { emit("PIPELINE_MISS", @"", -1, err.localizedDescription, NULL, 0, NULL, 0); return 0; }

    id<MTLBuffer> backingA = [dev newBufferWithLength:32 * 4 options:MTLResourceStorageModeShared];
    id<MTLBuffer> backingB = [dev newBufferWithLength:32 * 4 options:MTLResourceStorageModeShared];
    uint32_t *pa = backingA.contents, *pb = backingB.contents;
    for (int i = 0; i < 32; i++) { pa[i] = TAG_A; pb[i] = TAG_B; }
    id<MTLBuffer> addrs = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    uint64_t *paddr = addrs.contents;
    paddr[0] = backingA.gpuAddress;
    paddr[1] = backingB.gpuAddress;
    id<MTLBuffer> out = [dev newBufferWithLength:32 * 4 options:MTLResourceStorageModeShared];
    id<MTLBuffer> outb = [dev newBufferWithLength:32 * 4 options:MTLResourceStorageModeShared];

    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:pso];
    [ce useResource:backingA usage:MTLResourceUsageRead];
    [ce useResource:backingB usage:MTLResourceUsageRead];
    [ce setBuffer:addrs offset:0 atIndex:0];
    [ce setBuffer:out offset:0 atIndex:1];
    [ce setBuffer:outb offset:0 atIndex:2];
    [ce dispatchThreads:MTLSizeMake(32, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
    [ce endEncoding];
    [cb commit];
    [cb waitUntilCompleted];

    uint32_t out_w[32], outb_w[32];
    memcpy(out_w, out.contents, 32 * 4);
    memcpy(outb_w, outb.contents, 32 * 4);
    emit("OK", @"archive", (long)cb.status, cb.error.localizedDescription ?: @"", out_w, 32, outb_w, 32);
    if (fflush(stdout) != 0 || ferror(stdout)) { fprintf(stderr, "STDOUT_FLUSH_FAIL\n"); return 5; }
    return 0;
} }
