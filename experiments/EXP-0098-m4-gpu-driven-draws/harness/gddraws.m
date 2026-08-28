// EXP-0098 Bundle H (GLPRE-A01/A02) authored public-Metal harness.
// Apple binary introspection: NONE. Clean-room: OWN-SHADER (kernels/h_chain.metal,
// kernels/h_icbrange.metal) compiled via the public newLibraryWithSource: runtime
// path + HW-PROBE (live M4 dispatch/readback). No native VDM/CDM grammar, no
// splicing, no assembler -- public Metal API surface only, per the addendum's
// own instruction.
//
// Families:
//   h_sync      -- one producer/consumer pair (compute writes vertex data +
//                   [indexed] draw args; a render draw consumes them) swept
//                   across 6 named synchronization strategies, including
//                   deliberately-unsynchronized and asymmetric-fence controls.
//   h_fields    -- fixed "encoder_order" (known-good) sync; sweeps individual
//                   MTLDraw[Indexed]PrimitivesIndirectArguments fields
//                   written by a compute kernel (GLPRE-A02 field legality).
//   h_icbrange  -- a compute kernel writes the MTLIndirectCommandBufferExecutionRange
//                   {location,length} record that executeCommandsInBuffer:
//                   indirectBuffer:indirectBufferOffset: consumes against a
//                   CPU-pre-encoded ICB (device-generated draw COUNT grammar).
//   h_icbmax    -- allocation-only census: largest maxCommandCount an ICB
//                   accepts (finite-resource mandate).
//
// Stdout protocol (text; one field per line), consumed by harness/run.py:
//   STATUS OK | COMPILE_FAIL | FUNCTION_MISSING | PIPELINE_FAIL | CMDBUF_ERROR |
//          ALLOC_FAIL | HARNESS_CRASH
//   DEVICE <name>
//   OBSERVED <space-separated key=value fields, family-specific>
// Exit status: 0 on STATUS OK, 1 otherwise.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static const uint32_t SENTINEL = 0xDEADBEEFu;

static void emit_status(const char *s) { printf("STATUS %s\n", s); }

static void fail(const char *status, const char *msg, NSError *err) {
    emit_status(status);
    if (err)      printf("ERROR %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    if (fflush(NULL) != 0) { perror("fflush"); }
    if (ferror(stdout)) { fprintf(stderr, "stdout error\n"); }
    exit(1);
}

static NSString *readFile(const char *path) {
    NSError *err = nil;
    NSString *s = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:path]
                                             encoding:NSUTF8StringEncoding error:&err];
    if (!s) fail("COMPILE_FAIL", "read source", err);
    return s;
}

static id<MTLLibrary> compileLib(id<MTLDevice> dev, const char *path) {
    NSError *err = nil;
    MTLCompileOptions *copts = [MTLCompileOptions new];
    [copts setFastMathEnabled:YES];
    id<MTLLibrary> lib = [dev newLibraryWithSource:readFile(path) options:copts error:&err];
    if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
    return lib;
}

static id<MTLFunction> fn(id<MTLLibrary> lib, const char *name) {
    id<MTLFunction> f = [lib newFunctionWithName:[NSString stringWithUTF8String:name]];
    if (!f) fail("FUNCTION_MISSING", name, nil);
    return f;
}

// ---------------------------------------------------------------------------
// Common render-pipeline builder for v_verify/f_noop against a given library.
static id<MTLRenderPipelineState> buildVerifyPSO(id<MTLDevice> dev, id<MTLLibrary> lib) {
    NSError *err = nil;
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = fn(lib, "v_verify");
    pd.fragmentFunction = fn(lib, "f_noop");
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    pd.supportIndirectCommandBuffers = YES;  // required for use via executeCommandsInBuffer:
                                              // (h_icbrange); harmless for the direct-draw paths.
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if (!pso) fail("PIPELINE_FAIL", "verify render PSO", err);
    return pso;
}

static MTLRenderPassDescriptor *dummyPass(id<MTLTexture> target) {
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture = target;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0);
    rp.colorAttachments[0].storeAction = MTLStoreActionDontCare;
    return rp;
}

static int finishCB(id<MTLCommandBuffer> cb, const char *label, NSError **errOut) {
    [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) {
        if (errOut) *errOut = cb.error;
        return 1;
    }
    return 0;
}

