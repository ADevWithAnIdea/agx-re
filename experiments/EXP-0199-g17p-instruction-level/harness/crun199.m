// crun199.m -- EXP-0199 persistent COMPUTE splice + readback runner (G17P).
//
// Derived from OUR OWN tools/agxtest/agxrun_persist.m (EXP-0005: persistent
// device, fresh MTLLibrary per request from the SPLICED archive's own bytes,
// MTLPipelineOptionFailOnBinaryArchiveMiss, fault logged-and-continued) and from
// OUR OWN experiments/EXP-0172-.../harness/gfrun2.m (per-request scratch archive,
// the on-disk splice SENTINEL, the 0xDEADBEEF read-back poison and the ERRDOM
// fault-classification print).
//
// WHY A FORK RATHER THAN THE SHARED TOOL.  agxrun_persist.m takes an already
// written archive path per request and does NOT poison the output buffer.
// FIELD-SWEEP-PROTOCOL sec.7.1 makes the poison the single most important
// instrument, because on this ISA a wrong encoding usually yields a silent zero
// and a zero-initialised buffer cannot tell "wrote 0" from "never ran".  This
// experiment's whole method is insertion of a marker into an instruction stream,
// where "the program stopped early" and "the program computed 0" MUST be
// distinguishable.  It also needs the splice applied IN this process so the
// bytes on disk can be verified before the dispatch.
//
// CLEAN-ROOM: public Metal API only, on shaders compiled from OUR OWN MSL.  No
// Apple binary is disassembled or introspected.
//
// Build:  clang -fobjc-arc -framework Metal -framework Foundation -o crun199 crun199.m
//
// Startup:
//   crun199 --source S.metal --function F --archive base.bin --scratch work/sc.bin
//           --grid 32 --tg 32 --in 1=inputs.bin --out 0=512 [--no-fast-math] --persist
// Request (one line):
//   <reqid> <nsplices> [<off>=<hex> ...]
// Response:
//   REQ id / STATUS ... / [SENTINEL OK n] / [GPUTIME_NS n] / [OUT <idx> <hex>]
//   / [ERRDOM domain code] / [ERROR msg] / DONE id
// STATUS: OK | COMPILE_FAIL | FUNCTION_MISSING | ARCHIVE_FAIL | PIPELINE_MISS |
//         CMDBUF_ERROR | BAD_REQUEST | SENTINEL_FAIL

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

typedef struct { size_t off; unsigned char *bytes; size_t len; } SpliceSpec;

static const unsigned char READBACK_POISON[4] = {0xEF, 0xBE, 0xAD, 0xDE}; // 0xDEADBEEF LE
static void poison(unsigned char *p, size_t n) {
    for (size_t i = 0; i < n; i++) p[i] = READBACK_POISON[i & 3];
}

static id<MTLDevice> gDev = nil;
static id<MTLCommandQueue> gQ = nil;
static NSData *gBaseArchive = nil;
static NSString *gScratch = nil;
static const char *gSrcPath = NULL, *gFuncName = NULL;
static BOOL gFastMath = YES;
static long gGrid = 32, gTG = 32;
static unsigned long gReqSeq = 0;
static int gInIdx[16]; static NSData *gInData[16]; static int gNIn = 0;
static int gOutIdx[16]; static long gOutSz[16]; static int gNOut = 0;
// GATE A (RE_EXPERIMENT_PROCESS_CORRECTIONS sec.3): the ACTUAL-BYTE LEDGER.
// gLedger* names a window of the FINAL DISPATCHED FILE.  After the splices are
// written and the file is re-read from disk, those bytes are printed verbatim as
// `ACTUAL <off> <hex>`.  They are the bytes handed to newLibraryWithURL:, so the
// driver can decode the value that was really dispatched and assert it equals the
// value that was requested -- which a symmetric assemble/disassemble round trip
// cannot do.
static long gLedgerOff[8]; static long gLedgerLen[8]; static int gNLedger = 0;

