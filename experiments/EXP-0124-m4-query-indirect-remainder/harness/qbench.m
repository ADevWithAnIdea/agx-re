// EXP-0124 Group Q (P1.6 DRV-QUERY-01) harness. Public Metal API only + our own MSL
// (kernels/q_common.metal), compiled via newLibraryWithSource:. Apple binary
// introspection: NONE. Each process runs exactly ONE case (SAFETY: one case per
// process for this whole family, per dispatch instructions), selected by `--kind`
// with a JSON `--params` blob, and prints exactly one STATUS/DEVICE/OBSERVED text
// record to stdout (the EXP-0098 gddraws.m/xfbdraws.m protocol convention, reused
// here as our own prior authored code).
//
// Stdout protocol (consumed by harness/run.py):
//   STATUS OK | ALLOC_FAIL | ALLOC_REJECTED | RESOLVE_NIL | CMDBUF_ERROR |
//          COMPILE_FAIL | FUNCTION_MISSING | PIPELINE_FAIL | EXCEPTION | HARNESS_CRASH
//   DEVICE <name>
//   OBSERVED <space-separated key=value fields, kind-specific>
//   TICKS <space-separated key=value RAW nanosecond/tick fields; NEVER read by the
//          gated-record path in run.py -- collected only into the nongated sibling>
// Exit status: 0 on STATUS OK (or any status run.py's dispatcher treats as a valid,
// informative negative result -- see run.py), 1 on a status that should not occur if
// the harness itself is correct (COMPILE_FAIL/FUNCTION_MISSING/PIPELINE_FAIL/
// HARNESS_CRASH/EXCEPTION).

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
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
    exit(1);
}

// ---------------------------------------------------------------------------
// JSON param helpers.
static NSDictionary *parseParams(const char *json) {
    NSData *d = [NSData dataWithBytes:json length:strlen(json)];
    NSError *err = nil;
    id obj = [NSJSONSerialization JSONObjectWithData:d options:0 error:&err];
    if (!obj || ![obj isKindOfClass:[NSDictionary class]]) fail("HARNESS_CRASH", "bad --params json", err);
    return obj;
}
static long long pint(NSDictionary *p, NSString *k, long long defv) {
    id v = p[k];
    if (!v) return defv;
    return [v longLongValue];
}
static NSString *pstr(NSDictionary *p, NSString *k, NSString *defv) {
    id v = p[k];
    if (!v) return defv;
    return v;
}

// ---------------------------------------------------------------------------
static NSString *readFile(const char *path) {
    NSError *err = nil;
    NSString *s = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:path]
                                             encoding:NSUTF8StringEncoding error:&err];
    if (!s) fail("COMPILE_FAIL", "read source", err);
    return s;
}
static id<MTLLibrary> compileLib(id<MTLDevice> dev, const char *path) {
    NSError *err = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:readFile(path) options:[MTLCompileOptions new] error:&err];
    if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
    return lib;
}
static id<MTLFunction> fn(id<MTLLibrary> lib, const char *name) {
    id<MTLFunction> f = [lib newFunctionWithName:[NSString stringWithUTF8String:name]];
    if (!f) fail("FUNCTION_MISSING", name, nil);
    return f;
}
static int finishCB(id<MTLCommandBuffer> cb) {
    [cb waitUntilCompleted];
    return cb.status == MTLCommandBufferStatusError ? 1 : 0;
}

static id<MTLTexture> makeTarget(id<MTLDevice> dev, int w, int h) {
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:w height:h mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    td.storageMode = MTLStorageModeShared;
    return [dev newTextureWithDescriptor:td];
}
static MTLRenderPassDescriptor *dummyPass(id<MTLTexture> t) {
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture = t;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    return rp;
}
// M4 only supports MTLCounterSamplingPointAtStageBoundary (confirmed empirically by
// q_caps AND by the fact that `sampleCountersInBuffer:atSampleIndex:withBarrier:` --
// the per-draw/per-dispatch/per-blit-command encoder-level API -- hits a hard,
// UNCATCHABLE process-aborting assertion on this device family:
//   "-[AGXG16GFamilyBlitContext sampleCountersInBuffer:atSampleIndex:withBarrier:]:812:
//    failed assertion `... not supported on this device'"
// This is itself a first-class negative finding (see RESULTS.md); every helper below
// uses the ONLY working mechanism instead: pass-descriptor-level
// startOfEncoderSampleIndex/endOfEncoderSampleIndex sample-buffer attachments.
static id<MTLComputeCommandEncoder> computeEncSampled(id<MTLCommandBuffer> cb,
                                                       NSArray<id<MTLCounterSampleBuffer>> *bufs,
                                                       BOOL sampleEnd) {
    MTLComputePassDescriptor *pd = [MTLComputePassDescriptor computePassDescriptor];
    for (NSUInteger i = 0; i < bufs.count; i++) {
        pd.sampleBufferAttachments[i].sampleBuffer = bufs[i];
        pd.sampleBufferAttachments[i].startOfEncoderSampleIndex = 0;
        pd.sampleBufferAttachments[i].endOfEncoderSampleIndex = sampleEnd ? 1 : MTLCounterDontSample;
    }
    return [cb computeCommandEncoderWithDescriptor:pd];
}
// A totally empty encoder (sample-buffer attachments but zero actual encoded
// commands) was empirically found NOT to reach its stage-boundary HW sample point
// at all on M4 -- both start/end samples read back as untouched-zero, not a real
// timestamp and not MTLCounterErrorValue (see RESULTS.md "empty encoder" finding).
// Every blit-only sampled encoder below therefore issues one trivial real command
// (a 1-byte fillBuffer:) so the stage-boundary sample points are genuinely reached.
static void touchBlit(id<MTLDevice> dev, id<MTLBlitCommandEncoder> be) {
    static id<MTLBuffer> dummy = nil;
    if (!dummy) dummy = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
    [be fillBuffer:dummy range:NSMakeRange(0,1) value:0];
}

