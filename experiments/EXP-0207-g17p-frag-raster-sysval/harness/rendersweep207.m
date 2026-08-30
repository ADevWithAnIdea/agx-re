// rendersweep207.m -- EXP-0207 persistent OWN-SHADER render sweep runner.
//
// DERIVATIVE of our own experiments/EXP-0178-g17p-sysval-tileread/harness/
// rendersweep.m (itself derived from our EXP-0147 harness and from
// tools/agxtest/agxrender.m).  It keeps ONE live MTLDevice + queue for the
// process lifetime and services (spliced-archive, pipeline-state, inputs) ->
// (pixels, device buffer) requests read as one JSON object per line on stdin.
// Each request re-loads the binary archive FROM DISK and forces the render
// pipeline to come from it with MTLPipelineOptionFailOnBinaryArchiveMiss, so
// the bytes we spliced are the bytes that execute.
//
// EXP-0207 adds exactly the pipeline-state dimensions its fields need, and
// changes nothing else:
//   "format"  : the colour-attachment pixel format (was hard-wired RGBA32Float)
//   "blend"   : "none" | "alpha" | "dual"  (dual-source blending is the untried
//               destination kind for frag_color_store.store_mode)
//   "depth"   : 1 to attach a Depth32Float target and a depth-writing state
//   "outbuf"  : bytes of a device buffer bound at fragment buffer(1), POISONED
//               with 0xDEADBEEF before every dispatch and returned as hex --
//               the integrity sentinel, and the per-sample observable for the
//               iter arms (a resolve average would hide a sample permutation)
//   "prim"    : "triangle" | "point"
//   response  : "raw" is the hex of every colour attachment's bytes, so the
//               observable is byte-exact and format-agnostic; "pixels" is still
//               emitted for RGBA32Float so oracles stay readable.
//
// CLEAN-ROOM: public Metal API only, driving OUR OWN compiled MSL.  No Apple
// binary is disassembled, decompiled, or introspected.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o rendersweep207 rendersweep207.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void respond_fail(NSString *rid, const char *status, NSString *msg) {
    NSString *m = msg ? [[msg stringByReplacingOccurrencesOfString:@"\"" withString:@"'"]
                          stringByReplacingOccurrencesOfString:@"\n" withString:@" "] : @"";
    printf("{\"id\":\"%s\",\"status\":\"%s\",\"error\":\"%s\"}\n",
           [rid UTF8String], status, [m UTF8String]);
    fflush(stdout);
}

static NSUInteger bppOf(NSUInteger fmt) {
    switch (fmt) {
        case MTLPixelFormatRGBA32Float: case MTLPixelFormatRGBA32Uint:
        case MTLPixelFormatRGBA32Sint:  return 16;
        case MTLPixelFormatRGBA16Float: case MTLPixelFormatRGBA16Uint: return 8;
        case MTLPixelFormatRGBA8Unorm:  case MTLPixelFormatRGBA8Unorm_sRGB:
        case MTLPixelFormatBGRA8Unorm:  case MTLPixelFormatRGBA8Uint:
        case MTLPixelFormatR32Float:    case MTLPixelFormatR32Uint: return 4;
        default: return 0;                       // unsupported here -> BAD_REQUEST
    }
}

// A NaN or an infinity printed with %g is `nan` / `inf`, which is NOT valid JSON,
// and a single such pixel makes the whole response unparseable -- observed in
// work/pilot02 as five `measurement_failed` cases whose raw payload began with
// 0x7f800000 (+inf).  A measurement failure is not an observation, so the fix is
// to keep the response parseable: the authoritative observable is the exact
// `raw` byte string, and this convenience array emits JSON null for any
// non-finite value rather than an unparseable token.
static void appendNum(NSMutableString *s, double v, BOOL comma) {
    if (comma) [s appendString:@","];
    if (isfinite(v)) [s appendFormat:@"%.9g", v];
    else             [s appendString:@"null"];
}

static void hexcat(NSMutableString *dst, const uint8_t *b, NSUInteger n) {
    static const char *H = "0123456789abcdef";
    char *tmp = (char *)malloc(n * 2 + 1);
    for (NSUInteger i = 0; i < n; i++) { tmp[i*2] = H[b[i] >> 4]; tmp[i*2+1] = H[b[i] & 15]; }
    tmp[n*2] = 0;
    [dst appendString:[NSString stringWithUTF8String:tmp]];
    free(tmp);
}