static BOOL gLedgerEmitted = NO;
static void printHex(const char *tag, int idx, const unsigned char *p, size_t n) {
    static const char H[] = "0123456789abcdef";
    printf("%s %d ", tag, idx);
    for (size_t i = 0; i < n; i++) { fputc(H[p[i] >> 4], stdout); fputc(H[p[i] & 15], stdout); }
    fputc('\n', stdout);
}

static void respond_fail(const char *rid, const char *status, const char *msg, NSError *err) {
    if (rid && !gLedgerEmitted) printf("REQ %s\n", rid);
    printf("STATUS %s\n", status);
    if (err) {
        NSString *d = [[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" "];
        printf("ERRDOM %s %ld\n", [[err domain] UTF8String], (long)[err code]);
        printf("ERROR %s: %s\n", msg ? msg : "", [d UTF8String]);
    } else if (msg) printf("ERROR %s\n", msg);
    if (rid) printf("DONE %s\n", rid);
    fflush(stdout);
}

static int doRun(const char *rid, SpliceSpec *spl, int nspl) {
  @autoreleasepool {
    gLedgerEmitted = NO;
    NSError *err = nil;

    NSMutableData *patched = [gBaseArchive mutableCopy];
    for (int i = 0; i < nspl; i++) {
        if (spl[i].off + spl[i].len > [patched length]) {
            respond_fail(rid, "BAD_REQUEST", "splice OOB", nil); return 1;
        }
        memcpy((unsigned char *)[patched mutableBytes] + spl[i].off, spl[i].bytes, spl[i].len);
    }
    NSString *scratchN = [NSString stringWithFormat:@"%@.%lu", gScratch, ++gReqSeq];
    if (![patched writeToFile:scratchN atomically:YES]) {
        respond_fail(rid, "ARCHIVE_FAIL", "write scratch", nil); return 1;
    }
    NSURL *aurl = [NSURL fileURLWithPath:scratchN];

    // INTEGRITY SENTINEL: read the file back through a SEPARATE NSData read and
    // compare every spliced window byte-for-byte, so a silent write failure or a
    // stale cached path reports SENTINEL_FAIL instead of scoring as a result.
    {
        NSData *rb = [NSData dataWithContentsOfFile:scratchN];
        if (!rb || [rb length] != [patched length]) {
            respond_fail(rid, "SENTINEL_FAIL", "scratch read-back size mismatch", nil);
            [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil];
            return 1;
        }
        const unsigned char *rp = (const unsigned char *)[rb bytes];
        for (int i = 0; i < nspl; i++) {
            if (memcmp(rp + spl[i].off, spl[i].bytes, spl[i].len) != 0) {
                respond_fail(rid, "SENTINEL_FAIL", "spliced window not on disk", nil);
                [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil];
                return 1;
            }
        }
        if (rid) printf("REQ %s\n", rid);
        for (int i = 0; i < gNLedger; i++) {
            if ((size_t)(gLedgerOff[i] + gLedgerLen[i]) > [rb length]) continue;
            printHex("ACTUAL", (int)gLedgerOff[i], rp + gLedgerOff[i], (size_t)gLedgerLen[i]);
        }
        gLedgerEmitted = (rid != NULL);
    }

    id<MTLLibrary> lib = [gDev newLibraryWithURL:aurl error:&err];
    if (!lib) { respond_fail(rid, "COMPILE_FAIL", "newLibraryWithURL(archive)", err);
                [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil]; return 1; }
    id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:gFuncName]];
    if (!fn) { respond_fail(rid, "FUNCTION_MISSING", "newFunctionWithName", nil);
               [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil]; return 1; }

    MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
    [adesc setUrl:aurl];
    id<MTLBinaryArchive> arc = [gDev newBinaryArchiveWithDescriptor:adesc error:&err];
    if (!arc) { respond_fail(rid, "ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err);
                [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil]; return 1; }

    MTLComputePipelineDescriptor *pdesc = [MTLComputePipelineDescriptor new];
    [pdesc setComputeFunction:fn];
    [pdesc setBinaryArchives:@[arc]];
    id<MTLComputePipelineState> pso =
        [gDev newComputePipelineStateWithDescriptor:pdesc
                                            options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                         reflection:nil error:&err];
    if (!pso) { respond_fail(rid, "PIPELINE_MISS", "pipeline (FailOnBinaryArchiveMiss)", err);
                [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil]; return 1; }

    id<MTLBuffer> bufs[64]; memset(bufs, 0, sizeof(bufs));
    for (int i = 0; i < gNIn; i++)
        bufs[gInIdx[i]] = [gDev newBufferWithBytes:[gInData[i] bytes]
                                            length:[gInData[i] length]
                                           options:MTLResourceStorageModeShared];
    for (int i = 0; i < gNOut; i++) {
        bufs[gOutIdx[i]] = [gDev newBufferWithLength:(NSUInteger)gOutSz[i]
                                             options:MTLResourceStorageModeShared];
        // FIELD-SWEEP-PROTOCOL sec.7.1: poison, so "wrote 0" and "never ran"
        // are distinguishable observations.
        poison((unsigned char *)[bufs[gOutIdx[i]] contents], (size_t)gOutSz[i]);
    }

    id<MTLCommandBuffer> cb = [gQ commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    for (int i = 0; i < 64; i++) if (bufs[i]) [enc setBuffer:bufs[i] offset:0 atIndex:i];
    [enc dispatchThreads:MTLSizeMake((NSUInteger)gGrid, 1, 1)
   threadsPerThreadgroup:MTLSizeMake((NSUInteger)gTG, 1, 1)];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];

    if ([cb status] == MTLCommandBufferStatusError) {
        respond_fail(rid, "CMDBUF_ERROR", "command buffer failed", [cb error]);
        [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil];
        gQ = [gDev newCommandQueue];
        return 1;
    }

    if (rid && !gLedgerEmitted) printf("REQ %s\n", rid);
    printf("STATUS OK\n");
    printf("SENTINEL OK %d\n", nspl);
    printf("GPUTIME_NS %llu\n",
           (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));
    for (int i = 0; i < gNOut; i++)
        printHex("OUT", gOutIdx[i], (const unsigned char *)[bufs[gOutIdx[i]] contents],
                 (size_t)gOutSz[i]);
    [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil];
    if (rid) printf("DONE %s\n", rid);
    fflush(stdout);
    return 0;
  }
}

