// gfxprobe.m -- EXP-0136 items 2/3: primitive-restart sentinel behavior and a
// rasterizationEnabled=NO structural probe, PUBLIC Metal API only (no memory
// patching -- unlike descpatch.m, nothing here needs the live-pointer
// technique because every input here (index-buffer bytes, vertex positions,
// pipeline flags) is directly settable through the public API).
//
// Clean-room: OWN-SHADER + HW-PROBE (+ DATA-TRACE for op=norender_probe, which
// relies on the caller wrapping this binary with tools/iotrace, unmodified,
// exactly like descpatch.m; this binary itself does not link IOKit).
//
// ops:
//   restart_line  -- line-strip indexed draw with a sentinel index value in
//                     the middle of the index buffer; reports whether the
//                     "connecting" pixel region between the two vertex groups
//                     is lit (cut => restart honored) and whether the draw
//                     faulted.
//   norender_draw -- draws either with rasterizationEnabled YES or NO (per
//                     case param) with a vertex function that ALSO writes a
//                     side-effect record to a device buffer, so the caller can
//                     confirm vertex processing happened even when raster is
//                     off. No pass/fail verdict beyond "did it run" -- pure
//                     characterization; the caller (run.py + iotrace, dumping
//                     around this process) captures the command stream shape
//                     for offline structural comparison.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -O1 -o gfxprobe gfxprobe.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <dirent.h>
#include <time.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

// Same technique/timing as descpatch.m's trigger_dump_and_wait (see that file
// for the empirical justification): repeat SIGUSR1 + settle until the
// tools/iotrace (unmodified) bo-file count stabilizes.
static int count_bo_files(const char *dumpdir) {
    DIR *d = opendir(dumpdir);
    if (!d) return 0;
    int n = 0; struct dirent *e;
    while ((e = readdir(d)) != NULL) if (strncmp(e->d_name, "bo_", 3) == 0) n++;
    closedir(d);
    return n;
}
static void trigger_dump_and_wait(const char *dumpdir) {
    struct timespec settle = {0, 150 * 1000 * 1000};
    int prev = -1;
    for (int tries = 0; tries < 20; tries++) {
        kill(getpid(), SIGUSR1);
        nanosleep(&settle, NULL);
        int n = count_bo_files(dumpdir);
        if (n > 0 && n == prev) return;
        prev = n;
    }
}

