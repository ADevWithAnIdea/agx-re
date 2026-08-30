// frun.m -- EXP-0143 authored render + splice + readback harness.
//
// Derived from OUR OWN prior authored code in this repository:
//   tools/agxtest/agxrender.m           (render splice-and-observe, EXP-0008)
//   tools/agxtest/agxrun_persist.m      (persistent request loop, EXP-0005)
//   experiments/EXP-0129-.../harness/fsrun.m  (MRT/depth/occlusion/buffers)
// New here: (a) a PERSISTENT render request loop (the render analogue of
// agxrun_persist, which only existed for compute), and (b) exact float
// readback for RGBA32Float attachments so a field sweep has an exact oracle
// instead of 8-bit quantized pixels.
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
        td.textureType = (gSamples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
        td.sampleCount = (NSUInteger)gSamples;
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = (gSamples > 1) ? MTLStorageModePrivate : MTLStorageModeShared;
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

    id<MTLCommandBuffer> cb = [gQ commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
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
                                 : ((gSamples > 1) ? nil : targets[rt]);
        char tag[16]; snprintf(tag, sizeof tag, "PIX%d", rt);
        if (!readTex) { printf("%s_UNAVAILABLE multisample-not-resolved\n", tag); continue; }
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
       O_BUFU32, O_OUTBUF, O_SPLICE, O_PERSIST, O_NOFM, O_BUILD, O_RESOLVE };
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
    {"resolve", no_argument, 0, O_RESOLVE}, {0, 0, 0, 0}
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