// ---------------------------------------------------------------------------
// family h_sync / h_fields shared types
typedef struct {
    uint32_t vertexCount, instanceCount, vertexStart, baseInstance;
} DrawArgsC;
typedef struct {
    uint32_t indexCount, instanceCount, indexStart; int32_t baseVertex; uint32_t baseInstance;
} DrawIndexedArgsC;

static void fillSentinelU32(void *p, size_t nbytes, uint32_t v) {
    uint32_t *w = (uint32_t *)p;
    for (size_t i = 0; i < nbytes / 4; ++i) w[i] = v;
}

// ---------------------------------------------------------------------------
static int run_h_sync(id<MTLDevice> dev, id<MTLCommandQueue> queue, id<MTLLibrary> lib,
                       BOOL indexed, const char *syncMode, unsigned n, uint32_t magicBase,
                       uint32_t spinIters) {
    NSError *err = nil;
    id<MTLComputePipelineState> producerPSO =
        [dev newComputePipelineStateWithFunction:fn(lib, indexed ? "producer_chain_indexed32" : "producer_chain")
                                            error:&err];
    if (!producerPSO) fail("PIPELINE_FAIL", "producer compute PSO", err);
    id<MTLRenderPipelineState> renderPSO = buildVerifyPSO(dev, lib);

    BOOL cpuBaseline = strcmp(syncMode, "cpu_baseline") == 0;
    BOOL sameCB       = strcmp(syncMode, "encoder_order") == 0 || strcmp(syncMode, "fence_sym") == 0;
    BOOL useFenceProd = strcmp(syncMode, "fence_sym") == 0 || strcmp(syncMode, "asym_producer") == 0;
    BOOL useFenceCons = strcmp(syncMode, "fence_sym") == 0 || strcmp(syncMode, "asym_consumer") == 0;
    BOOL untracked    = !cpuBaseline && strcmp(syncMode, "encoder_order") != 0;

    MTLResourceOptions opt = MTLResourceStorageModeShared |
        (untracked ? MTLResourceHazardTrackingModeUntracked : MTLResourceHazardTrackingModeTracked);

    id<MTLBuffer> vtxBuf  = [dev newBufferWithLength:n * 16 options:opt];
    id<MTLBuffer> idxBuf  = indexed ? [dev newBufferWithLength:n * 4 options:opt] : nil;
    id<MTLBuffer> argsBuf = [dev newBufferWithLength:indexed ? sizeof(DrawIndexedArgsC) : sizeof(DrawArgsC)
                                              options:opt];
    id<MTLBuffer> seenBuf = [dev newBufferWithLength:n * 16 options:MTLResourceStorageModeShared];
    id<MTLBuffer> vparamBuf = [dev newBufferWithLength:8 options:MTLResourceStorageModeShared];
    { uint32_t *vp = vparamBuf.contents; vp[0] = (uint32_t)n; vp[1] = 1u; }

    fillSentinelU32(vtxBuf.contents, vtxBuf.length, SENTINEL);
    fillSentinelU32(seenBuf.contents, seenBuf.length, SENTINEL);
    fillSentinelU32(argsBuf.contents, argsBuf.length, SENTINEL);
    if (idxBuf) fillSentinelU32(idxBuf.contents, idxBuf.length, 0xFFFFFFFFu);

    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                                                   width:1 height:1 mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
    id<MTLTexture> target = [dev newTextureWithDescriptor:td];

    if (cpuBaseline) {
        uint32_t *vw = vtxBuf.contents;
        for (unsigned i = 0; i < n; ++i) { vw[i*4]=magicBase+i; vw[i*4+1]=i; vw[i*4+2]=0xA5A5A5A5u; vw[i*4+3]=0; }
        if (indexed) {
            uint32_t *iw = idxBuf.contents;
            for (unsigned i = 0; i < n; ++i) iw[i] = i;
            DrawIndexedArgsC *a = argsBuf.contents;
            a->indexCount=n; a->instanceCount=1; a->indexStart=0; a->baseVertex=0; a->baseInstance=0;
        } else {
            DrawArgsC *a = argsBuf.contents;
            a->vertexCount=n; a->instanceCount=1; a->vertexStart=0; a->baseInstance=0;
        }
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLRenderCommandEncoder> renc = [cb renderCommandEncoderWithDescriptor:dummyPass(target)];
        [renc setRenderPipelineState:renderPSO];
        [renc setVertexBuffer:vtxBuf offset:0 atIndex:0];
        [renc setVertexBuffer:seenBuf offset:0 atIndex:1];
        [renc setVertexBuffer:vparamBuf offset:0 atIndex:2];
        if (indexed)
            [renc drawIndexedPrimitives:MTLPrimitiveTypePoint indexType:MTLIndexTypeUInt32
                             indexBuffer:idxBuf indexBufferOffset:0
                          indirectBuffer:argsBuf indirectBufferOffset:0];
        else
            [renc drawPrimitives:MTLPrimitiveTypePoint indirectBuffer:argsBuf indirectBufferOffset:0];
        [renc endEncoding];
        [cb commit];
        NSError *cberr = nil;
        if (finishCB(cb, "h_sync_cpu_baseline", &cberr)) { fail("CMDBUF_ERROR", "cpu_baseline", cberr); }
    } else {
        id<MTLFence> fence = (useFenceProd || useFenceCons) ? [dev newFence] : nil;

        id<MTLCommandBuffer> cbA = [queue commandBuffer];
        id<MTLComputeCommandEncoder> cenc = [cbA computeCommandEncoder];
        [cenc setComputePipelineState:producerPSO];
        [cenc setBuffer:vtxBuf offset:0 atIndex:0];
        if (indexed) {
            [cenc setBuffer:idxBuf offset:0 atIndex:1];
            [cenc setBuffer:argsBuf offset:0 atIndex:2];
            struct { uint32_t n, magicBase, idxBase, indexCount, instanceCount, indexStart; int32_t baseVertex; uint32_t baseInstance, restartAt, spinIters; } p =
                { (uint32_t)n, magicBase, 0, (uint32_t)n, 1, 0, 0, 0, 0xFFFFFFFFu, spinIters };
            id<MTLBuffer> pbuf = [dev newBufferWithLength:sizeof(p) options:MTLResourceStorageModeShared];
            memcpy(pbuf.contents, &p, sizeof(p));
            [cenc setBuffer:pbuf offset:0 atIndex:3];
            [cenc dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(MIN(n,64u),1,1)];
        } else {
            [cenc setBuffer:argsBuf offset:0 atIndex:1];
            struct { uint32_t n, magicBase, vertexCount, instanceCount, vertexStart, baseInstance, spinIters; } p =
                { (uint32_t)n, magicBase, (uint32_t)n, 1, 0, 0, spinIters };
            id<MTLBuffer> pbuf = [dev newBufferWithLength:sizeof(p) options:MTLResourceStorageModeShared];
            memcpy(pbuf.contents, &p, sizeof(p));
            [cenc setBuffer:pbuf offset:0 atIndex:2];
            [cenc dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(MIN(n,64u),1,1)];
        }
        if (useFenceProd) [cenc updateFence:fence];
        [cenc endEncoding];

        id<MTLCommandBuffer> cbB = sameCB ? cbA : [queue commandBuffer];
        id<MTLRenderCommandEncoder> renc = [cbB renderCommandEncoderWithDescriptor:dummyPass(target)];
        if (useFenceCons) [renc waitForFence:fence beforeStages:MTLRenderStageVertex];
        [renc setRenderPipelineState:renderPSO];
        [renc setVertexBuffer:vtxBuf offset:0 atIndex:0];
        [renc setVertexBuffer:seenBuf offset:0 atIndex:1];
        [renc setVertexBuffer:vparamBuf offset:0 atIndex:2];
        if (indexed)
            [renc drawIndexedPrimitives:MTLPrimitiveTypePoint indexType:MTLIndexTypeUInt32
                             indexBuffer:idxBuf indexBufferOffset:0
                          indirectBuffer:argsBuf indirectBufferOffset:0];
        else
            [renc drawPrimitives:MTLPrimitiveTypePoint indirectBuffer:argsBuf indirectBufferOffset:0];
        [renc endEncoding];

        [cbA commit];
        if (!sameCB) [cbB commit];   // committed back-to-back, no CPU wait between -- the
                                     // deliberately-unsynchronized/asymmetric pattern.
        NSError *cberrA = nil, *cberrB = nil;
        int badA = finishCB(cbA, "h_sync_A", &cberrA);
        int badB = sameCB ? 0 : finishCB(cbB, "h_sync_B", &cberrB);
        if (badA || badB) fail("CMDBUF_ERROR", "h_sync", badA ? cberrA : cberrB);
    }

    uint32_t *seen = seenBuf.contents;
    unsigned n_correct = 0, n_stale = 0, n_other = 0, n_z_wrong = 0;
    for (unsigned i = 0; i < n; ++i) {
        uint32_t x = seen[i*4+0], z = seen[i*4+2];
        if (z != i) n_z_wrong++;
        if (x == magicBase + i) n_correct++;
        else if (x == SENTINEL) n_stale++;
        else n_other++;
    }
    printf("OBSERVED n=%u n_correct=%u n_stale=%u n_other=%u n_z_wrong=%u\n",
           n, n_correct, n_stale, n_other, n_z_wrong);
    emit_status("OK");
    return 0;
}

