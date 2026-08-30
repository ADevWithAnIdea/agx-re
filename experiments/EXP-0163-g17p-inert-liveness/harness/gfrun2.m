// gfrun2.m -- EXP-0163 authored render + splice + readback harness (G17P).
//
// DERIVED DIRECTLY FROM OUR OWN experiments/EXP-0155-g17p-emit-tex-frag/harness/
// gfrun.m (which is itself derived from our own tools/agxtest/agxrender.m,
// agxrun_persist.m, EXP-0129 fsrun.m, EXP-0143 frun.m and EXP-0142 texpersist.m).
// EXP-0163 adds ONLY the observation surfaces the inert-field carriers need,
// because the whole question here is whether a field looked inert merely because
// the carrier could not exercise it:
//
//   (a) --rt-array N : colour attachment 0 becomes a texture2d_array with N
//       slices and renderTargetArrayLength N, so a shader can select its
//       destination slice with [[render_target_array_index]].  This is the ONLY
//       configuration in which frag_color_store's documented array/layer
//       slice-address path is emitted at all.
//   (b) --tex-write-arr / --tex-write-3d / --tex-write-half / --tex-write-uint :
//       WRITABLE textures of array, 3D, 16-bit-float and 32-bit-integer kinds at
//       [[texture(6..9)]], each reset to a distinctive sentinel before every
//       render and read back after it, so texture writes can be observed on
//       destinations other than a plain 2D RGBA32Float target.
//   (c) OUTBUF is reported for render passes too (it was already allocated and
//       poisoned; EXP-0163 needs it as the PRIMARY observation for multisampled
//       passes, where the colour attachment cannot be read back directly and a
//       resolve would average the per-sample values this experiment is trying
//       to tell apart).
//
//
// Derived from OUR OWN prior authored code in this repository:
//   tools/agxtest/agxrender.m                    (render splice-and-observe, EXP-0008)
//   tools/agxtest/agxrun_persist.m               (persistent request loop, EXP-0005)
//   experiments/EXP-0129-.../harness/fsrun.m     (MRT/depth/occlusion/buffers)
//   experiments/EXP-0143-.../harness/frun.m      (persistent RENDER loop + the
//                                                 FIELD-SWEEP-PROTOCOL sec.7
//                                                 sentinel/poison/per-request
//                                                 scratch mitigations)
//   experiments/EXP-0142-.../harness/{tex,render}persist.m  (texture binding and
//                                                 the ERRDOM fault-class print)
// New here, for the TEXTURE arms this experiment adds to the fragment arms:
//   (a) a SAMPLED texture bound at [[texture(0)]] whose texel(x,y) = x + 100*y,
//       so every sample result is an exact integer naming its own texel;
//   (b) a WRITABLE texture at [[texture(1)]] reset to a distinctive sentinel
//       before every render and read back after it, so "wrote here" / "did not
//       write" / "wrote somewhere else" are three distinguishable observations;
//   (c) the OS fault-classification domain+code (ERRDOM), which
//       FIELD-SWEEP-PROTOCOL sec.7.2 requires alongside the status.
//
// CLEAN-ROOM: public Metal API only, on shaders compiled from OUR OWN MSL.
// No Apple binary is disassembled or introspected.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -o frun frun.m
//
// One-shot:
//   ./frun --source S.metal --vertex V --fragment F --archive base.bin \
//          --scratch work/scratch.bin --color-format 125 --width 8 --height 8 \
//          --splice 0x1234=2f0d54...
// Persistent (stdin request loop, one live MTLDevice for the process lifetime):
//   ./frun ... --persist
//   request:  <reqid> <nsplices> [<off>=<hex> ...]
//   response: REQ id / STATUS ... / PIX <hex> / [DEPTH <hex>] / [OCC n]
//             / [BUF <idx> <hex>] / DONE id
//
// STATUS values: OK | COMPILE_FAIL | FUNCTION_MISSING | ARCHIVE_FAIL |
//                PIPELINE_MISS | PIPELINE_FAIL | CMDBUF_ERROR | BAD_REQUEST |
//                SENTINEL_FAIL

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
typedef struct { int idx; unsigned n; unsigned *vals; } BufU32Spec;

// FIELD-SWEEP-PROTOCOL sec.7 mitigations:
//  * gReqSeq gives every request its OWN scratch archive path, so Metal can
//    never serve a cached library/pipeline keyed on a reused file URL.
//  * READBACK_POISON pre-fills every host read-back buffer, so a getBytes that
//    silently does not write is reported as poison rather than as zeros.
static unsigned long gReqSeq = 0;
static const unsigned char READBACK_POISON[4] = {0xEF, 0xBE, 0xAD, 0xDE}; // 0xDEADBEEF LE

static void poison(unsigned char *p, size_t n) {
    for (size_t i = 0; i < n; i++) p[i] = READBACK_POISON[i & 3];
}

static id<MTLDevice> gDev = nil;
static id<MTLCommandQueue> gQ = nil;
static NSData *gBaseArchive = nil;
static NSString *gScratch = nil;
static const char *gSrcPath = NULL, *gVName = NULL, *gFName = NULL;
static int gColorFmt = 125, gRtCount = 1, gSamples = 1;
static long gW = 8, gH = 8;
static BOOL gWantDepth = NO, gWantOcc = NO, gFastMath = YES, gWantResolve = NO;
static float gClear[4] = {0, 0, 0, 0};
static float gDepthClear = 1.0f;
static int gDepthCompare = 1;      // MTLCompareFunctionAlways = 8? (see below)
static BOOL gDepthWrite = YES;
static BufU32Spec gBufs[8]; static int gNBufs = 0;
static long gOutBufIdx = -1, gOutBufBytes = 0;
// Texture arms (EXP-0155).  Both textures are created ONCE for the process
// lifetime; only the writable one is reset per request.
static id<MTLTexture> gTexSamp = nil, gTexWrite = nil;
static long gTexSampW = 8, gTexSampH = 8, gTexWriteW = 8, gTexWriteH = 8;
static BOOL gWantTexSamp = NO, gWantTexWrite = NO, gWantTexExtra = NO;
// The 3D / cube / 2D-array textures the tex_coord_setup carrier needs, at
// [[texture(2)]], [[texture(3)]] and [[texture(4)]].  4x4 in every dimension,
// R32Float, with a value pattern that names the texel AND the slice/face.
static id<MTLTexture> gTex3D = nil, gTexCube = nil, gTexArr = nil;
// A Depth32Float SAMPLED texture at [[texture(5)]] for the sample_compare arm.
static id<MTLTexture> gTexDepth = nil;
static BOOL gWantTexDepth = NO; static long gTexDepthW = 8, gTexDepthH = 8;
static const float TEXW_RESET[4] = {-1.0f, -2.0f, -3.0f, -4.0f};