static id<MTLBlitCommandEncoder> blitEncSampled(id<MTLCommandBuffer> cb,
                                                 NSArray<id<MTLCounterSampleBuffer>> *bufs,
                                                 NSArray<NSNumber *> *startIdx,
                                                 NSArray<NSNumber *> *endIdx) {
    MTLBlitPassDescriptor *pd = [MTLBlitPassDescriptor blitPassDescriptor];
    for (NSUInteger i = 0; i < bufs.count; i++) {
        pd.sampleBufferAttachments[i].sampleBuffer = bufs[i];
        pd.sampleBufferAttachments[i].startOfEncoderSampleIndex = startIdx[i].unsignedIntegerValue;
        pd.sampleBufferAttachments[i].endOfEncoderSampleIndex = endIdx[i].unsignedIntegerValue;
    }
    return [cb blitCommandEncoderWithDescriptor:pd];
}

static id<MTLRenderPipelineState> buildFullscreenPSO(id<MTLDevice> dev, id<MTLLibrary> lib,
                                                      const char *vfn, const char *ffn) {
    NSError *err = nil;
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = fn(lib, vfn);
    pd.fragmentFunction = fn(lib, ffn);
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if (!pso) fail("PIPELINE_FAIL", "render PSO", err);
    return pso;
}

#define VIEWW 64
#define VIEWH 64
#define PIXN (VIEWW*VIEWH)

// ===========================================================================
// q_caps -- device counter-set / sampling-point census. No GPU work performed
// beyond one benign marker dispatch for sanity; this is a capability query.
static int run_q_caps(id<MTLDevice> dev, id<MTLCommandQueue> q) {
    NSMutableString *setsOut = [NSMutableString string];
    NSMutableString *hasStat = [NSMutableString string];
    for (id<MTLCounterSet> cs in dev.counterSets) {
        [setsOut appendFormat:@"%@,", cs.name];
        if ([cs.name isEqualToString:MTLCommonCounterSetStatistic]) {
            NSMutableString *names = [NSMutableString string];
            for (id<MTLCounter> c in cs.counters) [names appendFormat:@"%@|", c.name];
            [hasStat appendFormat:@"%@", names];
        }
    }
    BOOL supStage = [dev supportsCounterSampling:MTLCounterSamplingPointAtStageBoundary];
    BOOL supDraw  = [dev supportsCounterSampling:MTLCounterSamplingPointAtDrawBoundary];
    BOOL supDisp  = [dev supportsCounterSampling:MTLCounterSamplingPointAtDispatchBoundary];
    BOOL supTile  = [dev supportsCounterSampling:MTLCounterSamplingPointAtTileDispatchBoundary];
    BOOL supBlit  = [dev supportsCounterSampling:MTLCounterSamplingPointAtBlitBoundary];

    MTLTimestamp cpu0=0, gpu0=0;
    [dev sampleTimestamps:&cpu0 gpuTimestamp:&gpu0];

    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED counterSets=%s hasStatisticSet=%d statisticCounters=%s "
           "supStage=%d supDraw=%d supDispatch=%d supTile=%d supBlit=%d\n",
           setsOut.length ? [setsOut UTF8String] : "(none)",
           hasStat.length > 0,
           hasStat.length ? [hasStat UTF8String] : "(n/a)",
           supStage, supDraw, supDisp, supTile, supBlit);
    printf("TICKS cpu0=%llu gpu0=%llu\n", cpu0, gpu0);
    return 0;
}

// ===========================================================================
// q_alloc_sweep / q_alloc_mode -- allocation boundary mapping.
static MTLStorageMode storageModeFromStr(NSString *s) {
    if ([s isEqualToString:@"shared"]) return MTLStorageModeShared;
    if ([s isEqualToString:@"private"]) return MTLStorageModePrivate;
    if ([s isEqualToString:@"managed"]) return MTLStorageModeManaged;
    return MTLStorageModeShared;
}
static int run_q_alloc_sweep(id<MTLDevice> dev, NSDictionary *p) {
    NSUInteger sampleCount = (NSUInteger)pint(p, @"sampleCount", 1);
    MTLStorageMode mode = storageModeFromStr(pstr(p, @"storageMode", @"shared"));
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set on device", nil);

    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts;
    d.storageMode = mode;
    d.sampleCount = sampleCount;
    NSError *err = nil;
    id<MTLCounterSampleBuffer> sb = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!sb) {
        emit_status("ALLOC_REJECTED");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED requestedSampleCount=%llu storageMode=%s allocated=0 errCode=%ld\n",
               (unsigned long long)sampleCount, [pstr(p,@"storageMode",@"shared") UTF8String],
               (long)err.code);
        return 0;
    }
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED requestedSampleCount=%llu storageMode=%s allocated=1 readbackSampleCount=%llu\n",
           (unsigned long long)sampleCount, [pstr(p,@"storageMode",@"shared") UTF8String],
           (unsigned long long)sb.sampleCount);
    return 0;
}