// ---------------------------------------------------------------------------
static int run_h_fields(id<MTLDevice> dev, id<MTLCommandQueue> queue, id<MTLLibrary> lib,
                         BOOL indexed, unsigned cap, uint32_t magicBase,
                         uint32_t vertexCount, uint32_t instanceCount, uint32_t vertexStart,
                         uint32_t baseInstance, int32_t baseVertex, uint32_t idxBase,
                         int idxBits, uint32_t restartAt, unsigned indirectOffsetBytes) {
    NSError *err = nil;
    id<MTLComputePipelineState> producerPSO;
    if (indexed)
        producerPSO = [dev newComputePipelineStateWithFunction:
            fn(lib, idxBits == 16 ? "producer_chain_indexed16" : "producer_chain_indexed32") error:&err];
    else
        producerPSO = [dev newComputePipelineStateWithFunction:fn(lib, "producer_chain") error:&err];
    if (!producerPSO) fail("PIPELINE_FAIL", "producer compute PSO", err);
    id<MTLRenderPipelineState> renderPSO = buildVerifyPSO(dev, lib);

    id<MTLBuffer> vtxBuf = [dev newBufferWithLength:cap * 16 options:MTLResourceStorageModeShared];
    id<MTLBuffer> idxBuf = indexed ? [dev newBufferWithLength:cap * (idxBits/8) options:MTLResourceStorageModeShared] : nil;
    size_t argsSz = indexed ? sizeof(DrawIndexedArgsC) : sizeof(DrawArgsC);
    // Deliberately over-allocate the args buffer and place the record at
    // `indirectOffsetBytes` so misaligned-offset behavior can be tested
    // without touching adjacent guard bytes.
    id<MTLBuffer> argsBuf = [dev newBufferWithLength:indirectOffsetBytes + argsSz + 64
                                              options:MTLResourceStorageModeShared];
    // [[instance_id]] is the ABSOLUTE instance identifier (baseInstance-inclusive) --
    // seen[] must be sized to cover [0, baseInstance+instanceCount), not just
    // [0, instanceCount) (build-time finding; see PRE_REGISTRATION.md).
    unsigned instanceCap = baseInstance + MAX(instanceCount, 1u);
    id<MTLBuffer> seenBuf = [dev newBufferWithLength:(size_t)cap * instanceCap * 16 options:MTLResourceStorageModeShared];
    id<MTLBuffer> vparamBuf = [dev newBufferWithLength:8 options:MTLResourceStorageModeShared];
    { uint32_t *vp = vparamBuf.contents; vp[0] = (uint32_t)cap; vp[1] = (uint32_t)instanceCap; }

    fillSentinelU32(vtxBuf.contents, vtxBuf.length, SENTINEL);
    fillSentinelU32(seenBuf.contents, seenBuf.length, SENTINEL);
    fillSentinelU32(argsBuf.contents, argsBuf.length, SENTINEL);
    if (idxBuf) memset(idxBuf.contents, 0xFF, idxBuf.length);

    id<MTLCommandBuffer> cbA = [queue commandBuffer];
    id<MTLComputeCommandEncoder> cenc = [cbA computeCommandEncoder];
    [cenc setComputePipelineState:producerPSO];
    [cenc setBuffer:vtxBuf offset:0 atIndex:0];
    if (indexed) {
        [cenc setBuffer:idxBuf offset:0 atIndex:1];
        [cenc setBuffer:argsBuf offset:indirectOffsetBytes atIndex:2];
        struct { uint32_t n, magicBase, idxBase, indexCount, instanceCount, indexStart; int32_t baseVertex; uint32_t baseInstance, restartAt; } p =
            { (uint32_t)cap, magicBase, idxBase, vertexCount, instanceCount, vertexStart, baseVertex, baseInstance, restartAt };
        id<MTLBuffer> pbuf = [dev newBufferWithLength:sizeof(p) options:MTLResourceStorageModeShared];
        memcpy(pbuf.contents, &p, sizeof(p));
        [cenc setBuffer:pbuf offset:0 atIndex:3];
    } else {
        [cenc setBuffer:argsBuf offset:indirectOffsetBytes atIndex:1];
        struct { uint32_t n, magicBase, vertexCount, instanceCount, vertexStart, baseInstance; } p =
            { (uint32_t)cap, magicBase, vertexCount, instanceCount, vertexStart, baseInstance };
        id<MTLBuffer> pbuf = [dev newBufferWithLength:sizeof(p) options:MTLResourceStorageModeShared];
        memcpy(pbuf.contents, &p, sizeof(p));
        [cenc setBuffer:pbuf offset:0 atIndex:2];
    }
    [cenc dispatchThreads:MTLSizeMake(cap,1,1) threadsPerThreadgroup:MTLSizeMake(MIN(cap,64u),1,1)];
    [cenc endEncoding];

    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                                                   width:1 height:1 mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
    id<MTLTexture> target = [dev newTextureWithDescriptor:td];
    id<MTLRenderCommandEncoder> renc = [cbA renderCommandEncoderWithDescriptor:dummyPass(target)];
    [renc setRenderPipelineState:renderPSO];
    [renc setVertexBuffer:vtxBuf offset:0 atIndex:0];
    [renc setVertexBuffer:seenBuf offset:0 atIndex:1];
    [renc setVertexBuffer:vparamBuf offset:0 atIndex:2];
    if (indexed)
        [renc drawIndexedPrimitives:MTLPrimitiveTypePoint
                           indexType:(idxBits==16?MTLIndexTypeUInt16:MTLIndexTypeUInt32)
                         indexBuffer:idxBuf indexBufferOffset:0
                      indirectBuffer:argsBuf indirectBufferOffset:indirectOffsetBytes];
    else
        [renc drawPrimitives:MTLPrimitiveTypePoint indirectBuffer:argsBuf indirectBufferOffset:indirectOffsetBytes];
    [renc endEncoding];
    [cbA commit];
    NSError *cberr = nil;
    if (finishCB(cbA, "h_fields", &cberr)) { fail("CMDBUF_ERROR", "h_fields", cberr); }

    uint32_t *seen = seenBuf.contents;
    unsigned n_invoked = 0, n_correct = 0;
    uint32_t minVid = 0xFFFFFFFFu, maxVid = 0, minIid = 0xFFFFFFFFu, maxIid = 0;
    // An invocation always overwrites .z (=raw vid) and .w (=raw iid) even
    // under a stale .x read, so any slot whose four words are no longer all
    // == SENTINEL was genuinely touched by a real vertex-stage invocation.
    for (unsigned iidx = 0; iidx < instanceCap; ++iidx) {
        for (unsigned slot = 0; slot < cap; ++slot) {
            uint32_t *rec = seen + (iidx*cap + slot) * 4;
            BOOL touched = !(rec[0]==SENTINEL && rec[1]==SENTINEL && rec[2]==SENTINEL && rec[3]==SENTINEL);
            if (!touched) continue;
            n_invoked++;
            uint32_t rawVid = rec[2], rawIid = rec[3];
            if (rawVid < minVid) minVid = rawVid;
            if (rawVid > maxVid) maxVid = rawVid;
            if (rawIid < minIid) minIid = rawIid;
            if (rawIid > maxIid) maxIid = rawIid;
            uint32_t expectedX = magicBase + slot; // slot == clamp(rawVid); iidx == clamp(rawIid)
            if (rec[0] == expectedX && rawIid == iidx) n_correct++;
        }
    }
    printf("OBSERVED cap=%u n_invoked=%u n_correct=%u minVid=%u maxVid=%u minIid=%u maxIid=%u\n",
           cap, n_invoked, n_correct, minVid == 0xFFFFFFFFu ? 0 : minVid, maxVid,
           minIid == 0xFFFFFFFFu ? 0 : minIid, maxIid);
    emit_status("OK");
    return 0;
}