// EXP-0163 additions -------------------------------------------------------
// Layered colour attachment 0 (texture2d_array), for the render_target_array
// _index / slice-address path.
static long gRtArray = 0;                 // 0 = plain 2D attachment
// Writable textures of other kinds, at [[texture(6..9)]].
static id<MTLTexture> gTexWArr = nil, gTexW3D = nil, gTexWHalf = nil, gTexWUint = nil;
static BOOL gWantTexWArr = NO, gWantTexW3D = NO, gWantTexWHalf = NO, gWantTexWUint = NO;
static long gTWA[3] = {8, 8, 4};          // array  W,H,slices
static long gTW3[3] = {8, 8, 4};          // 3D     W,H,D
static long gTWH[2] = {8, 8};             // half   W,H
static long gTWU[2] = {8, 8};             // uint   W,H
static const unsigned TEXWU_RESET[4] = {0xFFFFFFF1u, 0xFFFFFFF2u,
                                        0xFFFFFFF3u, 0xFFFFFFF4u};

// Reset every EXP-0163 writable texture to its sentinel.  Called before every
// draw, exactly like reset_write_texture(), so "did not write" is always
// distinguishable from "wrote the reset value".
static void reset_write_textures_0163(void) {
    if (gTexWArr) {
        size_t n = (size_t)gTWA[0] * (size_t)gTWA[1];
        float *row = (float *)malloc(n * 16);
        for (size_t i = 0; i < n; i++) memcpy(row + i * 4, TEXW_RESET, 16);
        for (long sl = 0; sl < gTWA[2]; sl++)
            [gTexWArr replaceRegion:MTLRegionMake2D(0, 0, (NSUInteger)gTWA[0], (NSUInteger)gTWA[1])
                        mipmapLevel:0 slice:(NSUInteger)sl withBytes:row
                        bytesPerRow:16 * (size_t)gTWA[0] bytesPerImage:0];
        free(row);
    }
    if (gTexW3D) {
        size_t n = (size_t)gTW3[0] * (size_t)gTW3[1] * (size_t)gTW3[2];
        float *vol = (float *)malloc(n * 16);
        for (size_t i = 0; i < n; i++) memcpy(vol + i * 4, TEXW_RESET, 16);
        [gTexW3D replaceRegion:MTLRegionMake3D(0, 0, 0, (NSUInteger)gTW3[0],
                                               (NSUInteger)gTW3[1], (NSUInteger)gTW3[2])
                   mipmapLevel:0 slice:0 withBytes:vol
                   bytesPerRow:16 * (size_t)gTW3[0]
                 bytesPerImage:16 * (size_t)gTW3[0] * (size_t)gTW3[1]];
        free(vol);
    }
    if (gTexWHalf) {
        size_t n = (size_t)gTWH[0] * (size_t)gTWH[1];
        unsigned short *row = (unsigned short *)malloc(n * 8);
        // half sentinel (-1,-2,-3,-4): exact in half, so no quantisation noise.
        const unsigned short H4[4] = {0xBC00, 0xC000, 0xC200, 0xC400};
        for (size_t i = 0; i < n; i++) memcpy(row + i * 4, H4, 8);
        [gTexWHalf replaceRegion:MTLRegionMake2D(0, 0, (NSUInteger)gTWH[0], (NSUInteger)gTWH[1])
                     mipmapLevel:0 withBytes:row bytesPerRow:8 * (size_t)gTWH[0]];
        free(row);
    }
    if (gTexWUint) {
        size_t n = (size_t)gTWU[0] * (size_t)gTWU[1];
        unsigned *row = (unsigned *)malloc(n * 16);
        for (size_t i = 0; i < n; i++) memcpy(row + i * 4, TEXWU_RESET, 16);
        [gTexWUint replaceRegion:MTLRegionMake2D(0, 0, (NSUInteger)gTWU[0], (NSUInteger)gTWU[1])
                     mipmapLevel:0 withBytes:row bytesPerRow:16 * (size_t)gTWU[0]];
        free(row);
    }
}

static void reset_write_texture(void) {
    if (!gTexWrite) return;
    size_t n = (size_t)gTexWriteW * (size_t)gTexWriteH;
    float *row = (float *)malloc(n * 16);
    for (size_t i = 0; i < n; i++) memcpy(row + i * 4, TEXW_RESET, 16);
    [gTexWrite replaceRegion:MTLRegionMake2D(0, 0, (NSUInteger)gTexWriteW, (NSUInteger)gTexWriteH)
                 mipmapLevel:0 withBytes:row bytesPerRow:16 * (size_t)gTexWriteW];
    free(row);
}

static size_t bytesPerPixel(int fmt) {
    switch (fmt) {
        case 125: return 16;  // RGBA32Float
        case 115: return 8;   // RGBA16Float
        case 80:  case 70: case 71: case 81: return 4;  // BGRA8Unorm/RGBA8*/BGRA8_sRGB
        case 55:  return 4;   // R32Float
        case 10:  return 1;   // R8Unorm
        default:  return 4;
    }
}