static int run_q_alloc_mode(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, NSDictionary *p) {
    MTLStorageMode mode = storageModeFromStr(pstr(p, @"storageMode", @"shared"));
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set on device", nil);
    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts; d.storageMode = mode; d.sampleCount = 4;
    NSError *err = nil;
    id<MTLCounterSampleBuffer> sb = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!sb) {
        emit_status("ALLOC_REJECTED");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED storageMode=%s allocated=0 resolvedOk=0 errCode=%ld\n",
               [pstr(p,@"storageMode",@"shared") UTF8String], (long)err.code);
        return 0;
    }
    // Try to sample+resolve so we can see whether resolveCounterRange: on a
    // non-Shared sample buffer crashes, throws, or returns nil (H-Q3/private path).
    // Uses the ONLY supported sampling mechanism on this device (stage-boundary via
    // pass-descriptor attachment; see computeEncSampled/blitEncSampled comment).
    id<MTLCommandQueue> queue = q ?: [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLBlitCommandEncoder> be = blitEncSampled(cb, @[sb], @[@0], @[@(MTLCounterDontSample)]);
    touchBlit(dev, be);
    [be endEncoding];
    [cb commit];
    if (finishCB(cb)) {
        emit_status("CMDBUF_ERROR");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED storageMode=%s allocated=1 sampleCmdOk=0\n", [pstr(p,@"storageMode",@"shared") UTF8String]);
        return 1;
    }
    NSData *resolved = nil;
    BOOL threw = NO;
    @try {
        resolved = [sb resolveCounterRange:NSMakeRange(0,1)];
    } @catch (NSException *e) {
        threw = YES;
    }
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED storageMode=%s allocated=1 resolveThrew=%d resolveNil=%d\n",
           [pstr(p,@"storageMode",@"shared") UTF8String], threw, resolved == nil);
    return 0;
}

// ===========================================================================
// q_avail -- MTLCounterErrorValue sentinel across the command-buffer lifecycle.
static int run_q_avail_impl(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, NSDictionary *p) {
    NSString *point = pstr(p, @"point", @"post_completed");
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set", nil);
    NSError *err = nil;
    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts; d.storageMode = MTLStorageModeShared; d.sampleCount = 2;
    id<MTLCounterSampleBuffer> sb = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!sb) fail("ALLOC_FAIL", "counter sample buffer", err);

    if ([point isEqualToString:@"pre_commit"]) {
        NSData *resolved = [sb resolveCounterRange:NSMakeRange(0,2)];
        const uint64_t *vals = resolved ? (const uint64_t *)resolved.bytes : NULL;
        emit_status("OK");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED point=pre_commit resolvedNil=%d v0IsError=%d v1IsError=%d\n",
               resolved == nil,
               vals ? (int)(vals[0] == MTLCounterErrorValue) : -1,
               vals ? (int)(vals[1] == MTLCounterErrorValue) : -1);
        printf("TICKS v0=%llu v1=%llu\n", vals ? vals[0] : 0, vals ? vals[1] : 0);
        return 0;
    }

    id<MTLComputePipelineState> spinPSO = [dev newComputePipelineStateWithFunction:fn(lib, "k_spin") error:&err];
    if (!spinPSO) fail("PIPELINE_FAIL", "spin PSO", err);
    id<MTLBuffer> outBuf = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
    // Calibrated small enough to comfortably avoid any GPU command-timeout watchdog
    // (400,000,000 iterations was observed at build time to occasionally trigger a
    // CMDBUF_ERROR on this device -- see PROGRESS.md) while still being far from
    // instant, so `[cb commit]` reliably returns before the dispatch has finished.
    uint32_t iters = 3000000u;
    id<MTLBuffer> itersBuf = [dev newBufferWithBytes:&iters length:4 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    // Stage-boundary sampling: index 0 = start of this compute encoder, index 1 =
    // end of this compute encoder (the only supported sampling points on M4;
    // brackets the single spin dispatch below).
    id<MTLComputeCommandEncoder> ce = computeEncSampled(cb, @[sb], YES);
    [ce setComputePipelineState:spinPSO];
    [ce setBuffer:outBuf offset:0 atIndex:0];
    [ce setBuffer:itersBuf offset:0 atIndex:1];
    [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];

    if ([point isEqualToString:@"post_commit_unwaited"]) {
        [cb commit];
        // Poll status without waiting; capture the resolve at the first observed
        // non-completed status (or immediately if already scheduled-but-not-done).
        int sawNonCompleted = 0;
        MTLCommandBufferStatus st = cb.status;
        if (st != MTLCommandBufferStatusCompleted) sawNonCompleted = 1;
        NSData *resolved = [sb resolveCounterRange:NSMakeRange(0,2)];
        const uint64_t *vals = resolved ? (const uint64_t *)resolved.bytes : NULL;
        MTLCommandBufferStatus stAfter = cb.status;
        [cb waitUntilCompleted]; // drain before process exit; not timed
        int err2 = cb.status == MTLCommandBufferStatusError;
        emit_status(err2 ? "CMDBUF_ERROR" : "OK");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED point=post_commit_unwaited sawNonCompletedAtResolve=%d "
               "statusAtResolve=%ld statusAfterResolve=%ld resolvedNil=%d v0IsError=%d v1IsError=%d\n",
               sawNonCompleted, (long)st, (long)stAfter, resolved == nil,
               vals ? (int)(vals[0] == MTLCounterErrorValue) : -1,
               vals ? (int)(vals[1] == MTLCounterErrorValue) : -1);
        printf("TICKS v0=%llu v1=%llu\n", vals ? vals[0] : 0, vals ? vals[1] : 0);
        return 0;
    }

    // post_completed
    [cb commit];
    [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "spin cb", cb.error);
    NSData *resolved = [sb resolveCounterRange:NSMakeRange(0,2)];
    const uint64_t *vals = resolved ? (const uint64_t *)resolved.bytes : NULL;
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED point=post_completed resolvedNil=%d v0IsError=%d v1IsError=%d v1GTv0=%d\n",
           resolved == nil,
           vals ? (int)(vals[0] == MTLCounterErrorValue) : -1,
           vals ? (int)(vals[1] == MTLCounterErrorValue) : -1,
           vals ? (int)(vals[1] > vals[0]) : -1);
    printf("TICKS v0=%llu v1=%llu\n", vals ? vals[0] : 0, vals ? vals[1] : 0);
    return 0;
}