static NSMutableDictionary *gResult;
static void setStatus(NSString *s) { gResult[@"status"] = s; }
static void setErrFromNSError(NSError *err, NSString *key) {
    if (err) gResult[key] = [[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" | "];
}
static void emitAndExit(int code) {
    NSError *jerr = nil;
    NSData *d = [NSJSONSerialization dataWithJSONObject:gResult options:0 error:&jerr];
    if (!d) fprintf(stdout, "{\"status\":\"HARNESS_JSON_FAIL\"}\n");
    else { fwrite([d bytes], 1, [d length], stdout); fprintf(stdout, "\n"); }
    fflush(stdout);
    exit(code);
}

// -------------------------------------------------------------- restart_line
// 64x16 R8Unorm target. Two solid quads (each a 4-vertex triangle strip: two
// filled bars with real AREA, far more robust to rasterize/read back than a
// zero-height line) -- a LEFT bar (x in [-0.9,-0.3]) and a RIGHT bar (x in
// [0.3,0.9]), joined into ONE 9-vertex indexed triangle-strip draw via a
// SENTINEL index in between. If the sentinel is honored as a strip-restart
// cut, no fragment should ever land in the middle "connector" band (x in
// roughly [-0.25,0.25]) between the two bars. If it is NOT honored (treated
// as a literal, wildly out-of-bounds vertex index into an 8-vertex position
// buffer), we expect either a page-fault-style CMDBUF_ERROR (OOB vertex
// fetch) or a filled/garbage connector band -- both are captured, not
// silently dropped.
static void opRestartLine(NSDictionary *c, id<MTLDevice> dev) {
    NSString *idxType = c[@"index_type"] ?: @"u16"; // "u16" or "u32"
    NSNumber *sentinelOverride = c[@"sentinel"];     // optional explicit index value

    NSString *msl =
      @"#include <metal_stdlib>\n"
       "using namespace metal;\n"
       "struct VOut { float4 pos [[position]]; };\n"
       "vertex VOut vs(device const float2* p [[buffer(0)]], uint vid [[vertex_id]]) {\n"
       "  VOut o; o.pos = float4(p[vid].x, p[vid].y, 0.0, 1.0); return o;\n"
       "}\n"
       "fragment float4 fs() { return float4(1.0,1.0,1.0,1.0); }\n";
    NSError *err = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:msl options:nil error:&err];
    if (!lib) { setStatus(@"COMPILE_FAIL"); setErrFromNSError(err, @"error"); emitAndExit(1); }
    id<MTLFunction> vfn = [lib newFunctionWithName:@"vs"];
    id<MTLFunction> ffn = [lib newFunctionWithName:@"fs"];

    const int W = 64, H = 16;
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR8Unorm width:W height:H mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    td.storageMode = MTLStorageModeShared;
    id<MTLTexture> rt = [dev newTextureWithDescriptor:td];

    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vfn; pd.fragmentFunction = ffn;
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatR8Unorm;
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if (!pso) { setStatus(@"PIPELINE_FAIL"); setErrFromNSError(err, @"error"); emitAndExit(1); }

    // 8 real vertices: left bar strip (0..3), right bar strip (4..7).
    float positions[8][2] = {
        {-0.9f, -0.8f}, {-0.9f, 0.8f}, {-0.3f, -0.8f}, {-0.3f, 0.8f},
        { 0.3f, -0.8f}, { 0.3f,  0.8f}, { 0.9f, -0.8f}, { 0.9f, 0.8f},
    };
    id<MTLBuffer> posBuf = [dev newBufferWithLength:sizeof(positions) options:MTLResourceStorageModeShared];
    memcpy([posBuf contents], positions, sizeof(positions));

    id<MTLBuffer> idxBuf;
    NSUInteger idxCount = 9; // 0,1,2,3, SENTINEL, 4,5,6,7
    MTLIndexType mtlIdxType;
    if ([idxType isEqualToString:@"u32"]) {
        uint32_t sentinel = sentinelOverride ? (uint32_t)[sentinelOverride unsignedLongLongValue] : 0xFFFFFFFFu;
        uint32_t idx[9] = {0, 1, 2, 3, sentinel, 4, 5, 6, 7};
        idxBuf = [dev newBufferWithLength:sizeof(idx) options:MTLResourceStorageModeShared];
        memcpy([idxBuf contents], idx, sizeof(idx));
        mtlIdxType = MTLIndexTypeUInt32;
        gResult[@"sentinel_used"] = @(sentinel);
    } else {
        uint16_t sentinel = sentinelOverride ? (uint16_t)[sentinelOverride unsignedLongLongValue] : (uint16_t)0xFFFFu;
        uint16_t idx[9] = {0, 1, 2, 3, sentinel, 4, 5, 6, 7};
        idxBuf = [dev newBufferWithLength:sizeof(idx) options:MTLResourceStorageModeShared];
        memcpy([idxBuf contents], idx, sizeof(idx));
        mtlIdxType = MTLIndexTypeUInt16;
        gResult[@"sentinel_used"] = @(sentinel);
    }

    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    MTLRenderPassDescriptor *rpd = [MTLRenderPassDescriptor renderPassDescriptor];
    rpd.colorAttachments[0].texture = rt;
    rpd.colorAttachments[0].loadAction = MTLLoadActionClear;
    rpd.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
    rpd.colorAttachments[0].storeAction = MTLStoreActionStore;
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rpd];
    [enc setRenderPipelineState:pso];
    [enc setVertexBuffer:posBuf offset:0 atIndex:0];
    [enc setCullMode:MTLCullModeNone];
    @try {
        [enc drawIndexedPrimitives:MTLPrimitiveTypeTriangleStrip indexCount:idxCount indexType:mtlIdxType
                        indexBuffer:idxBuf indexBufferOffset:0];
    } @catch (NSException *ex) {
        gResult[@"draw_exception"] = [ex reason] ?: @"?";
    }
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    NSString *st = @"OK";
    if ([cb status] == MTLCommandBufferStatusError) { st = @"CMDBUF_ERROR"; setErrFromNSError([cb error], @"error"); }

    if ([st isEqualToString:@"OK"]) {
        uint8_t *px = malloc((size_t)W * H);
        [rt getBytes:px bytesPerRow:W fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
        int row = H / 2;
        NSMutableArray *rowVals = [NSMutableArray array];
        for (int x = 0; x < W; x++) [rowVals addObject:@(px[row * W + x])];
        gResult[@"row_pixels"] = rowVals;
        // bars span NDC x in [-0.9,-0.3] and [0.3,0.9] -> cols [3,22] and [42,60]
        // (col = (ndc_x+1)/2 * W). connector band strictly between the bars.
        int connLo = 26, connHi = 38;
        int connLit = 0;
        for (int x = connLo; x <= connHi; x++) if (px[row * W + x] > 32) connLit = 1;
        gResult[@"connector_band_lit"] = @(connLit);
        int leftLit = 0, rightLit = 0;
        for (int x = 5; x <= 20; x++) if (px[row * W + x] > 32) leftLit = 1;
        for (int x = 44; x <= 59; x++) if (px[row * W + x] > 32) rightLit = 1;
        gResult[@"left_segment_lit"] = @(leftLit);
        gResult[@"right_segment_lit"] = @(rightLit);
        free(px);
    }
    setStatus(st);
    emitAndExit([st isEqualToString:@"OK"] ? 0 : 1);
}