static void printHex(const char *tag, const unsigned char *p, size_t n) {
    static const char H[] = "0123456789abcdef";
    fputs(tag, stdout); fputc(' ', stdout);
    for (size_t i = 0; i < n; i++) { fputc(H[p[i] >> 4], stdout); fputc(H[p[i] & 15], stdout); }
    fputc('\n', stdout);
}

static void respond_fail(const char *rid, const char *status, const char *msg, NSError *err) {
    if (rid) printf("REQ %s\n", rid);
    printf("STATUS %s\n", status);
    if (err) {
        NSString *d = [[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" "];
        // FIELD-SWEEP-PROTOCOL sec.7.2: record the OS fault CLASSIFICATION, not
        // just the status, so an InnocentVictim (another client's fault took our
        // command buffer down as collateral) is separable from our own encoding.
        printf("ERRDOM %s %ld\n", [[err domain] UTF8String], (long)[err code]);
        printf("ERROR %s: %s\n", msg ? msg : "", [d UTF8String]);
    } else if (msg) printf("ERROR %s\n", msg);
    if (rid) printf("DONE %s\n", rid);
    fflush(stdout);
}

// Execute one render with the given splices. Returns 0 on success.
static int doRender(const char *rid, SpliceSpec *spl, int nspl) {
  @autoreleasepool {
    NSError *err = nil;

    // 1. Patch a scratch copy of the base archive at raw byte offsets.
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

    // INTEGRITY SENTINEL (FIELD-SWEEP-PROTOCOL sec.7, independent path).
    // The bytes above were written from memory; here they are read back from
    // the filesystem through a SEPARATE NSData read and every spliced window is
    // compared byte-for-byte.  A silent write failure, a truncated file, or a
    // stale cached path therefore reports SENTINEL MISMATCH instead of being
    // scored as a legitimate observation.  Combined with
    // MTLPipelineOptionFailOnBinaryArchiveMiss below (which fails pipeline
    // creation unless the ARCHIVE supplied the machine code), this establishes
    // that the bytes we chose are the bytes the GPU ran.
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
    }

    // 2. Fresh MTLLibrary from the SPLICED archive's own bytes every request.
    //    (agxrun_persist.m's crux: a source-compiled library's native code is
    //    memoized in-process, so a later spliced archive would be ignored.)
    id<MTLLibrary> lib = [gDev newLibraryWithURL:aurl error:&err];
    if (!lib) { respond_fail(rid, "COMPILE_FAIL", "newLibraryWithURL(archive)", err); [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil]; return 1; }
    id<MTLFunction> vfn = [lib newFunctionWithName:[NSString stringWithUTF8String:gVName]];
    id<MTLFunction> ffn = [lib newFunctionWithName:[NSString stringWithUTF8String:gFName]];
    if (!vfn || !ffn) { respond_fail(rid, "FUNCTION_MISSING", "newFunctionWithName", nil); [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil]; return 1; }

    MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
    [adesc setUrl:aurl];
    id<MTLBinaryArchive> arc = [gDev newBinaryArchiveWithDescriptor:adesc error:&err];
    if (!arc) { respond_fail(rid, "ARCHIVE_FAIL", "newBinaryArchiveWithDescriptor", err); [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil]; return 1; }

    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    [pd setVertexFunction:vfn];
    [pd setFragmentFunction:ffn];
    for (int i = 0; i < gRtCount; i++) pd.colorAttachments[i].pixelFormat = (MTLPixelFormat)gColorFmt;
    pd.rasterSampleCount = (NSUInteger)gSamples;
    if (gRtArray > 0) pd.inputPrimitiveTopology = MTLPrimitiveTopologyClassTriangle;
    if (gWantDepth) pd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
    [pd setBinaryArchives:@[arc]];
    id<MTLRenderPipelineState> pso =
        [gDev newRenderPipelineStateWithDescriptor:pd
                                           options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                        reflection:nil error:&err];
    if (!pso) { respond_fail(rid, "PIPELINE_MISS", "newRenderPipelineState(archive)", err); [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil]; return 1; }

    // 3. Targets.
    id<MTLTexture> targets[4]; memset(targets, 0, sizeof(targets));
    for (int i = 0; i < gRtCount; i++) {
        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:(MTLPixelFormat)gColorFmt
                                                               width:(NSUInteger)gW height:(NSUInteger)gH
                                                           mipmapped:NO];
        if (gRtArray > 0) {
            // EXP-0163: a LAYERED attachment.  This is the only configuration in
            // which the fragment colour store has an array/layer slice address to
            // encode at all.
            td.textureType = MTLTextureType2DArray;
            td.arrayLength = (NSUInteger)gRtArray;
        } else {
            td.textureType = (gSamples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
        }
        td.sampleCount = (gRtArray > 0) ? 1 : (NSUInteger)gSamples;
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = (gSamples > 1 && gRtArray == 0) ? MTLStorageModePrivate
                                                         : MTLStorageModeShared;
        targets[i] = [gDev newTextureWithDescriptor:td];
    }
    id<MTLTexture> resolveTex = nil;
    if (gSamples > 1 && gWantResolve) {
        MTLTextureDescriptor *rd =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:(MTLPixelFormat)gColorFmt
                                                               width:(NSUInteger)gW height:(NSUInteger)gH
                                                           mipmapped:NO];
        rd.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        rd.storageMode = MTLStorageModeShared;
        resolveTex = [gDev newTextureWithDescriptor:rd];
    }
    id<MTLTexture> depthTex = nil;
    if (gWantDepth) {
        MTLTextureDescriptor *dd =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float
                                                               width:(NSUInteger)gW height:(NSUInteger)gH
                                                           mipmapped:NO];
        dd.textureType = (gSamples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
        dd.sampleCount = (NSUInteger)gSamples;
        dd.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        dd.storageMode = (gSamples > 1) ? MTLStorageModePrivate : MTLStorageModeShared;
        depthTex = [gDev newTextureWithDescriptor:dd];
    }
    id<MTLDepthStencilState> dss = nil;
    if (gWantDepth) {
        MTLDepthStencilDescriptor *d = [MTLDepthStencilDescriptor new];
        d.depthCompareFunction = (MTLCompareFunction)gDepthCompare;
        d.depthWriteEnabled = gDepthWrite;
        dss = [gDev newDepthStencilStateWithDescriptor:d];
    }
    id<MTLBuffer> visBuf = nil;
    if (gWantOcc) { visBuf = [gDev newBufferWithLength:8 options:MTLResourceStorageModeShared];
                    memset([visBuf contents], 0, 8); }

    id<MTLBuffer> mbufs[8]; memset(mbufs, 0, sizeof(mbufs));
    for (int i = 0; i < gNBufs; i++) {
        mbufs[i] = [gDev newBufferWithLength:gBufs[i].n * 4 options:MTLResourceStorageModeShared];
        memcpy([mbufs[i] contents], gBufs[i].vals, gBufs[i].n * 4);
    }
    id<MTLBuffer> outBuf = nil;
    if (gOutBufIdx >= 0) {
        outBuf = [gDev newBufferWithLength:(NSUInteger)gOutBufBytes options:MTLResourceStorageModeShared];
        poison((unsigned char *)[outBuf contents], (size_t)gOutBufBytes);
    }

    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    for (int i = 0; i < gRtCount; i++) {
        rp.colorAttachments[i].texture = targets[i];
        rp.colorAttachments[i].loadAction = MTLLoadActionClear;
        rp.colorAttachments[i].clearColor = MTLClearColorMake(gClear[0], gClear[1], gClear[2], gClear[3]);
        if (i == 0 && resolveTex) {
            rp.colorAttachments[0].resolveTexture = resolveTex;
            rp.colorAttachments[0].storeAction = MTLStoreActionMultisampleResolve;
        } else {
            rp.colorAttachments[i].storeAction = MTLStoreActionStore;
        }
    }
    if (gWantDepth) {
        rp.depthAttachment.texture = depthTex;
        rp.depthAttachment.loadAction = MTLLoadActionClear;
        rp.depthAttachment.clearDepth = gDepthClear;
        rp.depthAttachment.storeAction = MTLStoreActionStore;
    }
    if (gWantOcc) rp.visibilityResultBuffer = visBuf;
    if (gRtArray > 0) rp.renderTargetArrayLength = (NSUInteger)gRtArray;

    reset_write_texture();      // before the draw, every request (EXP-0155)
    reset_write_textures_0163();// ... and the EXP-0163 writable textures

    id<MTLCommandBuffer> cb = [gQ commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    if (gTexSamp) { [enc setFragmentTexture:gTexSamp atIndex:0]; [enc setVertexTexture:gTexSamp atIndex:0]; }
    if (gTexWrite) { [enc setFragmentTexture:gTexWrite atIndex:1]; [enc setVertexTexture:gTexWrite atIndex:1]; }
    if (gTex3D)   [enc setFragmentTexture:gTex3D   atIndex:2];
    if (gTexCube) [enc setFragmentTexture:gTexCube atIndex:3];
    if (gTexArr)  [enc setFragmentTexture:gTexArr  atIndex:4];
    if (gTexDepth) [enc setFragmentTexture:gTexDepth atIndex:5];
    if (gTexWArr)  [enc setFragmentTexture:gTexWArr  atIndex:6];
    if (gTexW3D)   [enc setFragmentTexture:gTexW3D   atIndex:7];
    if (gTexWHalf) [enc setFragmentTexture:gTexWHalf atIndex:8];
    if (gTexWUint) [enc setFragmentTexture:gTexWUint atIndex:9];
    if (dss) [enc setDepthStencilState:dss];
    if (gWantOcc) [enc setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];
    for (int i = 0; i < gNBufs; i++) {
        [enc setVertexBuffer:mbufs[i] offset:0 atIndex:gBufs[i].idx];
        [enc setFragmentBuffer:mbufs[i] offset:0 atIndex:gBufs[i].idx];
    }
    if (outBuf) {
        [enc setVertexBuffer:outBuf offset:0 atIndex:(NSUInteger)gOutBufIdx];
        [enc setFragmentBuffer:outBuf offset:0 atIndex:(NSUInteger)gOutBufIdx];
    }
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError) {
        respond_fail(rid, "CMDBUF_ERROR", "command buffer failed", [cb error]);
        [[NSFileManager defaultManager] removeItemAtPath:scratchN error:nil];
        gQ = [gDev newCommandQueue];   // cheap insurance after a fault
        return 1;
    }

    if (rid) printf("REQ %s\n", rid);
    printf("STATUS OK\n");
    printf("SENTINEL OK %d\n", nspl);
    size_t bpp = bytesPerPixel(gColorFmt);
    size_t rowBytes = bpp * (size_t)gW;
    unsigned char *px = malloc(rowBytes * (size_t)gH);
    for (int rt = 0; rt < gRtCount; rt++) {
        id<MTLTexture> readTex = (rt == 0 && resolveTex) ? resolveTex
                                 : (((gSamples > 1) && gRtArray == 0) ? nil : targets[rt]);
        char tag[24];
        if (!readTex) {
            snprintf(tag, sizeof tag, "PIX%d", rt);
            printf("%s_UNAVAILABLE multisample-not-resolved\n", tag);
            continue;
        }
        if (gRtArray > 0) {
            // EXP-0163: read back EVERY slice, so "wrote the wrong slice" is a
            // distinguishable observation from "wrote no slice".
            for (long sl = 0; sl < gRtArray; sl++) {
                snprintf(tag, sizeof tag, "PIX%d_S%ld", rt, sl);
                poison(px, rowBytes * (size_t)gH);
                [readTex getBytes:px bytesPerRow:rowBytes bytesPerImage:0
                       fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)gW, (NSUInteger)gH)
                      mipmapLevel:0 slice:(NSUInteger)sl];
                printHex(tag, px, rowBytes * (size_t)gH);
            }
            continue;
        }
        snprintf(tag, sizeof tag, "PIX%d", rt);
        poison(px, rowBytes * (size_t)gH);
        [readTex getBytes:px bytesPerRow:rowBytes
               fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)gW, (NSUInteger)gH) mipmapLevel:0];
        printHex(tag, px, rowBytes * (size_t)gH);
    }
    free(px);
    if (gWantDepth && gSamples == 1) {
        unsigned char *dpx = malloc(4 * (size_t)gW * (size_t)gH);
        poison(dpx, 4 * (size_t)gW * (size_t)gH);
        [depthTex getBytes:dpx bytesPerRow:4 * (size_t)gW
                fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)gW, (NSUInteger)gH) mipmapLevel:0];
        printHex("DEPTH", dpx, 4 * (size_t)gW * (size_t)gH);
        free(dpx);
    }
    if (gWantOcc) printf("OCC %llu\n", *(unsigned long long *)[visBuf contents]);
    if (gTexWrite) {
        size_t wrow = 16 * (size_t)gTexWriteW;
        unsigned char *wpx = malloc(wrow * (size_t)gTexWriteH);
        poison(wpx, wrow * (size_t)gTexWriteH);
        [gTexWrite getBytes:wpx bytesPerRow:wrow
                 fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)gTexWriteW, (NSUInteger)gTexWriteH)
                mipmapLevel:0];
        printHex("TEXW", wpx, wrow * (size_t)gTexWriteH);
        free(wpx);
    }
    if (gTexWArr) {
        size_t wrow = 16 * (size_t)gTWA[0], img = wrow * (size_t)gTWA[1];
        unsigned char *wp = malloc(img);
        for (long sl = 0; sl < gTWA[2]; sl++) {
            char t[24]; snprintf(t, sizeof t, "TEXWA%ld", sl);
            poison(wp, img);
            [gTexWArr getBytes:wp bytesPerRow:wrow bytesPerImage:0
                    fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)gTWA[0], (NSUInteger)gTWA[1])
                   mipmapLevel:0 slice:(NSUInteger)sl];
            printHex(t, wp, img);
        }
        free(wp);
    }
    if (gTexW3D) {
        size_t wrow = 16 * (size_t)gTW3[0], img = wrow * (size_t)gTW3[1];
        unsigned char *wp = malloc(img * (size_t)gTW3[2]);
        poison(wp, img * (size_t)gTW3[2]);
        [gTexW3D getBytes:wp bytesPerRow:wrow bytesPerImage:img
               fromRegion:MTLRegionMake3D(0, 0, 0, (NSUInteger)gTW3[0],
                                          (NSUInteger)gTW3[1], (NSUInteger)gTW3[2])
              mipmapLevel:0 slice:0];
        printHex("TEXW3", wp, img * (size_t)gTW3[2]);
        free(wp);
    }
    if (gTexWHalf) {
        size_t wrow = 8 * (size_t)gTWH[0];
        unsigned char *wp = malloc(wrow * (size_t)gTWH[1]);
        poison(wp, wrow * (size_t)gTWH[1]);
        [gTexWHalf getBytes:wp bytesPerRow:wrow
                 fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)gTWH[0], (NSUInteger)gTWH[1])
                mipmapLevel:0];
        printHex("TEXWH", wp, wrow * (size_t)gTWH[1]);
        free(wp);
    }
    if (gTexWUint) {
        size_t wrow = 16 * (size_t)gTWU[0];
        unsigned char *wp = malloc(wrow * (size_t)gTWU[1]);
        poison(wp, wrow * (size_t)gTWU[1]);
        [gTexWUint getBytes:wp bytesPerRow:wrow
                 fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)gTWU[0], (NSUInteger)gTWU[1])
                mipmapLevel:0];
        printHex("TEXWU", wp, wrow * (size_t)gTWU[1]);
        free(wp);
    }
    if (outBuf) printHex("OUTBUF", (const unsigned char *)[outBuf contents], (size_t)gOutBufBytes);
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
    doRender(rid, spl, n);
