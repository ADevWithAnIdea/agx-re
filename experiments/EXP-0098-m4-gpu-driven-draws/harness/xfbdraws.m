// EXP-0098 Bundle I (GLXFB-A01) authored public-Metal harness. Compute-emulated
// OpenGL transform feedback: a compute kernel (kernels/xfb.metal, OWN-SHADER)
// captures synthetic primitives into up to 4 independent streams/buffers via
// global-memory writes + atomic counters, then a second compute kernel copies
// the captured count into a MTLDrawPrimitivesIndirectArguments record that a
// following render draw consumes (glDrawTransformFeedback's replay semantics).
// Apple binary introspection: NONE. Public Metal API surface only, no
// assembler, no native VDM/CDM grammar -- per the addendum's own instruction.
//
// --case capacity     -- single-stream (stream0) capacity/no-partial-primitive
//                         boundary sweep, feeding a replay draw.
// --case multistream   -- mask-mode sweep (all-4 / single / alternate /
//                         GS-shaped-fan-out) with independent per-stream
//                         generated/written counters.
// --case sync          -- the SAME 6-way sync-variant matrix as Bundle H's
//                         h_sync, applied to the (capture+finalize compute) ->
//                         (replay render draw) handoff.
// --case discard       -- rasterizer-discard on/off (skip vs. issue the
//                         replay draw) at a representative capture config.
//
// Stdout protocol mirrors harness/gddraws.m:
//   STATUS OK | COMPILE_FAIL | FUNCTION_MISSING | PIPELINE_FAIL | CMDBUF_ERROR
//   DEVICE <name>
//   OBSERVED <space-separated key=value fields>
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
static id<MTLRenderPipelineState> buildVerifyPSO(id<MTLDevice> dev, id<MTLLibrary> lib) {
    NSError *err = nil;
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = fn(lib, "v_verify");
    pd.fragmentFunction = fn(lib, "f_noop");
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
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
static int finishCB(id<MTLCommandBuffer> cb, NSError **errOut) {
    [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) { if (errOut) *errOut = cb.error; return 1; }
    return 0;
}
static void fillSentinelU32(void *p, size_t nbytes, uint32_t v) {
    uint32_t *w = (uint32_t *)p;
    for (size_t i = 0; i < nbytes / 4; ++i) w[i] = v;
}

typedef struct { uint32_t vertexCount, instanceCount, vertexStart, baseInstance; } DrawArgsC;

// ---------------------------------------------------------------------------
typedef struct {
    unsigned numPrimitives, maskMode, vppActive, vppAlt;
    unsigned cap[4], stride[4], off[4];
    BOOL interleave01;      // stream1 aliases stream0's buffer allocation
    unsigned replayStream;
    BOOL discard;
    const char *syncMode;   // NULL/"cpu_baseline" unused here -- always GPU-driven;
                             // "encoder_order"/"fence_sym"/"unsync_split"/
                             // "asym_producer"/"asym_consumer"
    uint32_t magicBase;
    uint32_t spinIters;
} XfbCase;

static int run_xfb(id<MTLDevice> dev, id<MTLCommandQueue> queue, id<MTLLibrary> lib, XfbCase c) {
    NSError *err = nil;
    id<MTLComputePipelineState> capturePSO =
        [dev newComputePipelineStateWithFunction:fn(lib, "xfb_capture") error:&err];
    if (!capturePSO) fail("PIPELINE_FAIL", "xfb_capture PSO", err);
    id<MTLComputePipelineState> finalizePSO =
        [dev newComputePipelineStateWithFunction:fn(lib, "xfb_finalize") error:&err];
    if (!finalizePSO) fail("PIPELINE_FAIL", "xfb_finalize PSO", err);
    id<MTLRenderPipelineState> renderPSO = buildVerifyPSO(dev, lib);

    BOOL sameCB       = c.syncMode == NULL || strcmp(c.syncMode, "encoder_order") == 0 || strcmp(c.syncMode, "fence_sym") == 0;
    BOOL useFenceProd = c.syncMode && (strcmp(c.syncMode, "fence_sym") == 0 || strcmp(c.syncMode, "asym_producer") == 0);
    BOOL useFenceCons = c.syncMode && (strcmp(c.syncMode, "fence_sym") == 0 || strcmp(c.syncMode, "asym_consumer") == 0);
    BOOL untracked    = c.syncMode && strcmp(c.syncMode, "encoder_order") != 0;
    MTLResourceOptions opt = MTLResourceStorageModeShared |
        (untracked ? MTLResourceHazardTrackingModeUntracked : MTLResourceHazardTrackingModeTracked);

    id<MTLBuffer> bufs[4];
    for (int s = 0; s < 4; ++s) {
        size_t len = (size_t)c.cap[s] * c.stride[s] + c.off[s] + 16;
        if (len < 64) len = 64;
        bufs[s] = [dev newBufferWithLength:len options:opt];
        fillSentinelU32(bufs[s].contents, bufs[s].length, SENTINEL);
    }
    if (c.interleave01) bufs[1] = bufs[0];

    // 3 counters per stream: generated, reserved, written (atomic_uint each) -- device buffer view.
    id<MTLBuffer> ctrGen = [dev newBufferWithLength:16 options:opt];
    id<MTLBuffer> ctrRes = [dev newBufferWithLength:16 options:opt];
    id<MTLBuffer> ctrWr  = [dev newBufferWithLength:16 options:opt];
    memset(ctrGen.contents, 0, 16); memset(ctrRes.contents, 0, 16); memset(ctrWr.contents, 0, 16);

    struct { uint32_t numPrimitives, vppActive, vppAlt, maskMode, magicBase, spinIters; } xp =
        { c.numPrimitives, c.vppActive, c.vppAlt, c.maskMode, c.magicBase, c.spinIters };
    id<MTLBuffer> xpBuf = [dev newBufferWithLength:sizeof(xp) options:MTLResourceStorageModeShared];
    memcpy(xpBuf.contents, &xp, sizeof(xp));
    uint32_t strides[4] = {c.stride[0],c.stride[1],c.stride[2],c.stride[3]};
    uint32_t offsets[4] = {c.off[0],c.off[1],c.off[2],c.off[3]};
    uint32_t caps[4]    = {c.cap[0],c.cap[1],c.cap[2],c.cap[3]};
    id<MTLBuffer> strideBuf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    id<MTLBuffer> offsetBuf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    id<MTLBuffer> capBuf    = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    memcpy(strideBuf.contents, strides, 16); memcpy(offsetBuf.contents, offsets, 16); memcpy(capBuf.contents, caps, 16);

    id<MTLBuffer> argsBuf = [dev newBufferWithLength:sizeof(DrawArgsC) options:opt];
    fillSentinelU32(argsBuf.contents, argsBuf.length, SENTINEL);
    id<MTLBuffer> replayBuf = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
    ((uint32_t *)replayBuf.contents)[0] = c.replayStream;

    // Precompute the deterministic expected `written` count for the replay
    // stream BEFORE dispatch (see the header comment on determinism: every
    // active thread for a stream requests the SAME vpp, so atomic_fetch_add
    // hands out a fixed partition of ranges regardless of scheduling order --
    // only WHICH primitive's data lands in which range is order-dependent).
    unsigned rs0 = c.replayStream;
    unsigned expectedWritten = 0;
    if (c.vppActive > 0 || c.vppAlt > 0) {
        unsigned reqForStream =
            (c.maskMode == 0) ? c.numPrimitives :
            (c.maskMode == 1) ? (rs0 == 0 ? c.numPrimitives : 0) :
            (c.maskMode == 2) ? ((rs0 < 2) ? (c.numPrimitives + 1) / 2 : c.numPrimitives / 2) :
            /* maskMode==3 */ (rs0 == 0 || rs0 == 1 ? c.numPrimitives : 0);
        unsigned vppForStream = (c.maskMode == 3 && rs0 == 1) ? c.vppAlt : c.vppActive;
        unsigned fits = (vppForStream > 0) ? (reqForStream * vppForStream <= caps[rs0] ? reqForStream
                                              : caps[rs0] / vppForStream) : 0;
        expectedWritten = fits * vppForStream;
    }

    id<MTLFence> fence = (useFenceProd || useFenceCons) ? [dev newFence] : nil;

    id<MTLCommandBuffer> cbA = [queue commandBuffer];
    id<MTLComputeCommandEncoder> cenc = [cbA computeCommandEncoder];
    [cenc setComputePipelineState:capturePSO];
    [cenc setBuffer:bufs[0] offset:0 atIndex:0];
    [cenc setBuffer:bufs[1] offset:0 atIndex:1];
    [cenc setBuffer:bufs[2] offset:0 atIndex:2];
    [cenc setBuffer:bufs[3] offset:0 atIndex:3];
    [cenc setBuffer:ctrGen offset:0 atIndex:4];
    [cenc setBuffer:ctrRes offset:0 atIndex:5];
    [cenc setBuffer:ctrWr  offset:0 atIndex:6];
    [cenc setBuffer:xpBuf offset:0 atIndex:7];
    [cenc setBuffer:strideBuf offset:0 atIndex:8];
    [cenc setBuffer:offsetBuf offset:0 atIndex:9];
    [cenc setBuffer:capBuf offset:0 atIndex:10];
    unsigned tgSize = MIN(c.numPrimitives, 64u); if (tgSize == 0) tgSize = 1;
    [cenc dispatchThreads:MTLSizeMake(MAX(c.numPrimitives,1u),1,1) threadsPerThreadgroup:MTLSizeMake(tgSize,1,1)];

    [cenc setComputePipelineState:finalizePSO];
    [cenc setBuffer:ctrWr offset:0 atIndex:0];
    [cenc setBuffer:argsBuf offset:0 atIndex:1];
    [cenc setBuffer:replayBuf offset:0 atIndex:2];
    [cenc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];

    if (useFenceProd) [cenc updateFence:fence];
    [cenc endEncoding];

    NSError *cberrA = nil, *cberrB = nil;
    int badA = 0, badB = 0;
    unsigned n_invoked = 0, n_correct = 0, n_stale = 0;
    uint32_t replayed_vertexCount = 0;
    id<MTLBuffer> seenBuf = nil;

    if (!c.discard) {
        unsigned seenCap = MAX(1u, caps[c.replayStream]);
        seenBuf = [dev newBufferWithLength:(size_t)seenCap * 16 options:MTLResourceStorageModeShared];
        fillSentinelU32(seenBuf.contents, seenBuf.length, SENTINEL);
        id<MTLBuffer> vparamBuf = [dev newBufferWithLength:8 options:MTLResourceStorageModeShared];
        { uint32_t *vp = vparamBuf.contents; vp[0] = seenCap; vp[1] = 1u; }

        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                                                       width:1 height:1 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];

        id<MTLCommandBuffer> cbB = sameCB ? cbA : [queue commandBuffer];
        id<MTLRenderCommandEncoder> renc = [cbB renderCommandEncoderWithDescriptor:dummyPass(target)];
        if (useFenceCons) [renc waitForFence:fence beforeStages:MTLRenderStageVertex];
        [renc setRenderPipelineState:renderPSO];
        [renc setVertexBuffer:bufs[c.replayStream] offset:0 atIndex:0];
        [renc setVertexBuffer:seenBuf offset:0 atIndex:1];
        [renc setVertexBuffer:vparamBuf offset:0 atIndex:2];
        [renc drawPrimitives:MTLPrimitiveTypePoint indirectBuffer:argsBuf indirectBufferOffset:0];
        [renc endEncoding];

        [cbA commit];
        if (!sameCB) [cbB commit];
        badA = finishCB(cbA, &cberrA);
        badB = sameCB ? 0 : finishCB(cbB, &cberrB);
        if (badA || badB) fail("CMDBUF_ERROR", "xfb", badA ? cberrA : cberrB);

        replayed_vertexCount = ((uint32_t *)argsBuf.contents)[0];
        uint32_t *seen = seenBuf.contents;
        for (unsigned slot = 0; slot < seenCap; ++slot) {
            uint32_t *rec = seen + slot * 4;
            BOOL touched = !(rec[0]==SENTINEL && rec[1]==SENTINEL && rec[2]==SENTINEL && rec[3]==SENTINEL);
            if (!touched) continue;
            n_invoked++;
            if (rec[2] == slot) n_correct++;   // z always == clamp(vid) regardless of data staleness
            // A slot within the expected-written range whose raw .x word still
            // equals SENTINEL means the render draw's vertex stage observed
            // data older than the producing compute dispatch's writes -- the
            // synchronization detector, reused from Bundle H's h_sync.
            if (slot < expectedWritten && rec[0] == SENTINEL) n_stale++;
        }
    } else {
        [cbA commit];
        badA = finishCB(cbA, &cberrA);
        if (badA) fail("CMDBUF_ERROR", "xfb_discard", cberrA);
    }

    uint32_t gen[4], res[4], wr[4];
    memcpy(gen, ctrGen.contents, 16); memcpy(res, ctrRes.contents, 16); memcpy(wr, ctrWr.contents, 16);
    unsigned rs = c.replayStream;
    unsigned char *raw = bufs[rs].contents;
    size_t boundaryByte = (size_t)expectedWritten * strides[rs] + offsets[rs];
    // Byte-wise, phase-correct check: fillSentinelU32 fills as repeating
    // 0xDEADBEEF little-endian words (bytes EF BE AD DE repeating). A naive
    // 4-byte-aligned memcpy+compare against SENTINEL is WRONG whenever
    // boundaryByte is not itself 4-byte aligned (e.g. a misaligned stride/
    // offset case) -- it reads a rotated phase of the SAME untouched
    // pattern and would falsely report a violation. Check each byte against
    // its correct phase instead, over a full 16-byte (one record) span.
    static const unsigned char SENTINEL_BYTES[4] = {0xEF, 0xBE, 0xAD, 0xDE};
    BOOL noPartial = YES;
    size_t checkLen = 16;
    if (boundaryByte + checkLen > bufs[rs].length) checkLen = bufs[rs].length > boundaryByte ? bufs[rs].length - boundaryByte : 0;
    for (size_t i = 0; i < checkLen; ++i) {
        if (raw[boundaryByte + i] != SENTINEL_BYTES[(boundaryByte + i) % 4]) { noPartial = NO; break; }
    }

    printf("OBSERVED gen0=%u gen1=%u gen2=%u gen3=%u res0=%u res1=%u res2=%u res3=%u "
           "wr0=%u wr1=%u wr2=%u wr3=%u expectedWritten_replay=%u noPartialAtBoundary=%d "
           "replay_vertexCount=%u n_invoked=%u n_correct=%u n_stale=%u discard=%d\n",
           gen[0],gen[1],gen[2],gen[3], res[0],res[1],res[2],res[3], wr[0],wr[1],wr[2],wr[3],
           expectedWritten, (int)noPartial, replayed_vertexCount, n_invoked, n_correct, n_stale, (int)c.discard);
    emit_status("OK");
    return 0;
}