// ---------------------------------------------------------------------------
static int run_h_icbrange(id<MTLDevice> dev, id<MTLCommandQueue> queue, id<MTLLibrary> lib,
                           unsigned maxCount, uint32_t location, uint32_t length,
                           unsigned writeLocation, unsigned writeLength) {
    NSError *err = nil;
    id<MTLComputePipelineState> producerPSO =
        [dev newComputePipelineStateWithFunction:fn(lib, "producer_icbrange") error:&err];
    if (!producerPSO) fail("PIPELINE_FAIL", "producer_icbrange PSO", err);
    id<MTLRenderPipelineState> renderPSO = buildVerifyPSO(dev, lib);

    MTLIndirectCommandBufferDescriptor *desc = [MTLIndirectCommandBufferDescriptor new];
    desc.commandTypes = MTLIndirectCommandTypeDraw;
    desc.inheritPipelineState = YES;
    desc.inheritBuffers = NO;
    desc.maxVertexBufferBindCount = 3;
    desc.maxFragmentBufferBindCount = 0;
    id<MTLIndirectCommandBuffer> icb = [dev newIndirectCommandBufferWithDescriptor:desc
        maxCommandCount:maxCount options:MTLResourceStorageModePrivate];
    if (!icb) fail("ALLOC_FAIL", "newIndirectCommandBufferWithDescriptor", nil);

    id<MTLBuffer> vtxBuf = [dev newBufferWithLength:maxCount * 16 options:MTLResourceStorageModeShared];
    id<MTLBuffer> seenBuf = [dev newBufferWithLength:maxCount * 16 options:MTLResourceStorageModeShared];
    id<MTLBuffer> vparamBuf = [dev newBufferWithLength:8 options:MTLResourceStorageModeShared];
    { uint32_t *vp = vparamBuf.contents; vp[0] = maxCount; vp[1] = 1u; }
    uint32_t *vw = vtxBuf.contents;
    for (unsigned i = 0; i < maxCount; ++i) { vw[i*4]=0xC0FFEE00u+i; vw[i*4+1]=i; vw[i*4+2]=0; vw[i*4+3]=0; }
    fillSentinelU32(seenBuf.contents, seenBuf.length, SENTINEL);

    for (unsigned i = 0; i < maxCount; ++i) {
        id<MTLIndirectRenderCommand> cmd = [icb indirectRenderCommandAtIndex:i];
        [cmd setVertexBuffer:vtxBuf offset:0 atIndex:0];
        [cmd setVertexBuffer:seenBuf offset:0 atIndex:1];
        [cmd setVertexBuffer:vparamBuf offset:0 atIndex:2];
        [cmd drawPrimitives:MTLPrimitiveTypePoint vertexStart:i vertexCount:1 instanceCount:1 baseInstance:0];
    }

    // The RANGE record consumed by executeCommandsInBuffer: is written by
    // producer_icbrange (a compute kernel), never CPU `contents`. writeLocation/
    // writeLength are the (possibly out-of-declared-bounds) values the KERNEL is
    // told to store; location/length below are unused when a range buffer drives
    // the call (kept for the --loc/--len single-shot CPU-encoded control case).
    id<MTLBuffer> rangeBuf = [dev newBufferWithLength:8 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cbA = [queue commandBuffer];
    id<MTLComputeCommandEncoder> cenc = [cbA computeCommandEncoder];
    [cenc setComputePipelineState:producerPSO];
    [cenc setBuffer:rangeBuf offset:0 atIndex:0];
    struct { uint32_t location, length; } p = { writeLocation, writeLength };
    id<MTLBuffer> pbuf = [dev newBufferWithLength:sizeof(p) options:MTLResourceStorageModeShared];
    memcpy(pbuf.contents, &p, sizeof(p));
    [cenc setBuffer:pbuf offset:0 atIndex:1];
    [cenc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [cenc endEncoding];

    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                                                   width:1 height:1 mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
    id<MTLTexture> target = [dev newTextureWithDescriptor:td];
    id<MTLRenderCommandEncoder> renc = [cbA renderCommandEncoderWithDescriptor:dummyPass(target)];
    [renc setRenderPipelineState:renderPSO];
    [renc executeCommandsInBuffer:icb indirectBuffer:rangeBuf indirectBufferOffset:0];
    [renc endEncoding];
    [cbA commit];
    NSError *cberr = nil;
    if (finishCB(cbA, "h_icbrange", &cberr)) { fail("CMDBUF_ERROR", "h_icbrange", cberr); }

    uint32_t *rangeOut = rangeBuf.contents;
    uint32_t *seen = seenBuf.contents;
    unsigned n_executed = 0;
    unsigned firstExecuted = 0xFFFFFFFFu, lastExecuted = 0;
    for (unsigned i = 0; i < maxCount; ++i) {
        BOOL touched = !(seen[i*4]==SENTINEL && seen[i*4+1]==SENTINEL && seen[i*4+2]==SENTINEL && seen[i*4+3]==SENTINEL);
        if (touched) { n_executed++; if (i<firstExecuted) firstExecuted=i; if (i>lastExecuted) lastExecuted=i; }
    }
    printf("OBSERVED maxCount=%u writeLocation=%u writeLength=%u rangeReadback_loc=%u rangeReadback_len=%u "
           "n_executed=%u firstExecuted=%u lastExecuted=%u\n",
           maxCount, writeLocation, writeLength, rangeOut[0], rangeOut[1],
           n_executed, firstExecuted==0xFFFFFFFFu?0:firstExecuted, lastExecuted);
    emit_status("OK");
    return 0;
}

// ---------------------------------------------------------------------------
static int run_h_icbmax(id<MTLDevice> dev, unsigned tryCount) {
    MTLIndirectCommandBufferDescriptor *desc = [MTLIndirectCommandBufferDescriptor new];
    desc.commandTypes = MTLIndirectCommandTypeDraw;
    desc.inheritPipelineState = YES;
    desc.inheritBuffers = YES;
    id<MTLIndirectCommandBuffer> icb = [dev newIndirectCommandBufferWithDescriptor:desc
        maxCommandCount:tryCount options:MTLResourceStorageModePrivate];
    printf("OBSERVED tryCount=%u alloc_ok=%d size_reported=%ld\n",
           tryCount, icb != nil, icb ? (long)icb.size : -1L);
    emit_status("OK");
    return 0;
}

// ---------------------------------------------------------------------------
enum { OPT_INDEXED=256, OPT_SYNC, OPT_N, OPT_MAGIC, OPT_CAP, OPT_VC, OPT_IC, OPT_VS, OPT_BI, OPT_BV,
       OPT_IDXBITS, OPT_IDXBASE, OPT_RESTARTAT, OPT_IOFF, OPT_MAXCOUNT, OPT_LOC, OPT_LEN,
       OPT_WLOC, OPT_WLEN, OPT_TRYCOUNT, OPT_SPIN };

static const struct option longOpts[] = {
    {"family",    required_argument, NULL, 'F'},
    {"indexed",   required_argument, NULL, OPT_INDEXED},
    {"sync",      required_argument, NULL, OPT_SYNC},
    {"n",         required_argument, NULL, OPT_N},
    {"magic",     required_argument, NULL, OPT_MAGIC},
    {"cap",       required_argument, NULL, OPT_CAP},
    {"vc",        required_argument, NULL, OPT_VC},
    {"ic",        required_argument, NULL, OPT_IC},
    {"vs",        required_argument, NULL, OPT_VS},
    {"bi",        required_argument, NULL, OPT_BI},
    {"bv",        required_argument, NULL, OPT_BV},
    {"idxbits",   required_argument, NULL, OPT_IDXBITS},
    {"idxbase",   required_argument, NULL, OPT_IDXBASE},
    {"restart-at",required_argument, NULL, OPT_RESTARTAT},
    {"ioff",      required_argument, NULL, OPT_IOFF},
    {"maxcount",  required_argument, NULL, OPT_MAXCOUNT},
    {"loc",       required_argument, NULL, OPT_LOC},
    {"len",       required_argument, NULL, OPT_LEN},
    {"wloc",      required_argument, NULL, OPT_WLOC},
    {"wlen",      required_argument, NULL, OPT_WLEN},
    {"trycount",  required_argument, NULL, OPT_TRYCOUNT},
    {"spin",      required_argument, NULL, OPT_SPIN},
    {NULL, 0, NULL, 0}
};

int main(int argc, char *argv[]) {
    setvbuf(stdout, NULL, _IONBF, 0);
    @autoreleasepool {
        const char *family = NULL, *syncMode = "encoder_order";
        int indexed = 0;
        unsigned n = 16, cap = 16, maxCount = 4, tryCount = 1024;
        uint32_t magicBase = 0xC0FFEE00u;
        uint32_t vc = 16, ic = 1, vs = 0, bi = 0, idxbase = 0, restartAt = 0xFFFFFFFFu;
        int32_t bv = 0;
        int idxbits = 32;
        unsigned ioff = 0, wloc = 0, wlen = 4;
        uint32_t spinIters = 0;
        uint32_t loc = 0, len = 4;
        int c;
        while ((c = getopt_long(argc, argv, "F:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'F': family = optarg; break;
                case OPT_INDEXED: indexed = (int)strtol(optarg, NULL, 0); break;
                case OPT_SYNC: syncMode = optarg; break;
                case OPT_N: n = (unsigned)strtoul(optarg, NULL, 0); break;
                case OPT_MAGIC: magicBase = (uint32_t)strtoul(optarg, NULL, 0); break;
                case OPT_CAP: cap = (unsigned)strtoul(optarg, NULL, 0); break;
                case OPT_VC: vc = (uint32_t)strtoul(optarg, NULL, 0); break;
                case OPT_IC: ic = (uint32_t)strtoul(optarg, NULL, 0); break;
                case OPT_VS: vs = (uint32_t)strtoul(optarg, NULL, 0); break;
                case OPT_BI: bi = (uint32_t)strtoul(optarg, NULL, 0); break;
                case OPT_BV: bv = (int32_t)strtol(optarg, NULL, 0); break;
                case OPT_IDXBITS: idxbits = (int)strtol(optarg, NULL, 0); break;
                case OPT_IDXBASE: idxbase = (uint32_t)strtoul(optarg, NULL, 0); break;
                case OPT_RESTARTAT: restartAt = (uint32_t)strtoul(optarg, NULL, 0); break;
                case OPT_IOFF: ioff = (unsigned)strtoul(optarg, NULL, 0); break;
                case OPT_MAXCOUNT: maxCount = (unsigned)strtoul(optarg, NULL, 0); break;
                case OPT_LOC: loc = (uint32_t)strtoul(optarg, NULL, 0); break;
                case OPT_LEN: len = (uint32_t)strtoul(optarg, NULL, 0); break;
                case OPT_WLOC: wloc = (unsigned)strtoul(optarg, NULL, 0); break;
                case OPT_WLEN: wlen = (unsigned)strtoul(optarg, NULL, 0); break;
                case OPT_TRYCOUNT: tryCount = (unsigned)strtoul(optarg, NULL, 0); break;
                case OPT_SPIN: spinIters = (uint32_t)strtoul(optarg, NULL, 0); break;
                default: fprintf(stderr, "usage: see header\n"); return 2;
            }
        }
        if (!family) fail("HARNESS_CRASH", "need --family", nil);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        id<MTLCommandQueue> queue = [dev newCommandQueue];

        if (strcmp(family, "h_icbmax") == 0) {
            return run_h_icbmax(dev, tryCount);
        }

        NSString *path = strcmp(family, "h_icbrange") == 0
            ? @"kernels/h_icbrange.metal" : @"kernels/h_chain.metal";
        id<MTLLibrary> lib = compileLib(dev, path.UTF8String);

        if (strcmp(family, "h_sync") == 0) {
            return run_h_sync(dev, queue, lib, indexed, syncMode, n, magicBase, spinIters);
        } else if (strcmp(family, "h_fields") == 0) {
            return run_h_fields(dev, queue, lib, indexed, cap, magicBase, vc, ic, vs, bi, bv,
                                 idxbase, idxbits, restartAt, ioff);
        } else if (strcmp(family, "h_icbrange") == 0) {
            return run_h_icbrange(dev, queue, lib, maxCount, loc, len, wloc, wlen);
        }
        fail("HARNESS_CRASH", "unknown --family", nil);
        return 1;
    }
}