// ===========================================================================
// q_reset_idempotent / q_reset_reuse
static int run_q_reset_idempotent(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib) {
    NSError *err = nil;
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set", nil);
    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts; d.storageMode = MTLStorageModeShared; d.sampleCount = 1;
    id<MTLCounterSampleBuffer> sb = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!sb) fail("ALLOC_FAIL", "sb", err);
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLBlitCommandEncoder> be = blitEncSampled(cb, @[sb], @[@0], @[@(MTLCounterDontSample)]);
    touchBlit(dev, be);
    [be endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);
    NSData *r1 = [sb resolveCounterRange:NSMakeRange(0,1)];
    NSData *r2 = [sb resolveCounterRange:NSMakeRange(0,1)];
    BOOL eq = r1 && r2 && [r1 isEqualToData:r2];
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED resolveIdempotent=%d\n", eq);
    uint64_t v1 = r1 ? *(const uint64_t*)r1.bytes : 0;
    uint64_t v2 = r2 ? *(const uint64_t*)r2.bytes : 0;
    printf("TICKS v1=%llu v2=%llu\n", v1, v2);
    return 0;
}

static int run_q_reset_reuse(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib) {
    NSError *err = nil;
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set", nil);
    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts; d.storageMode = MTLStorageModeShared; d.sampleCount = 1;
    id<MTLCounterSampleBuffer> sb = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!sb) fail("ALLOC_FAIL", "sb", err);

    id<MTLCommandBuffer> cb1 = [q commandBuffer];
    id<MTLBlitCommandEncoder> be1 = blitEncSampled(cb1, @[sb], @[@0], @[@(MTLCounterDontSample)]);
    touchBlit(dev, be1);
    [be1 endEncoding];
    [cb1 commit]; [cb1 waitUntilCompleted];
    if (cb1.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb1", cb1.error);
    NSData *r1 = [sb resolveCounterRange:NSMakeRange(0,1)];
    uint64_t v1 = r1 ? *(const uint64_t*)r1.bytes : 0;

    // Sleep briefly so a re-sample's timestamp is guaranteed to differ from v1 if
    // (and only if) the second sample is a genuine fresh write, not a cached value.
    usleep(20000);

    id<MTLCommandBuffer> cb2 = [q commandBuffer];
    id<MTLBlitCommandEncoder> be2 = blitEncSampled(cb2, @[sb], @[@0], @[@(MTLCounterDontSample)]);
    touchBlit(dev, be2);
    [be2 endEncoding];
    [cb2 commit]; [cb2 waitUntilCompleted];
    if (cb2.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb2", cb2.error);
    NSData *r2 = [sb resolveCounterRange:NSMakeRange(0,1)];
    uint64_t v2 = r2 ? *(const uint64_t*)r2.bytes : 0;

    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED v2GTv1=%d v2NEv1=%d\n", v2 > v1, v2 != v1);
    printf("TICKS v1=%llu v2=%llu\n", v1, v2);
    return 0;
}

// ===========================================================================
// q_copy_match / q_copy_oob -- GPU-side resolveCounters: vs CPU-side resolveCounterRange:
static int run_q_copy_match(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib) {
    NSError *err = nil;
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set", nil);
    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts; d.storageMode = MTLStorageModeShared; d.sampleCount = 4;
    id<MTLCounterSampleBuffer> sb = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!sb) fail("ALLOC_FAIL", "sb", err);

    id<MTLBuffer> dst = [dev newBufferWithLength:32 options:MTLResourceStorageModeShared];
    memset(dst.contents, 0xAB, 32);

    id<MTLCommandBuffer> cb = [q commandBuffer];
    // Stage-boundary sampling only gives start/end of an encoder (2 samples each);
    // use two successive blit encoders writing into disjoint index ranges [0,1] and
    // [2,3] of the SAME sample buffer to get 4 populated samples, then a third
    // (unsampled) blit encoder to perform the GPU-side resolve of the full range.
    id<MTLBlitCommandEncoder> be1 = blitEncSampled(cb, @[sb], @[@0], @[@1]);
    touchBlit(dev, be1);
    [be1 endEncoding];
    id<MTLBlitCommandEncoder> be2 = blitEncSampled(cb, @[sb], @[@2], @[@3]);
    touchBlit(dev, be2);
    [be2 endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    // Fully separate command buffer for the GPU-side resolve, after the sampling
    // CB has completed on the CPU side -- removes any same-CB in-flight-ordering
    // ambiguity from the comparison below.
    id<MTLCommandBuffer> cb2 = [q commandBuffer];
    id<MTLBlitCommandEncoder> be = [cb2 blitCommandEncoder];
    [be resolveCounters:sb inRange:NSMakeRange(0,4) destinationBuffer:dst destinationOffset:0];
    [be endEncoding];
    [cb2 commit]; [cb2 waitUntilCompleted];
    if (cb2.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb2", cb2.error);

    NSData *cpuResolved = [sb resolveCounterRange:NSMakeRange(0,4)];
    BOOL eq = cpuResolved && cpuResolved.length == 32 && memcmp(cpuResolved.bytes, dst.contents, 32) == 0;
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED gpuResolveMatchesCpuResolve=%d cpuLen=%lu\n", eq, cpuResolved ? (unsigned long)cpuResolved.length : 0);
    return 0;
}

// Deliberately reproduces the same-command-buffer ordering hazard discovered while
// building q_copy_match: a GPU-side resolveCounters: blit copy issued in a LATER
// blit encoder of the SAME command buffer as the sampling encoders is NOT reliably
// ordered after the stage-boundary counter writes -- it observes stale/zero data,
// even though CPU-side resolveCounterRange: (called after the whole CB completes)
// sees the correct values. This case exists specifically to make that hazard a
// first-class, reproducible, cross-run-gated result rather than a build-time aside.
static int run_q_copy_samecb_hazard(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib) {
    NSError *err = nil;
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set", nil);
    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts; d.storageMode = MTLStorageModeShared; d.sampleCount = 4;
    id<MTLCounterSampleBuffer> sb = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!sb) fail("ALLOC_FAIL", "sb", err);
    id<MTLBuffer> dst = [dev newBufferWithLength:32 options:MTLResourceStorageModeShared];
    memset(dst.contents, 0xAB, 32);

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLBlitCommandEncoder> be1 = blitEncSampled(cb, @[sb], @[@0], @[@1]);
    touchBlit(dev, be1);
    [be1 endEncoding];
    id<MTLBlitCommandEncoder> be2 = blitEncSampled(cb, @[sb], @[@2], @[@3]);
    touchBlit(dev, be2);
    [be2 endEncoding];
    // Same command buffer, later blit encoder: the hazard under test.
    id<MTLBlitCommandEncoder> be3 = [cb blitCommandEncoder];
    [be3 resolveCounters:sb inRange:NSMakeRange(0,4) destinationBuffer:dst destinationOffset:0];
    [be3 endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    NSData *cpuResolved = [sb resolveCounterRange:NSMakeRange(0,4)];
    const uint64_t *cpuv = cpuResolved ? (const uint64_t*)cpuResolved.bytes : NULL;
    const uint64_t *gpuv = (const uint64_t*)dst.contents;
    BOOL cpuAllNonzero = cpuv && cpuv[0] && cpuv[1] && cpuv[2] && cpuv[3];
    BOOL gpuAllZero = gpuv[0]==0 && gpuv[1]==0 && gpuv[2]==0 && gpuv[3]==0;
    BOOL match = cpuv && memcmp(cpuv, gpuv, 32) == 0;
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED sameCbCpuAllNonzero=%d sameCbGpuAllZero=%d sameCbMatch=%d\n",
           cpuAllNonzero, gpuAllZero, match);
    return 0;
}

static int run_q_copy_oob(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib) {
    NSError *err = nil;
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set", nil);
    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts; d.storageMode = MTLStorageModeShared; d.sampleCount = 4;
    id<MTLCounterSampleBuffer> sb = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!sb) fail("ALLOC_FAIL", "sb", err);
    // Range [2,8) exceeds sampleCount=4 -- probe CPU-side resolveCounterRange: OOB
    // behavior (documented to return nil / mark MTLCounterErrorValue on error,
    // per header; here we test the concrete outcome).
    NSData *resolved = nil;
    BOOL threw = NO;
    @try {
        resolved = [sb resolveCounterRange:NSMakeRange(2,6)];
    } @catch (NSException *e) { threw = YES; }
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED oobResolveThrew=%d oobResolveNil=%d oobResolveLen=%lu\n",
           threw, resolved == nil, resolved ? (unsigned long)resolved.length : 0);
    return 0;
}