// ---------------------------------------------------------------------------
enum { OPT_NUMPRIM=256, OPT_MASKMODE, OPT_VPPA, OPT_VPPB, OPT_CAP0, OPT_CAP1, OPT_CAP2, OPT_CAP3,
       OPT_STRIDE0, OPT_STRIDE1, OPT_STRIDE2, OPT_STRIDE3, OPT_OFF0, OPT_OFF1, OPT_OFF2, OPT_OFF3,
       OPT_INTERLEAVE, OPT_REPLAY, OPT_DISCARD, OPT_SYNC, OPT_MAGIC, OPT_SPIN };
static const struct option longOpts[] = {
    {"numprim",  required_argument, NULL, OPT_NUMPRIM},
    {"maskmode", required_argument, NULL, OPT_MASKMODE},
    {"vppa",     required_argument, NULL, OPT_VPPA},
    {"vppb",     required_argument, NULL, OPT_VPPB},
    {"cap0", required_argument, NULL, OPT_CAP0}, {"cap1", required_argument, NULL, OPT_CAP1},
    {"cap2", required_argument, NULL, OPT_CAP2}, {"cap3", required_argument, NULL, OPT_CAP3},
    {"stride0", required_argument, NULL, OPT_STRIDE0}, {"stride1", required_argument, NULL, OPT_STRIDE1},
    {"stride2", required_argument, NULL, OPT_STRIDE2}, {"stride3", required_argument, NULL, OPT_STRIDE3},
    {"off0", required_argument, NULL, OPT_OFF0}, {"off1", required_argument, NULL, OPT_OFF1},
    {"off2", required_argument, NULL, OPT_OFF2}, {"off3", required_argument, NULL, OPT_OFF3},
    {"interleave", required_argument, NULL, OPT_INTERLEAVE},
    {"replay",     required_argument, NULL, OPT_REPLAY},
    {"discard",    required_argument, NULL, OPT_DISCARD},
    {"sync",       required_argument, NULL, OPT_SYNC},
    {"magic",      required_argument, NULL, OPT_MAGIC},
    {"spin",       required_argument, NULL, OPT_SPIN},
    {NULL,0,NULL,0}
};