static void handle_request(char *line) {
    char *save = NULL;
    char *rid = strtok_r(line, " \t\r\n", &save);
    if (!rid) return;
    char *sn = strtok_r(NULL, " \t\r\n", &save);
    int n = sn ? (int)strtol(sn, NULL, 0) : 0;
    if (n < 0 || n > 32) { respond_fail(rid, "BAD_REQUEST", "nsplices out of range", nil); return; }
    SpliceSpec spl[32]; memset(spl, 0, sizeof spl);
    for (int i = 0; i < n; i++) {
        char *tok = strtok_r(NULL, " \t\r\n", &save);
        if (!tok) { respond_fail(rid, "BAD_REQUEST", "missing splice", nil); goto cleanup; }
        char *eq = strchr(tok, '=');
        if (!eq) { respond_fail(rid, "BAD_REQUEST", "splice wants OFF=HEX", nil); goto cleanup; }
        *eq = 0;
        spl[i].off = strtoul(tok, NULL, 0);
        size_t blen = strlen(eq + 1) / 2;
        spl[i].bytes = malloc(blen ? blen : 1);
        for (size_t k = 0; k < blen; k++) { unsigned v; sscanf(eq + 1 + k * 2, "%2x", &v); spl[i].bytes[k] = (unsigned char)v; }
        spl[i].len = blen;
    }
    doRun(rid, spl, n);
cleanup:
    for (int i = 0; i < n; i++) free(spl[i].bytes);
}