// ===========================================================================
// q_simul -- concurrent counter sample buffers.
static int run_q_simul_two_in_encoder(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib) {
    NSError *err = nil;
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set", nil);
    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts; d.storageMode = MTLStorageModeShared; d.sampleCount = 2;
    id<MTLCounterSampleBuffer> a = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    id<MTLCounterSampleBuffer> b = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!a || !b) fail("ALLOC_FAIL", "sb a/b", err);

    id<MTLCommandBuffer> cb = [q commandBuffer];
    // Two DISTINCT counter sample buffers as two attachment slots (index 0 and 1
    // of sampleBufferAttachments) on the SAME single encoder -- the only way to
    // express ">1 concurrently-active counter sample buffer in one encoder" on a
    // stage-boundary-only device.
    id<MTLBlitCommandEncoder> be = blitEncSampled(cb, @[a,b], @[@0,@0], @[@1,@1]);
    touchBlit(dev, be);
    [be endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    NSData *ra = [a resolveCounterRange:NSMakeRange(0,2)];
    NSData *rb = [b resolveCounterRange:NSMakeRange(0,2)];
    const uint64_t *va = (const uint64_t*)ra.bytes, *vb = (const uint64_t*)rb.bytes;
    BOOL aOk = va[0] != MTLCounterErrorValue && va[1] != MTLCounterErrorValue && va[1] >= va[0];
    BOOL bOk = vb[0] != MTLCounterErrorValue && vb[1] != MTLCounterErrorValue && vb[1] >= vb[0];
    BOOL distinct = !(va[0]==vb[0] && va[1]==vb[1]); // independent buffers should not
                                                       // coincidentally read identical
                                                       // pairs unless truly simultaneous
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED aMonotonicNoError=%d bMonotonicNoError=%d distinctPairs=%d\n", aOk, bOk, distinct);
    printf("TICKS a0=%llu a1=%llu b0=%llu b1=%llu\n", va[0], va[1], vb[0], vb[1]);
    return 0;
}