cleanup:
    for (int i = 0; i < n; i++) free(spl[i].bytes);
}

enum { O_SRC = 256, O_VTX, O_FRAG, O_ARCH, O_SCRATCH, O_CFMT, O_W, O_H, O_SAMPLES,
       O_DEPTH, O_DEPTHCLEAR, O_DEPTHCMP, O_DEPTHWRITE, O_OCC, O_RTCOUNT, O_CLEAR,
       O_BUFU32, O_OUTBUF, O_SPLICE, O_PERSIST, O_NOFM, O_BUILD, O_RESOLVE,
       O_TEXSAMP, O_TEXWRITE, O_TEXEXTRA, O_TEXDEPTH,
       /* EXP-0163 */ O_RTARRAY, O_TWARR, O_TW3D, O_TWHALF, O_TWUINT };
static struct option L[] = {
    {"source", required_argument, 0, O_SRC}, {"vertex", required_argument, 0, O_VTX},
    {"fragment", required_argument, 0, O_FRAG}, {"archive", required_argument, 0, O_ARCH},
    {"scratch", required_argument, 0, O_SCRATCH}, {"color-format", required_argument, 0, O_CFMT},
    {"width", required_argument, 0, O_W}, {"height", required_argument, 0, O_H},
    {"samples", required_argument, 0, O_SAMPLES}, {"depth", no_argument, 0, O_DEPTH},
    {"depth-clear", required_argument, 0, O_DEPTHCLEAR}, {"depth-compare", required_argument, 0, O_DEPTHCMP},
    {"depth-write", required_argument, 0, O_DEPTHWRITE}, {"occlusion", no_argument, 0, O_OCC},
    {"rt-count", required_argument, 0, O_RTCOUNT}, {"clear", required_argument, 0, O_CLEAR},
    {"buf-u32", required_argument, 0, O_BUFU32}, {"out-buf", required_argument, 0, O_OUTBUF},
    {"splice", required_argument, 0, O_SPLICE}, {"persist", no_argument, 0, O_PERSIST},
    {"no-fast-math", no_argument, 0, O_NOFM},
    {"build-archive", required_argument, 0, O_BUILD},
    {"resolve", no_argument, 0, O_RESOLVE},
    {"tex-sample", required_argument, 0, O_TEXSAMP},
    {"tex-write", required_argument, 0, O_TEXWRITE},
    {"tex-extra", no_argument, 0, O_TEXEXTRA},
    {"tex-depth", required_argument, 0, O_TEXDEPTH},
    /* EXP-0163 */
    {"rt-array", required_argument, 0, O_RTARRAY},
    {"tex-write-arr", required_argument, 0, O_TWARR},
    {"tex-write-3d", required_argument, 0, O_TW3D},
    {"tex-write-half", required_argument, 0, O_TWHALF},
    {"tex-write-uint", required_argument, 0, O_TWUINT},
    {0, 0, 0, 0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *archPath = NULL, *scratchPath = NULL, *buildPath = NULL;
    BOOL persist = NO;
    SpliceSpec spl[32]; int nspl = 0; memset(spl, 0, sizeof spl);
    int c;
    while ((c = getopt_long(argc, argv, "", L, NULL)) > 0) {
        switch (c) {
        case O_SRC: gSrcPath = optarg; break;
        case O_VTX: gVName = optarg; break;
        case O_FRAG: gFName = optarg; break;
        case O_ARCH: archPath = optarg; break;
        case O_SCRATCH: scratchPath = optarg; break;
        case O_CFMT: gColorFmt = (int)strtol(optarg, NULL, 0); break;
        case O_W: gW = strtol(optarg, NULL, 0); break;
        case O_H: gH = strtol(optarg, NULL, 0); break;
        case O_SAMPLES: gSamples = (int)strtol(optarg, NULL, 0); break;
        case O_DEPTH: gWantDepth = YES; break;
        case O_DEPTHCLEAR: gDepthClear = strtof(optarg, NULL); break;
        case O_DEPTHCMP: gDepthCompare = (int)strtol(optarg, NULL, 0); break;
        case O_DEPTHWRITE: gDepthWrite = strtol(optarg, NULL, 0) != 0; break;
        case O_OCC: gWantOcc = YES; break;
        case O_RTCOUNT: gRtCount = (int)strtol(optarg, NULL, 0); break;
        case O_CLEAR: sscanf(optarg, "%f,%f,%f,%f", &gClear[0], &gClear[1], &gClear[2], &gClear[3]); break;
        case O_PERSIST: persist = YES; break;
        case O_NOFM: gFastMath = NO; break;
        case O_BUILD: buildPath = optarg; break;
        case O_RESOLVE: gWantResolve = YES; break;
        case O_TEXSAMP: gWantTexSamp = YES; sscanf(optarg, "%ld,%ld", &gTexSampW, &gTexSampH); break;
        case O_TEXWRITE: gWantTexWrite = YES; sscanf(optarg, "%ld,%ld", &gTexWriteW, &gTexWriteH); break;
        case O_TEXEXTRA: gWantTexExtra = YES; break;
        case O_TEXDEPTH: gWantTexDepth = YES; sscanf(optarg, "%ld,%ld", &gTexDepthW, &gTexDepthH); break;
        case O_RTARRAY: gRtArray = strtol(optarg, NULL, 0); break;
        case O_TWARR:  gWantTexWArr  = YES; sscanf(optarg, "%ld,%ld,%ld", &gTWA[0], &gTWA[1], &gTWA[2]); break;
        case O_TW3D:   gWantTexW3D   = YES; sscanf(optarg, "%ld,%ld,%ld", &gTW3[0], &gTW3[1], &gTW3[2]); break;
        case O_TWHALF: gWantTexWHalf = YES; sscanf(optarg, "%ld,%ld", &gTWH[0], &gTWH[1]); break;
        case O_TWUINT: gWantTexWUint = YES; sscanf(optarg, "%ld,%ld", &gTWU[0], &gTWU[1]); break;
        case O_OUTBUF: { char *eq = strchr(optarg, '='); if (!eq) return 2; *eq = 0;
                         gOutBufIdx = strtol(optarg, NULL, 0); gOutBufBytes = strtol(eq + 1, NULL, 0); break; }
        case O_BUFU32: { char *eq = strchr(optarg, '='); if (!eq) return 2; *eq = 0;
                         gBufs[gNBufs].idx = (int)strtol(optarg, NULL, 0);
                         unsigned *v = malloc(sizeof(unsigned) * 4096); unsigned k = 0;
                         char *t = strtok(eq + 1, ","); while (t) { v[k++] = (unsigned)strtoul(t, NULL, 0); t = strtok(NULL, ","); }
                         gBufs[gNBufs].vals = v; gBufs[gNBufs].n = k; gNBufs++; break; }
        case O_SPLICE: { char *eq = strchr(optarg, '='); if (!eq) return 2; *eq = 0;
                         spl[nspl].off = strtoul(optarg, NULL, 0);
                         size_t blen = strlen(eq + 1) / 2; spl[nspl].bytes = malloc(blen ? blen : 1);
                         for (size_t k = 0; k < blen; k++) { unsigned x; sscanf(eq + 1 + k * 2, "%2x", &x); spl[nspl].bytes[k] = (unsigned char)x; }
                         spl[nspl].len = blen; nspl++; break; }
        default: fprintf(stderr, "frun: bad option\n"); return 2;
        }
    }
    if (!gSrcPath || !gVName || !gFName || (!buildPath && (!archPath || !scratchPath))) {
        fprintf(stderr, "frun: need --source --vertex --fragment and either --build-archive "
                        "or --archive --scratch\n");
        return 2;
    }
    gDev = MTLCreateSystemDefaultDevice();
    if (!gDev) { fprintf(stderr, "no Metal device\n"); return 1; }
    gQ = [gDev newCommandQueue];

    // --build-archive: serialize an MTLBinaryArchive for EXACTLY the pipeline
    // descriptor this process would run, so MTLPipelineOptionFailOnBinaryArchiveMiss
    // can never miss because of a descriptor mismatch (sample count, depth
    // format, MRT count).  tools/shdump/shdump.m only parameterizes the colour
    // format, which is why this is done here instead.
    if (buildPath) {
        NSError *berr = nil;
        NSString *bsrc = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:gSrcPath]
                                                   encoding:NSUTF8StringEncoding error:&berr];
        if (!bsrc) { fprintf(stderr, "cannot read source\n"); return 1; }
        MTLCompileOptions *bco = [MTLCompileOptions new];
        [bco setFastMathEnabled:gFastMath];
        id<MTLLibrary> blib = [gDev newLibraryWithSource:bsrc options:bco error:&berr];
        if (!blib) { fprintf(stderr, "compile failed: %s\n", [[berr localizedDescription] UTF8String]); return 1; }
        id<MTLFunction> bv = [blib newFunctionWithName:[NSString stringWithUTF8String:gVName]];
        id<MTLFunction> bf = [blib newFunctionWithName:[NSString stringWithUTF8String:gFName]];
        if (!bv || !bf) { fprintf(stderr, "function missing\n"); return 1; }
        MTLRenderPipelineDescriptor *bpd = [MTLRenderPipelineDescriptor new];
        [bpd setVertexFunction:bv];
        [bpd setFragmentFunction:bf];
        for (int i = 0; i < gRtCount; i++) bpd.colorAttachments[i].pixelFormat = (MTLPixelFormat)gColorFmt;
        bpd.rasterSampleCount = (NSUInteger)gSamples;
        // A vertex shader that writes [[render_target_array_index]] requires a
        // declared input primitive topology (recorded as the first draft's
        // pipeline failure in raw/prefreeze/census_run1.json).
        if (gRtArray > 0) bpd.inputPrimitiveTopology = MTLPrimitiveTopologyClassTriangle;
        if (gWantDepth) bpd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
        id<MTLRenderPipelineState> bpso = [gDev newRenderPipelineStateWithDescriptor:bpd error:&berr];
        if (!bpso) { fprintf(stderr, "pipeline failed: %s\n", [[berr localizedDescription] UTF8String]); return 1; }
        MTLBinaryArchiveDescriptor *bad = [MTLBinaryArchiveDescriptor new];
        id<MTLBinaryArchive> barc = [gDev newBinaryArchiveWithDescriptor:bad error:&berr];
        if (!barc) { fprintf(stderr, "archive create failed\n"); return 1; }
        if (![barc addRenderPipelineFunctionsWithDescriptor:bpd error:&berr]) {
            fprintf(stderr, "addRenderPipelineFunctions failed: %s\n", [[berr localizedDescription] UTF8String]);
            return 1;
        }
        NSURL *burl = [NSURL fileURLWithPath:[NSString stringWithUTF8String:buildPath]];
        if (![barc serializeToURL:burl error:&berr]) {
            fprintf(stderr, "serializeToURL failed: %s\n", [[berr localizedDescription] UTF8String]);
            return 1;
        }
        printf("BUILT %s\n", buildPath);
        fflush(stdout);
        return 0;
    }
    // Textures, created ONCE for the process lifetime (EXP-0155).
    if (gWantTexSamp) {
        MTLTextureDescriptor *sd =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float
                                                               width:(NSUInteger)gTexSampW
                                                              height:(NSUInteger)gTexSampH
                                                           mipmapped:NO];
        sd.usage = MTLTextureUsageShaderRead;
        sd.storageMode = MTLStorageModeShared;
        gTexSamp = [gDev newTextureWithDescriptor:sd];
        // texel(x,y) = x + 100*y : every sample result names its own texel.
        float *t = (float *)malloc(sizeof(float) * (size_t)gTexSampW * (size_t)gTexSampH);
        for (long y = 0; y < gTexSampH; y++)
            for (long x = 0; x < gTexSampW; x++)
                t[y * gTexSampW + x] = (float)x + 100.0f * (float)y;
        [gTexSamp replaceRegion:MTLRegionMake2D(0, 0, (NSUInteger)gTexSampW, (NSUInteger)gTexSampH)
                    mipmapLevel:0 withBytes:t bytesPerRow:4 * (size_t)gTexSampW];
        free(t);
    }
    if (gWantTexWrite) {
        MTLTextureDescriptor *wd =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                               width:(NSUInteger)gTexWriteW
                                                              height:(NSUInteger)gTexWriteH
                                                           mipmapped:NO];
        wd.usage = MTLTextureUsageShaderWrite | MTLTextureUsageShaderRead;
        wd.storageMode = MTLStorageModeShared;
        gTexWrite = [gDev newTextureWithDescriptor:wd];
        reset_write_texture();
    }

    if (gWantTexWArr) {
        MTLTextureDescriptor *ad = [MTLTextureDescriptor new];
        ad.textureType = MTLTextureType2DArray;
        ad.pixelFormat = MTLPixelFormatRGBA32Float;
        ad.width = (NSUInteger)gTWA[0]; ad.height = (NSUInteger)gTWA[1];
        ad.arrayLength = (NSUInteger)gTWA[2];
        ad.usage = MTLTextureUsageShaderWrite | MTLTextureUsageShaderRead;
        ad.storageMode = MTLStorageModeShared;
        gTexWArr = [gDev newTextureWithDescriptor:ad];
    }
    if (gWantTexW3D) {
        MTLTextureDescriptor *vd = [MTLTextureDescriptor new];
        vd.textureType = MTLTextureType3D;
        vd.pixelFormat = MTLPixelFormatRGBA32Float;
        vd.width = (NSUInteger)gTW3[0]; vd.height = (NSUInteger)gTW3[1];
        vd.depth = (NSUInteger)gTW3[2];
        vd.usage = MTLTextureUsageShaderWrite | MTLTextureUsageShaderRead;
        vd.storageMode = MTLStorageModeShared;
        gTexW3D = [gDev newTextureWithDescriptor:vd];
    }
    if (gWantTexWHalf) {
        MTLTextureDescriptor *hd =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA16Float
                                                               width:(NSUInteger)gTWH[0]
                                                              height:(NSUInteger)gTWH[1]
                                                           mipmapped:NO];
        hd.usage = MTLTextureUsageShaderWrite | MTLTextureUsageShaderRead;
        hd.storageMode = MTLStorageModeShared;
        gTexWHalf = [gDev newTextureWithDescriptor:hd];
    }
    if (gWantTexWUint) {
        MTLTextureDescriptor *ud =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Uint
                                                               width:(NSUInteger)gTWU[0]
                                                              height:(NSUInteger)gTWU[1]
                                                           mipmapped:NO];
        ud.usage = MTLTextureUsageShaderWrite | MTLTextureUsageShaderRead;
        ud.storageMode = MTLStorageModeShared;
        gTexWUint = [gDev newTextureWithDescriptor:ud];
    }
    if (gWantTexWArr || gWantTexW3D || gWantTexWHalf || gWantTexWUint)
        reset_write_textures_0163();

    if (gWantTexDepth) {
        MTLTextureDescriptor *dd2 =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float
                                                               width:(NSUInteger)gTexDepthW
                                                              height:(NSUInteger)gTexDepthH
                                                           mipmapped:NO];
        dd2.usage = MTLTextureUsageShaderRead; dd2.storageMode = MTLStorageModeShared;
        gTexDepth = [gDev newTextureWithDescriptor:dd2];
        float *dv = (float *)malloc(4 * (size_t)gTexDepthW * (size_t)gTexDepthH);
        for (long y = 0; y < gTexDepthH; y++)
            for (long x = 0; x < gTexDepthW; x++)
                dv[y * gTexDepthW + x] = ((float)x + 8.0f * (float)y) / 64.0f;
        [gTexDepth replaceRegion:MTLRegionMake2D(0, 0, (NSUInteger)gTexDepthW, (NSUInteger)gTexDepthH)
                     mipmapLevel:0 withBytes:dv bytesPerRow:4 * (size_t)gTexDepthW];
        free(dv);
    }
    if (gWantTexExtra) {
        const NSUInteger N = 4;
        float buf[4 * 4];
        // texture(2): 3D, texel(x,y,z) = x + 10*y + 100*z
        MTLTextureDescriptor *d3 = [MTLTextureDescriptor new];
        d3.textureType = MTLTextureType3D; d3.pixelFormat = MTLPixelFormatR32Float;
        d3.width = N; d3.height = N; d3.depth = N;
        d3.usage = MTLTextureUsageShaderRead; d3.storageMode = MTLStorageModeShared;
        gTex3D = [gDev newTextureWithDescriptor:d3];
        for (NSUInteger z = 0; z < N; z++) {
            for (NSUInteger y = 0; y < N; y++)
                for (NSUInteger x = 0; x < N; x++)
                    buf[y * N + x] = (float)x + 10.0f * (float)y + 100.0f * (float)z;
            [gTex3D replaceRegion:MTLRegionMake3D(0, 0, z, N, N, 1) mipmapLevel:0 slice:0
                        withBytes:buf bytesPerRow:4 * N bytesPerImage:4 * N * N];
        }
        // texture(3): cube, texel(x,y,face) = x + 10*y + 1000*face
        MTLTextureDescriptor *dc =
            [MTLTextureDescriptor textureCubeDescriptorWithPixelFormat:MTLPixelFormatR32Float
                                                                  size:N mipmapped:NO];
        dc.usage = MTLTextureUsageShaderRead; dc.storageMode = MTLStorageModeShared;
        gTexCube = [gDev newTextureWithDescriptor:dc];
        for (NSUInteger f = 0; f < 6; f++) {
            for (NSUInteger y = 0; y < N; y++)
                for (NSUInteger x = 0; x < N; x++)
                    buf[y * N + x] = (float)x + 10.0f * (float)y + 1000.0f * (float)f;
            [gTexCube replaceRegion:MTLRegionMake2D(0, 0, N, N) mipmapLevel:0 slice:f
                          withBytes:buf bytesPerRow:4 * N bytesPerImage:4 * N * N];
        }
        // texture(4): 2D array (2 layers), texel(x,y,l) = x + 10*y + 10000*l
        MTLTextureDescriptor *da =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float
                                                               width:N height:N mipmapped:NO];
        da.textureType = MTLTextureType2DArray; da.arrayLength = 2;
        da.usage = MTLTextureUsageShaderRead; da.storageMode = MTLStorageModeShared;
        gTexArr = [gDev newTextureWithDescriptor:da];
        for (NSUInteger l = 0; l < 2; l++) {
            for (NSUInteger y = 0; y < N; y++)
                for (NSUInteger x = 0; x < N; x++)
                    buf[y * N + x] = (float)x + 10.0f * (float)y + 10000.0f * (float)l;
            [gTexArr replaceRegion:MTLRegionMake2D(0, 0, N, N) mipmapLevel:0 slice:l
                         withBytes:buf bytesPerRow:4 * N bytesPerImage:4 * N * N];
        }
    }

    gScratch = [NSString stringWithUTF8String:scratchPath];
    gBaseArchive = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:archPath]];
    if (!gBaseArchive) { fprintf(stderr, "cannot read archive\n"); return 1; }
    // Sanity-compile OUR source once so a bad carrier fails fast and loudly.
    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:gSrcPath]
                                              encoding:NSUTF8StringEncoding error:&err];
    if (!src) { fprintf(stderr, "cannot read source\n"); return 1; }
    MTLCompileOptions *co = [MTLCompileOptions new];
    [co setFastMathEnabled:gFastMath];
    if (![gDev newLibraryWithSource:src options:co error:&err]) {
        fprintf(stderr, "compile failed: %s\n", [[err localizedDescription] UTF8String]); return 1;
    }

    if (!persist) { int rc = doRender(NULL, spl, nspl); return rc; }

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