int main(int argc, char **argv) { @autoreleasepool {
    const char *sourcePath = NULL;
    BOOL fastMath = NO;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--source") && i + 1 < argc) sourcePath = argv[++i];
        else if (!strcmp(argv[i], "--fast-math")) fastMath = YES;
    }
    if (!sourcePath) { fprintf(stderr, "need --source\n"); return 2; }

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { fprintf(stderr, "no Metal device\n"); return 2; }
    id<MTLCommandQueue> q = [dev newCommandQueue];

    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                              encoding:NSUTF8StringEncoding error:&err];
    if (!src) { fprintf(stderr, "read source failed\n"); return 2; }
    MTLCompileOptions *co = [MTLCompileOptions new];
    [co setFastMathEnabled:fastMath];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) { fprintf(stderr, "compile failed: %s\n",
                        [[err localizedDescription] UTF8String]); return 2; }

    printf("READY %s\n", [[dev name] UTF8String]);
    fflush(stdout);

    char *line = NULL; size_t cap = 0; ssize_t n;
    while ((n = getline(&line, &cap, stdin)) > 0) { @autoreleasepool {
        NSData *jd = [NSData dataWithBytes:line length:(NSUInteger)n];
        NSDictionary *req = [NSJSONSerialization JSONObjectWithData:jd options:0 error:nil];
        if (![req isKindOfClass:[NSDictionary class]]) {
            respond_fail(@"?", "BAD_REQUEST", @"not a JSON object"); continue;
        }
        NSString *rid = req[@"id"] ?: @"?";
        NSString *arc = req[@"archive"];
        NSString *vsn = req[@"vs"], *fsn = req[@"fs"];
        NSUInteger W    = [(req[@"w"] ?: @8) unsignedIntegerValue];
        NSUInteger H    = [(req[@"h"] ?: @8) unsignedIntegerValue];
        NSUInteger NRT  = [(req[@"nrt"] ?: @1) unsignedIntegerValue];
        NSUInteger SAMP = [(req[@"samples"] ?: @1) unsignedIntegerValue];
        NSUInteger FMT  = [(req[@"format"] ?: @125) unsignedIntegerValue];
        NSString  *BLEND = req[@"blend"] ?: @"none";
        BOOL DEPTH      = [(req[@"depth"] ?: @0) boolValue];
        NSUInteger OUTB = [(req[@"outbuf"] ?: @0) unsignedIntegerValue];
        // The authoritative observable is always the exact `raw` byte string; the
        // float `pixels` array exists only for the oracles that are written in
        // floats, and emitting it for every case roughly triples the response.
        BOOL WANTPX = [(req[@"want_pixels"] ?: @1) boolValue];
        NSArray *clear = req[@"clear"];
        NSArray *fbuf = req[@"fbuf"], *vbuf = req[@"vbuf"];
        NSUInteger INST = [(req[@"instances"] ?: @1) unsignedIntegerValue];
        NSString *DRAW = req[@"draw"] ?: @"prim";
        NSString *PRIM = req[@"prim"] ?: @"triangle";
        NSInteger BASEV = [(req[@"basevertex"] ?: @0) integerValue];
        NSUInteger BASEI = [(req[@"baseinstance"] ?: @0) unsignedIntegerValue];
        NSUInteger bpp = bppOf(FMT);
        if (!arc || !vsn || !fsn || NRT < 1 || NRT > 4 || bpp == 0) {
            respond_fail(rid, "BAD_REQUEST", @"need archive/vs/fs, nrt 1..4, known format");
            continue;
        }

        NSError *e = nil;
        // CRUCIAL (mirrors tools/agxtest/agxrun_persist.m): a library compiled
        // from *source* has a fixed AIR identity whose native code Metal
        // memoizes in-process, so a later spliced archive would be IGNORED and
        // the original code would run.  Load a FRESH MTLLibrary from the
        // spliced archive's own bytes each request so every splice executes.
        id<MTLLibrary> alib = [dev newLibraryWithURL:[NSURL fileURLWithPath:arc] error:&e];
        if (!alib) { respond_fail(rid, "COMPILE_FAIL", [e localizedDescription]); continue; }
        id<MTLFunction> vf = [alib newFunctionWithName:vsn];
        id<MTLFunction> ff = [alib newFunctionWithName:fsn];
        if (!vf || !ff) { respond_fail(rid, "FUNCTION_MISSING", nil); continue; }

        MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
        [ad setUrl:[NSURL fileURLWithPath:arc]];
        id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:ad error:&e];
        if (!archive) { respond_fail(rid, "ARCHIVE_FAIL", [e localizedDescription]); continue; }

        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        [pd setVertexFunction:vf]; [pd setFragmentFunction:ff];
        for (NSUInteger i = 0; i < NRT; i++)
            pd.colorAttachments[i].pixelFormat = (MTLPixelFormat)FMT;
        if ([BLEND isEqualToString:@"alpha"]) {
            pd.colorAttachments[0].blendingEnabled = YES;
            pd.colorAttachments[0].rgbBlendOperation = MTLBlendOperationAdd;
            pd.colorAttachments[0].alphaBlendOperation = MTLBlendOperationAdd;
            pd.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
            pd.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
            pd.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorOne;
            pd.colorAttachments[0].destinationAlphaBlendFactor = MTLBlendFactorZero;
        } else if ([BLEND isEqualToString:@"dual"]) {
            pd.colorAttachments[0].blendingEnabled = YES;
            pd.colorAttachments[0].rgbBlendOperation = MTLBlendOperationAdd;
            pd.colorAttachments[0].alphaBlendOperation = MTLBlendOperationAdd;
            pd.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorOne;
            pd.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorSource1Color;
            pd.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorOne;
            pd.colorAttachments[0].destinationAlphaBlendFactor = MTLBlendFactorSource1Alpha;
        }
        if (DEPTH) pd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
        pd.rasterSampleCount = SAMP;
        [pd setBinaryArchives:@[archive]];
        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithDescriptor:pd
                                              options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                           reflection:nil error:&e];
        if (!pso) { respond_fail(rid, "PIPELINE_MISS", [e localizedDescription]); continue; }

        NSMutableArray *tex = [NSMutableArray array];
        NSMutableArray *msaa = [NSMutableArray array];
        for (NSUInteger i = 0; i < NRT; i++) {
            MTLTextureDescriptor *td =
                [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:(MTLPixelFormat)FMT
                                                                   width:W height:H mipmapped:NO];
            td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
            td.storageMode = MTLStorageModeShared;
            [tex addObject:[dev newTextureWithDescriptor:td]];
            if (SAMP > 1) {
                MTLTextureDescriptor *md =
                    [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:(MTLPixelFormat)FMT
                                                                       width:W height:H mipmapped:NO];
                md.textureType = MTLTextureType2DMultisample;
                md.sampleCount = SAMP;
                md.usage = MTLTextureUsageRenderTarget;
                md.storageMode = MTLStorageModePrivate;
                [msaa addObject:[dev newTextureWithDescriptor:md]];
            }
        }
        id<MTLTexture> dtex = nil;
        id<MTLDepthStencilState> dss = nil;
        if (DEPTH) {
            MTLTextureDescriptor *dd =
                [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float
                                                                   width:W height:H mipmapped:NO];
            dd.textureType = (SAMP > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
            dd.sampleCount = SAMP;
            dd.usage = MTLTextureUsageRenderTarget;
            dd.storageMode = MTLStorageModePrivate;
            dtex = [dev newTextureWithDescriptor:dd];
            MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
            dsd.depthCompareFunction = MTLCompareFunctionAlways;
            dsd.depthWriteEnabled = YES;
            dss = [dev newDepthStencilStateWithDescriptor:dsd];
        }

        float fb[32], vb[32];
        memset(fb, 0, sizeof fb); memset(vb, 0, sizeof vb);
        for (NSUInteger i = 0; i < 32 && fbuf && i < [fbuf count]; i++) fb[i] = [fbuf[i] floatValue];
        for (NSUInteger i = 0; i < 32 && vbuf && i < [vbuf count]; i++) vb[i] = [vbuf[i] floatValue];
        id<MTLBuffer> fbb = [dev newBufferWithBytes:fb length:sizeof fb options:MTLResourceStorageModeShared];
        id<MTLBuffer> vbb = [dev newBufferWithBytes:vb length:sizeof vb options:MTLResourceStorageModeShared];

        // POISON (FIELD-SWEEP-PROTOCOL section 7, instrument 1): 0xDEADBEEF so
        // "never ran" is distinguishable from "wrote zero".
        id<MTLBuffer> ob = nil;
        if (OUTB) {
            ob = [dev newBufferWithLength:OUTB options:MTLResourceStorageModeShared];
            uint32_t *p = (uint32_t *)[ob contents];
            for (NSUInteger i = 0; i < OUTB / 4; i++) p[i] = 0xDEADBEEFu;
        }

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        for (NSUInteger i = 0; i < NRT; i++) {
            double c[4] = {0,0,0,0};
            if (clear && i < [clear count]) {
                NSArray *ci = clear[i];
                for (NSUInteger k = 0; k < 4 && k < [ci count]; k++) c[k] = [ci[k] doubleValue];
            }
            if (SAMP > 1) {
                rp.colorAttachments[i].texture = msaa[i];
                rp.colorAttachments[i].resolveTexture = tex[i];
                rp.colorAttachments[i].storeAction = MTLStoreActionMultisampleResolve;
            } else {
                rp.colorAttachments[i].texture = tex[i];
                rp.colorAttachments[i].storeAction = MTLStoreActionStore;
            }
            rp.colorAttachments[i].loadAction = MTLLoadActionClear;
            rp.colorAttachments[i].clearColor = MTLClearColorMake(c[0], c[1], c[2], c[3]);
        }
        if (DEPTH) {
            rp.depthAttachment.texture = dtex;
            rp.depthAttachment.loadAction = MTLLoadActionClear;
            rp.depthAttachment.storeAction = MTLStoreActionDontCare;
            rp.depthAttachment.clearDepth = 1.0;
        }

        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        if (dss) [enc setDepthStencilState:dss];
        [enc setFragmentBuffer:fbb offset:0 atIndex:0];
        [enc setVertexBuffer:vbb offset:0 atIndex:0];
        if (ob) [enc setFragmentBuffer:ob offset:0 atIndex:1];
        MTLPrimitiveType prim = [PRIM isEqualToString:@"point"]
                                ? MTLPrimitiveTypePoint : MTLPrimitiveTypeTriangle;
        if ([DRAW isEqualToString:@"indexed"]) {
            uint16_t idx[3] = {0, 1, 2};
            id<MTLBuffer> ib = [dev newBufferWithBytes:idx length:sizeof(idx)
                                               options:MTLResourceStorageModeShared];
            [enc drawIndexedPrimitives:prim indexCount:3
                             indexType:MTLIndexTypeUInt16 indexBuffer:ib
                     indexBufferOffset:0 instanceCount:INST
                            baseVertex:BASEV baseInstance:BASEI];
        } else {
            [enc drawPrimitives:prim vertexStart:0 vertexCount:3 instanceCount:INST];
        }
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError) {
            respond_fail(rid, "CMDBUF_ERROR", [[cb error] localizedDescription]); continue;
        }

        NSMutableString *out = [NSMutableString stringWithFormat:
            @"{\"id\":\"%@\",\"status\":\"OK\",\"gputime_ns\":%llu,\"raw\":\"",
            rid, (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9)];
        NSUInteger nb = W * H * bpp;
        uint8_t *px = (uint8_t *)malloc(nb);
        for (NSUInteger i = 0; i < NRT; i++) {
            [tex[i] getBytes:px bytesPerRow:W * bpp
                  fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
            hexcat(out, px, nb);
        }
        [out appendString:@"\""];
        if (WANTPX && FMT == MTLPixelFormatRGBA32Float) {
            [out appendString:@",\"pixels\":["];
            BOOL first = YES;
            for (NSUInteger i = 0; i < NRT; i++) {
                [tex[i] getBytes:px bytesPerRow:W * bpp
                      fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
                float *f = (float *)px;
                for (NSUInteger p = 0; p < W * H; p++) {
                    [out appendString:(first ? @"[" : @",[")];
                    for (int k = 0; k < 4; k++) appendNum(out, (double)f[p*4+k], k > 0);
                    [out appendString:@"]"];
                    first = NO;
                }
            }
            [out appendString:@"]"];
        }
        free(px);
        if (ob) {
            [out appendString:@",\"outbuf\":\""];
            hexcat(out, (const uint8_t *)[ob contents], OUTB);
            [out appendString:@"\""];
        }
        [out appendString:@"}\n"];
        fputs([out UTF8String], stdout);
        fflush(stdout);
    }}
    free(line);
    return 0;
}}