static int run_q_simul_many_in_encoder(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, NSDictionary *p) {
    int n = (int)pint(p, @"n", 8);
    NSError *err = nil;
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set", nil);
    NSMutableArray<id<MTLCounterSampleBuffer>> *bufs = [NSMutableArray array];
    for (int i = 0; i < n; i++) {
        MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
        d.counterSet = ts; d.storageMode = MTLStorageModeShared; d.sampleCount = 1;
        id<MTLCounterSampleBuffer> sb = [dev newCounterSampleBufferWithDescriptor:d error:&err];
        if (!sb) { fail("ALLOC_FAIL", "sb[i]", err); }
        [bufs addObject:sb];
    }
    id<MTLCommandBuffer> cb = [q commandBuffer];
    NSMutableArray<NSNumber *> *starts = [NSMutableArray array], *ends = [NSMutableArray array];
    for (NSUInteger i = 0; i < bufs.count; i++) { [starts addObject:@0]; [ends addObject:@(MTLCounterDontSample)]; }
    id<MTLBlitCommandEncoder> be = blitEncSampled(cb, bufs, starts, ends);
    touchBlit(dev, be);
    [be endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    int cmdErr = cb.status == MTLCommandBufferStatusError;
    if (cmdErr) {
        emit_status("CMDBUF_ERROR");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED n=%d allOk=0\n", n);
        return 1;
    }
    int allOk = 1;
    for (id<MTLCounterSampleBuffer> sb in bufs) {
        NSData *r = [sb resolveCounterRange:NSMakeRange(0,1)];
        uint64_t v = r ? *(const uint64_t*)r.bytes : MTLCounterErrorValue;
        if (v == MTLCounterErrorValue) allOk = 0;
    }
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED n=%d allOk=%d\n", n, allOk);
    return 0;
}

static int run_q_simul_two_queues(id<MTLDevice> dev, id<MTLLibrary> lib) {
    NSError *err = nil;
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set", nil);
    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts; d.storageMode = MTLStorageModeShared; d.sampleCount = 2;
    id<MTLCounterSampleBuffer> a = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    id<MTLCounterSampleBuffer> b = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!a || !b) fail("ALLOC_FAIL", "sb a/b", err);
    id<MTLCommandQueue> q1 = [dev newCommandQueue];
    id<MTLCommandQueue> q2 = [dev newCommandQueue];

    id<MTLCommandBuffer> cb1 = [q1 commandBuffer];
    id<MTLBlitCommandEncoder> be1 = blitEncSampled(cb1, @[a], @[@0], @[@1]);
    touchBlit(dev, be1);
    [be1 endEncoding];

    id<MTLCommandBuffer> cb2 = [q2 commandBuffer];
    id<MTLBlitCommandEncoder> be2 = blitEncSampled(cb2, @[b], @[@0], @[@1]);
    touchBlit(dev, be2);
    [be2 endEncoding];

    [cb1 commit];
    [cb2 commit];
    [cb1 waitUntilCompleted];
    [cb2 waitUntilCompleted];
    int e1 = cb1.status == MTLCommandBufferStatusError;
    int e2 = cb2.status == MTLCommandBufferStatusError;
    if (e1 || e2) {
        emit_status("CMDBUF_ERROR");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED q1Err=%d q2Err=%d\n", e1, e2);
        return 1;
    }
    NSData *ra = [a resolveCounterRange:NSMakeRange(0,2)];
    NSData *rb = [b resolveCounterRange:NSMakeRange(0,2)];
    const uint64_t *va = (const uint64_t*)ra.bytes, *vb = (const uint64_t*)rb.bytes;
    BOOL aOk = va[0] != MTLCounterErrorValue && va[1] != MTLCounterErrorValue && va[1] >= va[0];
    BOOL bOk = vb[0] != MTLCounterErrorValue && vb[1] != MTLCounterErrorValue && vb[1] >= vb[0];
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED q1BufOk=%d q2BufOk=%d\n", aOk, bOk);
    printf("TICKS a0=%llu a1=%llu b0=%llu b1=%llu\n", va[0], va[1], vb[0], vb[1]);
    return 0;
}