// ------------------------------------------------------------- norender_draw
static void opNorenderDraw(NSDictionary *c, id<MTLDevice> dev, const char *dumpdir) {
    BOOL rasterOn = [c[@"raster_enabled"] boolValue];
    // Public Metal API constraint (discovered here): a rasterizationEnabled=NO
    // pipeline's vertex function must return void (no [[position]] -- there is
    // no rasterization stage left to consume it). Use two source variants so
    // the ONLY thing that differs between the raster-on and raster-off cases
    // is that one fact plus the pipeline flag itself.
    NSString *msl = rasterOn ?
      @"#include <metal_stdlib>\n"
       "using namespace metal;\n"
       "struct VOut { float4 pos [[position]]; };\n"
       "vertex VOut vs(device const float2* p [[buffer(0)]], device atomic_uint* cnt [[buffer(1)]], uint vid [[vertex_id]]) {\n"
       "  atomic_fetch_add_explicit(cnt, 1, memory_order_relaxed);\n"
       "  VOut o; o.pos = float4(p[vid].x, p[vid].y, 0.0, 1.0); return o;\n"
       "}\n"
       "fragment float4 fs() { return float4(1.0,0.0,0.0,1.0); }\n"
      :
      @"#include <metal_stdlib>\n"
       "using namespace metal;\n"
       "vertex void vs(device const float2* p [[buffer(0)]], device atomic_uint* cnt [[buffer(1)]], uint vid [[vertex_id]]) {\n"
       "  atomic_fetch_add_explicit(cnt, 1, memory_order_relaxed);\n"
       "  device float2* pp = (device float2*)p; float2 dummy = pp[vid]; (void)dummy;\n"
       "}\n"
       "fragment float4 fs() { return float4(1.0,0.0,0.0,1.0); }\n";
    NSError *err = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:msl options:nil error:&err];
    if (!lib) { setStatus(@"COMPILE_FAIL"); setErrFromNSError(err, @"error"); emitAndExit(1); }
    id<MTLFunction> vfn = [lib newFunctionWithName:@"vs"];
    id<MTLFunction> ffn = rasterOn ? [lib newFunctionWithName:@"fs"] : nil;

    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vfn;
    pd.rasterizationEnabled = rasterOn;
    if (rasterOn) { pd.fragmentFunction = ffn; pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm; }
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if (!pso) { setStatus(@"PIPELINE_FAIL"); setErrFromNSError(err, @"error"); emitAndExit(1); }

    float positions[3][2] = {{-0.5f, -0.5f}, {0.5f, -0.5f}, {0.0f, 0.5f}};
    id<MTLBuffer> posBuf = [dev newBufferWithLength:sizeof(positions) options:MTLResourceStorageModeShared];
    memcpy([posBuf contents], positions, sizeof(positions));
    id<MTLBuffer> cntBuf = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
    memset([cntBuf contents], 0, 4);
    uint64_t cntVA = (uint64_t)[cntBuf gpuAddress];
    uint64_t posVA = (uint64_t)[posBuf gpuAddress];
    gResult[@"cnt_gpu_va"] = @(cntVA);
    gResult[@"pos_gpu_va"] = @(posVA);

    const int W = 8, H = 8;
    id<MTLTexture> rt = nil;
    if (rasterOn) {
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        rt = [dev newTextureWithDescriptor:td];
    }

    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    MTLRenderPassDescriptor *rpd = [MTLRenderPassDescriptor renderPassDescriptor];
    if (rasterOn) {
        rpd.colorAttachments[0].texture = rt;
        rpd.colorAttachments[0].loadAction = MTLLoadActionClear;
        rpd.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
        rpd.colorAttachments[0].storeAction = MTLStoreActionStore;
    } else {
        rpd.renderTargetWidth = W; rpd.renderTargetHeight = H; rpd.defaultRasterSampleCount = 1;
    }
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rpd];
    [enc setRenderPipelineState:pso];
    [enc setVertexBuffer:posBuf offset:0 atIndex:0];
    [enc setVertexBuffer:cntBuf offset:0 atIndex:1];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];

    // pre-commit dump (see descpatch.m note): capture the encoded-but-not-yet-
    // submitted command stream shape for offline structural comparison between
    // the raster-on and raster-off cases (pure DATA-TRACE read, no patching).
    if (dumpdir) trigger_dump_and_wait(dumpdir);

    [cb commit];
    [cb waitUntilCompleted];
    NSString *st = @"OK";
    if ([cb status] == MTLCommandBufferStatusError) { st = @"CMDBUF_ERROR"; setErrFromNSError([cb error], @"error"); }
    uint32_t cntVal = *(uint32_t *)[cntBuf contents];
    gResult[@"vertex_invocations_observed"] = @(cntVal);
    int anyRed = 0;
    if (rasterOn && [st isEqualToString:@"OK"]) {
        uint8_t *px = malloc((size_t)W * H * 4);
        [rt getBytes:px bytesPerRow:W * 4 fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
        for (int i = 0; i < W * H; i++) if (px[i * 4 + 2] > 32) anyRed = 1; // BGRA -> index2=R
        free(px);
    }
    gResult[@"any_fragment_rendered"] = @(anyRed);
    gResult[@"raster_enabled"] = @(rasterOn);
    setStatus(st);
    emitAndExit([st isEqualToString:@"OK"] ? 0 : 1);
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        gResult = [NSMutableDictionary dictionary];
        if (argc < 2) { fprintf(stderr, "usage: gfxprobe CASE.json\n"); return 2; }
        NSData *cd = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:argv[1]]];
        if (!cd) { fprintf(stderr, "cannot read %s\n", argv[1]); return 2; }
        NSError *jerr = nil;
        NSDictionary *c = [NSJSONSerialization JSONObjectWithData:cd options:0 error:&jerr];
        if (!c) { fprintf(stderr, "bad json\n"); return 2; }
        gResult[@"case_id"] = c[@"case_id"] ?: @"?";
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { setStatus(@"NO_DEVICE"); emitAndExit(1); }
        NSString *op = c[@"op"];
        if ([op isEqualToString:@"restart_line"]) opRestartLine(c, dev);
        else if ([op isEqualToString:@"norender_draw"]) opNorenderDraw(c, dev, getenv("IOTRACE_DUMP_DIR"));
        else { setStatus(@"UNKNOWN_OP"); emitAndExit(2); }
    }
    return 0;
}