enum { O_SRC = 256, O_FN, O_ARCH, O_SCRATCH, O_GRID, O_TG, O_IN, O_OUT, O_NOFM, O_PERSIST, O_LEDGER };
static struct option L[] = {
    {"source", required_argument, 0, O_SRC}, {"function", required_argument, 0, O_FN},
    {"archive", required_argument, 0, O_ARCH}, {"scratch", required_argument, 0, O_SCRATCH},
    {"grid", required_argument, 0, O_GRID}, {"tg", required_argument, 0, O_TG},
    {"in", required_argument, 0, O_IN}, {"out", required_argument, 0, O_OUT},
    {"no-fast-math", no_argument, 0, O_NOFM}, {"persist", no_argument, 0, O_PERSIST},
    {"ledger", required_argument, 0, O_LEDGER},
    {0, 0, 0, 0}
};

int main(int argc, char *argv[]) { @autoreleasepool {
    const char *archPath = NULL, *scratchPath = NULL;
    BOOL persist = NO;
    int c;
    while ((c = getopt_long(argc, argv, "", L, NULL)) > 0) {
        switch (c) {
        case O_SRC: gSrcPath = optarg; break;
        case O_FN: gFuncName = optarg; break;
        case O_ARCH: archPath = optarg; break;
        case O_SCRATCH: scratchPath = optarg; break;
        case O_GRID: gGrid = strtol(optarg, NULL, 0); break;
        case O_TG: gTG = strtol(optarg, NULL, 0); break;
        case O_NOFM: gFastMath = NO; break;
        case O_PERSIST: persist = YES; break;
        case O_LEDGER: { char *c2 = strchr(optarg, ':'); if (!c2) return 2; *c2 = 0;
                         gLedgerOff[gNLedger] = strtol(optarg, NULL, 0);
                         gLedgerLen[gNLedger] = strtol(c2 + 1, NULL, 0); gNLedger++; break; }
        case O_IN: { char *eq = strchr(optarg, '='); if (!eq) return 2; *eq = 0;
                     gInIdx[gNIn] = (int)strtol(optarg, NULL, 0);
                     gInData[gNIn] = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:eq + 1]];
                     if (!gInData[gNIn]) { fprintf(stderr, "cannot read %s\n", eq + 1); return 1; }
                     gNIn++; break; }
        case O_OUT: { char *eq = strchr(optarg, '='); if (!eq) return 2; *eq = 0;
                      gOutIdx[gNOut] = (int)strtol(optarg, NULL, 0);
                      gOutSz[gNOut] = strtol(eq + 1, NULL, 0); gNOut++; break; }
        default: fprintf(stderr, "crun199: bad option\n"); return 2;
        }
    }
    if (!gSrcPath || !gFuncName || !archPath || !scratchPath) {
        fprintf(stderr, "crun199: need --source --function --archive --scratch\n"); return 2;
    }
    gDev = MTLCreateSystemDefaultDevice();
    if (!gDev) { fprintf(stderr, "no Metal device\n"); return 1; }
    gQ = [gDev newCommandQueue];
    gScratch = [NSString stringWithUTF8String:scratchPath];
    gBaseArchive = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:archPath]];
    if (!gBaseArchive) { fprintf(stderr, "cannot read archive\n"); return 1; }

    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:gSrcPath]
                                              encoding:NSUTF8StringEncoding error:&err];
    if (!src) { fprintf(stderr, "cannot read source\n"); return 1; }
    MTLCompileOptions *co = [MTLCompileOptions new];
    [co setFastMathEnabled:gFastMath];
    id<MTLLibrary> slib = [gDev newLibraryWithSource:src options:co error:&err];
    if (!slib) { fprintf(stderr, "compile failed: %s\n", [[err localizedDescription] UTF8String]); return 1; }
    if (![slib newFunctionWithName:[NSString stringWithUTF8String:gFuncName]]) {
        fprintf(stderr, "function %s missing\n", gFuncName); return 1; }

    if (!persist) { return doRun(NULL, NULL, 0); }

    printf("READY %s\n", [[gDev name] UTF8String]);
    fflush(stdout);
    char *line = NULL; size_t cap = 0; ssize_t len;
    while ((len = getline(&line, &cap, stdin)) > 0) {
        char *copy = strdup(line);
        handle_request(copy);
        free(copy);
    }
    free(line);
    return 0;
} }