int main(int argc, char *argv[]) {
    setvbuf(stdout, NULL, _IONBF, 0);
    @autoreleasepool {
        XfbCase c; memset(&c, 0, sizeof(c));
        c.numPrimitives = 64; c.maskMode = 1; c.vppActive = 3; c.vppAlt = 1;
        c.cap[0]=c.cap[1]=c.cap[2]=c.cap[3]=256;
        c.stride[0]=c.stride[1]=c.stride[2]=c.stride[3]=16;
        c.off[0]=c.off[1]=c.off[2]=c.off[3]=0;
        c.interleave01 = NO; c.replayStream = 0; c.discard = NO;
        c.syncMode = "encoder_order"; c.magicBase = 0xC0FFEE00u; c.spinIters = 0;
        int c_;
        while ((c_ = getopt_long(argc, argv, "", longOpts, NULL)) > 0) {
            switch (c_) {
                case OPT_NUMPRIM: c.numPrimitives = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_MASKMODE: c.maskMode = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_VPPA: c.vppActive = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_VPPB: c.vppAlt = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_CAP0: c.cap[0] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_CAP1: c.cap[1] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_CAP2: c.cap[2] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_CAP3: c.cap[3] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_STRIDE0: c.stride[0] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_STRIDE1: c.stride[1] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_STRIDE2: c.stride[2] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_STRIDE3: c.stride[3] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_OFF0: c.off[0] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_OFF1: c.off[1] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_OFF2: c.off[2] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_OFF3: c.off[3] = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_INTERLEAVE: c.interleave01 = strtoul(optarg,NULL,0) != 0; break;
                case OPT_REPLAY: c.replayStream = (unsigned)strtoul(optarg,NULL,0); break;
                case OPT_DISCARD: c.discard = strtoul(optarg,NULL,0) != 0; break;
                case OPT_SYNC: c.syncMode = optarg; break;
                case OPT_MAGIC: c.magicBase = (uint32_t)strtoul(optarg,NULL,0); break;
                case OPT_SPIN: c.spinIters = (uint32_t)strtoul(optarg,NULL,0); break;
                default: fprintf(stderr, "usage: see header\n"); return 2;
            }
        }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLLibrary> lib = compileLib(dev, "kernels/xfb.metal");
        return run_xfb(dev, queue, lib, c);
    }
}