// ===========================================================================
// q_occmode / q_occmode_zero -- occlusion counting vs boolean, overlap, zero coverage.
static int run_q_occmode(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, NSDictionary *p) {
    NSString *modeStr = pstr(p, @"mode", @"counting");
    int overlap = (int)pint(p, @"overlap", 1);
    MTLVisibilityResultMode mode = [modeStr isEqualToString:@"boolean"]
        ? MTLVisibilityResultModeBoolean : MTLVisibilityResultModeCounting;

    id<MTLRenderPipelineState> pso = buildFullscreenPSO(dev, lib, "v_fullscreen", "f_white");
    id<MTLTexture> tgt = makeTarget(dev, VIEWW, VIEWH);
    id<MTLBuffer> vis = [dev newBufferWithLength:8 options:MTLResourceStorageModeShared];
    memset(vis.contents, 0xCC, 8);

    id<MTLCommandBuffer> cb = [q commandBuffer];
    MTLRenderPassDescriptor *rp = dummyPass(tgt);
    rp.visibilityResultBuffer = vis;
    id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
    [re setRenderPipelineState:pso];
    [re setVisibilityResultMode:mode offset:0];
    for (int i = 0; i < overlap; i++) [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [re endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    uint64_t v = *(const uint64_t*)vis.contents;
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED mode=%s overlap=%d value=%llu expectedCountingIfNoDedup=%llu\n",
           [modeStr UTF8String], overlap, v, (uint64_t)(overlap * PIXN));
    return 0;
}

static int run_q_occmode_zero(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib) {
    id<MTLRenderPipelineState> pso = buildFullscreenPSO(dev, lib, "v_offscreen", "f_noop_out");
    id<MTLTexture> tgt = makeTarget(dev, VIEWW, VIEWH);
    id<MTLBuffer> vis = [dev newBufferWithLength:8 options:MTLResourceStorageModeShared];
    memset(vis.contents, 0xCC, 8);
    id<MTLCommandBuffer> cb = [q commandBuffer];
    MTLRenderPassDescriptor *rp = dummyPass(tgt);
    rp.visibilityResultBuffer = vis;
    id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
    [re setRenderPipelineState:pso];
    [re setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];
    [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [re endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);
    uint64_t v = *(const uint64_t*)vis.contents;
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED value=%llu\n", v);
    return 0;
}

// ===========================================================================
// q_occoverwrite -- same-offset reuse within one encoder.
static int run_q_occoverwrite(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, NSDictionary *p) {
    NSString *variant = pstr(p, @"variant", @"same_offset");
    id<MTLRenderPipelineState> pso = buildFullscreenPSO(dev, lib, "v_fullscreen", "f_white");
    id<MTLTexture> tgt = makeTarget(dev, VIEWW, VIEWH);
    id<MTLBuffer> vis = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    memset(vis.contents, 0xCC, 16);

    id<MTLCommandBuffer> cb = [q commandBuffer];
    MTLRenderPassDescriptor *rp = dummyPass(tgt);
    rp.visibilityResultBuffer = vis;
    id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
    [re setRenderPipelineState:pso];

    if ([variant isEqualToString:@"same_offset"]) {
        [re setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];
        [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [re setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];
        [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    } else if ([variant isEqualToString:@"disabled_between"]) {
        [re setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];
        [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [re setVisibilityResultMode:MTLVisibilityResultModeDisabled offset:0];
        [re setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];
        [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    } else { // distinct_offsets
        [re setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];
        [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [re setVisibilityResultMode:MTLVisibilityResultModeCounting offset:8];
        [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    }
    [re endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    uint64_t v0 = *(const uint64_t*)vis.contents;
    uint64_t v1 = *((const uint64_t*)vis.contents + 1);
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED variant=%s v0=%llu v1=%llu overwriteMatch=%d accumulateMatch=%d\n",
           [variant UTF8String], v0, v1,
           v0 == (uint64_t)PIXN, v0 == (uint64_t)(2*PIXN));
    return 0;
}

// ===========================================================================
// q_tick -- counter-heap timestamp vs public sampleTimestamps cross-check.
static int run_q_tick(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib) {
    NSError *err = nil;
    id<MTLCounterSet> ts = nil;
    for (id<MTLCounterSet> cs in dev.counterSets)
        if ([cs.name isEqualToString:MTLCommonCounterSetTimestamp]) { ts = cs; break; }
    if (!ts) fail("HARNESS_CRASH", "no timestamp counter set", nil);
    MTLCounterSampleBufferDescriptor *d = [MTLCounterSampleBufferDescriptor new];
    d.counterSet = ts; d.storageMode = MTLStorageModeShared; d.sampleCount = 1;
    id<MTLCounterSampleBuffer> sb = [dev newCounterSampleBufferWithDescriptor:d error:&err];
    if (!sb) fail("ALLOC_FAIL", "sb", err);

    MTLTimestamp cpuBefore=0, gpuBefore=0, cpuAfter=0, gpuAfter=0;
    [dev sampleTimestamps:&cpuBefore gpuTimestamp:&gpuBefore];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLBlitCommandEncoder> be = blitEncSampled(cb, @[sb], @[@0], @[@(MTLCounterDontSample)]);
    touchBlit(dev, be);
    [be endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    [dev sampleTimestamps:&cpuAfter gpuTimestamp:&gpuAfter];
    NSData *r = [sb resolveCounterRange:NSMakeRange(0,1)];
    uint64_t heapVal = r ? *(const uint64_t*)r.bytes : 0;

    int betweenBounds = (heapVal >= gpuBefore) && (heapVal <= gpuAfter);
    // Same order of magnitude as a sanity check (within 10x of the gpuAfter-gpuBefore
    // span order, generously bounded -- not a strict physical claim).
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED heapValBetweenPublicBounds=%d\n", betweenBounds);
    printf("TICKS cpuBefore=%llu gpuBefore=%llu cpuAfter=%llu gpuAfter=%llu heapVal=%llu\n",
           cpuBefore, gpuBefore, cpuAfter, gpuAfter, heapVal);
    return 0;
}

// ===========================================================================
int main(int argc, char *argv[]) {
    setvbuf(stdout, NULL, _IONBF, 0);
    @autoreleasepool {
        if (argc < 3) fail("HARNESS_CRASH", "usage: qbench <kind> <json params>", nil);
        const char *kind = argv[1];
        NSDictionary *p = parseParams(argv[2]);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
        id<MTLCommandQueue> q = [dev newCommandQueue];

        if (strcmp(kind, "q_caps") == 0) return run_q_caps(dev, q);
        if (strcmp(kind, "q_alloc_sweep") == 0) return run_q_alloc_sweep(dev, p);

        // Every remaining kind needs the compiled kernel library.
        id<MTLLibrary> lib = compileLib(dev, "kernels/q_common.metal");

        if (strcmp(kind, "q_alloc_mode") == 0) return run_q_alloc_mode(dev, q, lib, p);
        if (strcmp(kind, "q_avail") == 0) return run_q_avail_impl(dev, q, lib, p);
        if (strcmp(kind, "q_reset_idempotent") == 0) return run_q_reset_idempotent(dev, q, lib);
        if (strcmp(kind, "q_reset_reuse") == 0) return run_q_reset_reuse(dev, q, lib);
        if (strcmp(kind, "q_copy_match") == 0) return run_q_copy_match(dev, q, lib);
        if (strcmp(kind, "q_copy_samecb_hazard") == 0) return run_q_copy_samecb_hazard(dev, q, lib);
        if (strcmp(kind, "q_copy_oob") == 0) return run_q_copy_oob(dev, q, lib);
        if (strcmp(kind, "q_simul_two_in_encoder") == 0) return run_q_simul_two_in_encoder(dev, q, lib);
        if (strcmp(kind, "q_simul_many_in_encoder") == 0) return run_q_simul_many_in_encoder(dev, q, lib, p);
        if (strcmp(kind, "q_simul_two_queues") == 0) return run_q_simul_two_queues(dev, lib);
        if (strcmp(kind, "q_occmode") == 0) return run_q_occmode(dev, q, lib, p);
        if (strcmp(kind, "q_occmode_zero") == 0) return run_q_occmode_zero(dev, q, lib);
        if (strcmp(kind, "q_occoverwrite") == 0) return run_q_occoverwrite(dev, q, lib, p);
        if (strcmp(kind, "q_tick") == 0) return run_q_tick(dev, q, lib);

        fail("HARNESS_CRASH", "unknown --kind", nil);
        return 1;
    }
}
