/*
 * EXP-0132 render-pass / attachment-descriptor probe.
 *
 * Forked from EXP-0108-m4-bg-eot-programs/harness/probe.m (same authored-MSL,
 * JSON-config-driven, one-case-per-process design: read argv[1] JSON config,
 * render it, print one JSON result line to argv[2], optionally trigger a
 * wtrace.dylib descriptor snapshot). This probe inspects only its own
 * generated MSL, its own buffer/texture readback bytes, and Metal API return
 * values/errors; it never reads BO content itself (that is wtrace.c's job,
 * gated by its own frozen content-capture policy).
 *
 * New over EXP-0108, for this experiment's own priorities:
 *
 *   1. Attachment-0 ARRAY (arrayLength/slice) and MIP (mipCount/level)
 *      support -- DRV-PBE-01 explicitly requires "layer/mip/... array
 *      selection" field decoding, which EXP-0108's matrix never exercised.
 *      When arrayLength>1 or mipCount>1, attachment 0 is allocated as a
 *      plain (non-buffer-backed) MTLStorageModeShared texture, pre-filled
 *      with a distinct per-(slice,level) canary byte pattern, and read back
 *      at EVERY requested (slice,level) after the render -- not just the
 *      one targeted by the render pass -- so a boundary/invalid slice or
 *      level can be checked for silent-zero, clamp, alias-into-neighbor, or
 *      untouched-vs-corrupted behavior, not just command-buffer success.
 *   2. The race FIX (see harness/wtrace.c file header): if the interposer
 *      is loaded, this probe calls its exported `wtrace_snapshot_now()`
 *      directly via dlsym (synchronous, in-process, same thread, right
 *      after waitUntilCompleted) instead of `kill(getpid(), SIGUSR1)` +
 *      sleep. No signal, no separate handler thread, no send/receive race.
 *   3. A boundary case (deliberately invalid slice/level/etc.) is expected,
 *      per this project's own prior findings (EXP-0117), to sometimes raise
 *      a FATAL, uncatchable Metal API validation assertion (SIGABRT) rather
 *      than a graceful NSError. This probe therefore still writes nothing
 *      it cannot -- the calling run.py invokes one case per subprocess (as
 *      EXP-0108/EXP-0117/EXP-0095 already do) and classifies a negative
 *      subprocess return code as PROCESS_ABORT, a contained, expected,
 *      pre-registered result, never a harness fault.
 */
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <dlfcn.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static MTLPixelFormat fmt_from_name(NSString *s) {
    struct { const char *n; MTLPixelFormat f; } tbl[] = {
        {"RGBA8Unorm", MTLPixelFormatRGBA8Unorm},
        {"BGRA8Unorm", MTLPixelFormatBGRA8Unorm},
        {"RGBA8Unorm_sRGB", MTLPixelFormatRGBA8Unorm_sRGB},
        {"R32Float", MTLPixelFormatR32Float},
        {"R32Uint", MTLPixelFormatR32Uint},
        {"RGBA16Float", MTLPixelFormatRGBA16Float},
        {"R8Unorm", MTLPixelFormatR8Unorm},
        {"RG8Unorm", MTLPixelFormatRG8Unorm},
        {"Depth32Float", MTLPixelFormatDepth32Float},
        {"Stencil8", MTLPixelFormatStencil8},
        {"Depth32Float_Stencil8", MTLPixelFormatDepth32Float_Stencil8},
    };
    for (size_t i = 0; i < sizeof(tbl)/sizeof(tbl[0]); ++i)
        if ([s isEqualToString:@(tbl[i].n)]) return tbl[i].f;
    return MTLPixelFormatInvalid;
}

static MTLLoadAction load_from_name(NSString *s) {
    if ([s isEqualToString:@"Clear"]) return MTLLoadActionClear;
    if ([s isEqualToString:@"Load"]) return MTLLoadActionLoad;
    return MTLLoadActionDontCare;
}

static MTLStoreAction store_from_name(NSString *s) {
    if ([s isEqualToString:@"Store"]) return MTLStoreActionStore;
    if ([s isEqualToString:@"MultisampleResolve"]) return MTLStoreActionMultisampleResolve;
    if ([s isEqualToString:@"StoreAndMultisampleResolve"]) return MTLStoreActionStoreAndMultisampleResolve;
    return MTLStoreActionDontCare;
}

static NSString *elem_type_for_fmt(MTLPixelFormat f) {
    if (f == MTLPixelFormatR32Uint) return @"uint4";
    return @"float4";
}

static void write_result_and_exit(NSMutableDictionary *result, NSString *argv2,
                                   const char *statusLiteral) __attribute__((noreturn));
static void write_result_and_exit(NSMutableDictionary *result, NSString *argv2,
                                   const char *statusLiteral) {
    NSData *out = [NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
    [out writeToFile:argv2 atomically:NO];
    printf("STATUS %s\n", statusLiteral);
    fflush(stdout);
    exit(0);
}

int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc < 3) { fprintf(stderr, "usage: probe <case.json> <result.json> [--dump]\n"); return 2; }
        int do_dump = (argc > 3 && !strcmp(argv[3], "--dump"));
        NSError *err = nil;
        NSData *cfgData = [NSData dataWithContentsOfFile:@(argv[1])];
        if (!cfgData) { fprintf(stderr, "CONFIG_READ_FAIL\n"); return 2; }
        NSDictionary *cfg = [NSJSONSerialization JSONObjectWithData:cfgData options:0 error:&err];
        if (!cfg) { fprintf(stderr, "CONFIG_PARSE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 2; }

        NSMutableDictionary *result = [NSMutableDictionary dictionary];
        result[@"name"] = cfg[@"name"];

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "NO_DEVICE\n"); return 3; }
        result[@"device"] = [dev name];

        NSInteger ncolor = [cfg[@"ncolor"] integerValue];
        NSArray *fmtNames = cfg[@"fmt"];
        NSArray *loadNames = cfg[@"load"];
        NSArray *storeNames = cfg[@"store"];
        NSArray *memless = cfg[@"memoryless"];
        NSInteger samples = [cfg[@"samples"] integerValue];
        BOOL depth = [cfg[@"depth"] boolValue];
        BOOL depthWrite = [cfg[@"depthWrite"] boolValue];
        BOOL depthMemoryless = [cfg[@"depthMemoryless"] boolValue];
        NSString *depthLoadN = cfg[@"depthLoad"], *depthStoreN = cfg[@"depthStore"];
        BOOL stencil = [cfg[@"stencil"] boolValue];
        BOOL stencilWrite = [cfg[@"stencilWrite"] boolValue];
        NSString *stencilLoadN = cfg[@"stencilLoad"], *stencilStoreN = cfg[@"stencilStore"];
        BOOL draw = [cfg[@"draw"] boolValue];
        NSUInteger W = [cfg[@"width"] unsignedIntegerValue], H = [cfg[@"height"] unsignedIntegerValue];
        NSUInteger instances = [cfg[@"instances"] unsignedIntegerValue];
        NSUInteger arrayLength = cfg[@"arrayLength"] ? [cfg[@"arrayLength"] unsignedIntegerValue] : 1;
        NSUInteger slice = [cfg[@"slice"] unsignedIntegerValue];
        NSUInteger mipCount = cfg[@"mipCount"] ? [cfg[@"mipCount"] unsignedIntegerValue] : 1;
        NSUInteger level = [cfg[@"level"] unsignedIntegerValue];
        /* cfg[@"readback_slices"/"readback_levels"] is JSON `null` -> NSNull
         * (not nil) for the common case; guard explicitly rather than
         * relying on Objective-C truthiness (NSNull is a real, "truthy"
         * object -- caught by this experiment's own pre-capture smoke test,
         * see PROGRESS.md). */
        id readbackSlicesRaw = cfg[@"readback_slices"];
        id readbackLevelsRaw = cfg[@"readback_levels"];
        NSArray *readbackSlices = [readbackSlicesRaw isKindOfClass:[NSArray class]] ? readbackSlicesRaw : nil;
        NSArray *readbackLevels = [readbackLevelsRaw isKindOfClass:[NSArray class]] ? readbackLevelsRaw : nil;

        MTLPixelFormat fmt[4]; BOOL ml[4];
        for (NSInteger i = 0; i < ncolor; ++i) {
            fmt[i] = fmt_from_name(fmtNames[i]);
            ml[i] = [memless[i] boolValue];
            if (fmt[i] == MTLPixelFormatInvalid) { fprintf(stderr, "BAD_FORMAT %ld\n", (long)i); return 2; }
        }

        NSString *vsrc =
            @"#include <metal_stdlib>\nusing namespace metal;\n"
             "struct VO { float4 pos [[position]]; };\n"
             "vertex VO v_main(uint vid [[vertex_id]], uint iid [[instance_id]]) {\n"
             "  float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};\n"
             "  float j = fract(float(iid) * 0.6180339887) * 0.0005;\n"
             "  VO o; o.pos=float4(p[vid]+j,0,1); return o;\n"
             "}\n";
        NSMutableString *fbody = [NSMutableString stringWithString:
            @"#include <metal_stdlib>\nusing namespace metal;\n"
             "struct VO { float4 pos [[position]]; };\n"
             "struct FO {\n"];
        for (NSInteger i = 0; i < ncolor; ++i)
            [fbody appendFormat:@"  %@ c%ld [[color(%ld)]];\n", elem_type_for_fmt(fmt[i]), (long)i, (long)i];
        [fbody appendString:@"};\n"
             "fragment FO f_main(VO in [[stage_in]]) {\n"
             "  (void)in; FO o;\n"];
        for (NSInteger i = 0; i < ncolor; ++i) {
            if (fmt[i] == MTLPixelFormatR32Uint)
                [fbody appendFormat:@"  o.c%ld = uint4(37u,0u,0u,1u);\n", (long)i];
            else
                [fbody appendFormat:@"  o.c%ld = float4(0.25,0.5,0.75,0.5);\n", (long)i];
        }
        [fbody appendString:@"  return o;\n}\n"];

        id<MTLLibrary> vl = [dev newLibraryWithSource:vsrc options:nil error:&err];
        if (!vl) { fprintf(stderr, "VERTEX_COMPILE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 5; }
        id<MTLLibrary> fl = [dev newLibraryWithSource:fbody options:nil error:&err];
        if (!fl) { fprintf(stderr, "FRAGMENT_COMPILE_FAIL %s\n%s\n",
                           [[err localizedDescription] UTF8String], [fbody UTF8String]); return 6; }

        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = [vl newFunctionWithName:@"v_main"];
        pd.fragmentFunction = [fl newFunctionWithName:@"f_main"];
        pd.rasterSampleCount = (NSUInteger)samples;
        for (NSInteger i = 0; i < ncolor; ++i) pd.colorAttachments[i].pixelFormat = fmt[i];
        if (depth) pd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
        if (stencil) pd.stencilAttachmentPixelFormat = MTLPixelFormatStencil8;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if (!pso) {
            result[@"status"] = @"PIPELINE_FAIL";
            result[@"error"] = [err localizedDescription] ?: @"unknown";
            write_result_and_exit(result, @(argv[2]), "PIPELINE_FAIL");
        }

        id<MTLDepthStencilState> dss = nil;
        if (depthWrite || stencilWrite) {
            MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
            dsd.depthCompareFunction = MTLCompareFunctionAlways;
            dsd.depthWriteEnabled = depthWrite;
            if (stencilWrite) {
                MTLStencilDescriptor *sd = [MTLStencilDescriptor new];
                sd.stencilCompareFunction = MTLCompareFunctionAlways;
                sd.depthStencilPassOperation = MTLStencilOperationReplace;
                dsd.frontFaceStencil = sd; dsd.backFaceStencil = sd;
            }
            dss = [dev newDepthStencilStateWithDescriptor:dsd];
        }

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        id<MTLTexture> colorTex[4] = {0}, resolveTex[4] = {0};
        NSUInteger arrayLenFor[4] = {0}, mipCountFor[4] = {0};

        /* IMPORTANT (this experiment's own pre-capture diagnostic, see
         * PRE_REGISTRATION.md / PROGRESS.md): EXP-0108's probe.m allocated a
         * client MTLBuffer (newBufferWithLength: then newTextureWithDescriptor:
         * offset:bytesPerRow:) as the buffer-backed color target for small
         * (32x32) cases. In a two-run dry check of THIS harness, that
         * client buffer's own gpuAddress landed EXACTLY on the fixed VA
         * `0x10000018200` that harness/wtrace.c's known-role table treats as
         * "mrt-attachment-descriptors" -- i.e. it aliased the very role this
         * experiment exists to decode, silently substituting our own pixel
         * bytes for the real descriptor content (EXP-0048's own
         * raw/preflight_failures.md flagged exactly this class of VA
         * coincidence). Removed at the root: every color/resolve attachment
         * here is a plain (non-buffer-backed) MTLStorageModeShared texture,
         * never a client MTLBuffer, so there is no client-buffer allocation
         * competing for the same VA class as the tiler-heap descriptor
         * arena. Readback uses getBytes:bytesPerRow:bytesPerImage:
         * fromRegion:mipmapLevel:slice: uniformly (works directly on
         * Shared-storage textures on this unified-memory hardware). Every
         * (slice,level) is pre-filled with a distinct canary byte pattern
         * before the render so an out-of-range slice/level can be checked
         * for aliasing into a neighbor vs. staying untouched. */
        for (NSInteger i = 0; i < ncolor; ++i) {
            BOOL memoryless = ml[i];
            NSUInteger al = (i == 0) ? MAX((NSUInteger)1, arrayLength) : 1;
            NSUInteger mc = (i == 0) ? MAX((NSUInteger)1, mipCount) : 1;
            arrayLenFor[i] = al; mipCountFor[i] = mc;
            MTLTextureDescriptor *td = [MTLTextureDescriptor new];
            td.textureType = (al > 1) ? MTLTextureType2DArray
                            : ((samples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D);
            td.pixelFormat = fmt[i];
            td.width = W; td.height = H;
            td.arrayLength = al;
            td.mipmapLevelCount = mc;
            td.sampleCount = (NSUInteger)((al > 1) ? 1 : samples);
            td.usage = MTLTextureUsageRenderTarget;
            td.storageMode = memoryless ? MTLStorageModeMemoryless : MTLStorageModeShared;
            colorTex[i] = [dev newTextureWithDescriptor:td];
            /* replaceRegion is invalid on a multisample texture (Metal
             * validation rejects it); skip the canary pre-fill there --
             * MSAA correctness/readback is covered via the resolve target
             * instead, allocated separately below as a genuine 1x texture. */
            if (colorTex[i] && !memoryless && samples == 1) {
                for (NSUInteger s = 0; s < al; ++s) {
                    for (NSUInteger lv = 0; lv < mc; ++lv) {
                        NSUInteger lw = MAX((NSUInteger)1, W >> lv), lh = MAX((NSUInteger)1, H >> lv);
                        NSUInteger lbpr = lw * 4;
                        uint8_t canary = (uint8_t)(0xA0 + (s * 16 + lv));
                        NSMutableData *fill = [NSMutableData dataWithLength:lbpr * lh];
                        memset([fill mutableBytes], canary, [fill length]);
                        MTLRegion region = MTLRegionMake2D(0, 0, lw, lh);
                        [colorTex[i] replaceRegion:region mipmapLevel:lv slice:s
                            withBytes:[fill bytes] bytesPerRow:lbpr bytesPerImage:0];
                    }
                }
            }
            MTLStoreAction sa = store_from_name(storeNames[i]);
            if (sa == MTLStoreActionMultisampleResolve || sa == MTLStoreActionStoreAndMultisampleResolve) {
                MTLTextureDescriptor *rtd = [MTLTextureDescriptor new];
                rtd.textureType = MTLTextureType2D;
                rtd.pixelFormat = fmt[i]; rtd.width = W; rtd.height = H; rtd.sampleCount = 1;
                rtd.usage = MTLTextureUsageRenderTarget;
                rtd.storageMode = MTLStorageModeShared;
                resolveTex[i] = [dev newTextureWithDescriptor:rtd];
                if (resolveTex[i]) {
                    NSMutableData *fill = [NSMutableData dataWithLength:W * 4 * H];
                    memset([fill mutableBytes], 0xa5, [fill length]);
                    MTLRegion region = MTLRegionMake2D(0, 0, W, H);
                    [resolveTex[i] replaceRegion:region mipmapLevel:0 slice:0
                        withBytes:[fill bytes] bytesPerRow:W * 4 bytesPerImage:0];
                }
            }
            if (!colorTex[i]) {
                result[@"status"] = @"COLOR_TEXTURE_CREATE_FAIL";
                write_result_and_exit(result, @(argv[2]), "COLOR_TEXTURE_CREATE_FAIL");
            }
            rp.colorAttachments[i].texture = colorTex[i];
            rp.colorAttachments[i].loadAction = load_from_name(loadNames[i]);
            rp.colorAttachments[i].storeAction = store_from_name(storeNames[i]);
            rp.colorAttachments[i].clearColor = MTLClearColorMake(0.125, 0.25, 0.375, 0.5);
            if (resolveTex[i]) rp.colorAttachments[i].resolveTexture = resolveTex[i];
            if (i == 0 && al > 1) rp.colorAttachments[i].slice = slice;
            if (i == 0 && mc > 1) rp.colorAttachments[i].level = level;
        }

        if (depth) {
            MTLTextureDescriptor *td = [MTLTextureDescriptor
                texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float width:W height:H mipmapped:NO];
            td.textureType = (samples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
            td.sampleCount = (NSUInteger)samples;
            td.usage = MTLTextureUsageRenderTarget;
            td.storageMode = depthMemoryless ? MTLStorageModeMemoryless : MTLStorageModePrivate;
            id<MTLTexture> depthTex = [dev newTextureWithDescriptor:td];
            if (!depthTex) {
                result[@"status"] = @"DEPTH_TEXTURE_CREATE_FAIL";
                write_result_and_exit(result, @(argv[2]), "DEPTH_TEXTURE_CREATE_FAIL");
            }
            rp.depthAttachment.texture = depthTex;
            rp.depthAttachment.loadAction = load_from_name(depthLoadN);
            rp.depthAttachment.storeAction = store_from_name(depthStoreN);
            rp.depthAttachment.clearDepth = 0.75;
        }
        if (stencil) {
            MTLTextureDescriptor *td = [MTLTextureDescriptor
                texture2DDescriptorWithPixelFormat:MTLPixelFormatStencil8 width:W height:H mipmapped:NO];
            td.textureType = (samples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
            td.sampleCount = (NSUInteger)samples;
            td.usage = MTLTextureUsageRenderTarget;
            td.storageMode = MTLStorageModePrivate;
            id<MTLTexture> stencilTex = [dev newTextureWithDescriptor:td];
            if (!stencilTex) {
                result[@"status"] = @"STENCIL_TEXTURE_CREATE_FAIL";
                write_result_and_exit(result, @(argv[2]), "STENCIL_TEXTURE_CREATE_FAIL");
            }
            rp.stencilAttachment.texture = stencilTex;
            rp.stencilAttachment.loadAction = load_from_name(stencilLoadN);
            rp.stencilAttachment.storeAction = store_from_name(stencilStoreN);
            rp.stencilAttachment.clearStencil = 0x55;
        }

        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc = nil;
        @try {
            enc = [cb renderCommandEncoderWithDescriptor:rp];
        } @catch (NSException *exn) {
            result[@"status"] = @"NSEXCEPTION_ENCODER";
            result[@"exception_name"] = [exn name] ?: @"unknown";
            result[@"exception_reason"] = [exn reason] ?: @"unknown";
            write_result_and_exit(result, @(argv[2]), "NSEXCEPTION_ENCODER");
        }
        if (!enc) {
            result[@"status"] = @"ENCODER_CREATE_FAIL";
            write_result_and_exit(result, @(argv[2]), "ENCODER_CREATE_FAIL");
        }
        @try {
            [enc setRenderPipelineState:pso];
            if (dss) [enc setDepthStencilState:dss];
            [enc setStencilReferenceValue:0xAA];
            MTLViewport viewport = {0, 0, (double)W, (double)H, 0, 1};
            [enc setViewport:viewport];
            if (draw) [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:instances];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
        } @catch (NSException *exn) {
            result[@"status"] = @"NSEXCEPTION_ENCODE";
            result[@"exception_name"] = [exn name] ?: @"unknown";
            result[@"exception_reason"] = [exn reason] ?: @"unknown";
            write_result_and_exit(result, @(argv[2]), "NSEXCEPTION_ENCODE");
        }

        result[@"cb_status"] = @((long)[cb status]);
        result[@"cb_error"] = [cb error] ? [[[cb error] localizedDescription] description] : [NSNull null];
        result[@"status"] = ([cb status] == MTLCommandBufferStatusCompleted && ![cb error]) ? @"OK" : @"CMDBUF_ERROR";

        /* Uniform readback for every color attachment via getBytes (no
         * client MTLBuffer is ever allocated for a color/resolve target in
         * this probe -- see the allocation-loop comment above for why).
         * Attachment 0 reads back every requested (slice,level) cell (the
         * alias/clamp/silent-zero boundary detector); attachments >0 (MRT
         * companions, never array/mip in this matrix) read back their
         * single (0,0) cell in the same "cells" shape for schema
         * uniformity. */
        NSMutableArray *rts = [NSMutableArray array];
        for (NSInteger i = 0; i < ncolor; ++i) {
            NSMutableArray *cells = [NSMutableArray array];
            NSArray *slicesToRead = (i == 0 && readbackSlices) ? readbackSlices : @[@(0)];
            NSArray *levelsToRead = (i == 0 && readbackLevels) ? readbackLevels : @[@(0)];
            for (NSNumber *sN in slicesToRead) {
                NSUInteger s = [sN unsignedIntegerValue];
                if (s >= arrayLenFor[i]) continue; /* only read back in-bounds slices */
                for (NSNumber *lN in levelsToRead) {
                    NSUInteger lv = [lN unsignedIntegerValue];
                    if (lv >= mipCountFor[i]) continue;
                    NSUInteger lw = MAX((NSUInteger)1, W >> lv);
                    NSUInteger lbpr = lw * 4;
                    uint8_t px[4] = {0,0,0,0};
                    MTLRegion region = MTLRegionMake2D(0, 0, 1, 1);
                    if (!ml[i] && samples == 1) {
                        /* getBytes is likewise invalid directly on a
                         * multisample texture; MSAA cases read back only
                         * via resolveTex below (colorTex[i] cells stay the
                         * zeroed placeholder for those cases). */
                        [colorTex[i] getBytes:px bytesPerRow:lbpr bytesPerImage:0
                            fromRegion:region mipmapLevel:lv slice:s];
                    }
                    char hex[9];
                    snprintf(hex, sizeof(hex), "%02x%02x%02x%02x", px[0], px[1], px[2], px[3]);
                    [cells addObject:@{@"slice": @(s), @"level": @(lv), @"first4_hex": @(hex)}];
                }
            }
            NSMutableDictionary *rt = [NSMutableDictionary dictionaryWithDictionary:@{@"i": @(i), @"cells": cells}];
            if (resolveTex[i]) {
                uint8_t px[4] = {0,0,0,0};
                MTLRegion region = MTLRegionMake2D(0, 0, 1, 1);
                [resolveTex[i] getBytes:px bytesPerRow:W * 4 bytesPerImage:0
                    fromRegion:region mipmapLevel:0 slice:0];
                char hex[9];
                snprintf(hex, sizeof(hex), "%02x%02x%02x%02x", px[0], px[1], px[2], px[3]);
                rt[@"resolve_first4_hex"] = @(hex);
            }
            [rts addObject:rt];
        }
        result[@"rts"] = rts;

        NSData *out = [NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
        [out writeToFile:@(argv[2]) atomically:NO];
        printf("STATUS %s\n", [result[@"status"] UTF8String]);
        fflush(stdout);
        if (do_dump) {
            void (*direct)(void) = (void (*)(void))dlsym(RTLD_DEFAULT, "wtrace_snapshot_now");
            if (direct) {
                direct();
            } else {
                /* Safety: do NOT fall back to kill(getpid(), SIGUSR1) here. If
                 * the interposer dylib failed to load (env misconfiguration,
                 * wrong DYLD_INSERT_LIBRARIES path), there is no signal
                 * handler installed for SIGUSR1 and its default disposition
                 * terminates the process -- turning a harmless "no dump
                 * available" condition into a fatal, misleading-looking
                 * crash (this was caught during this experiment's own
                 * harness development, see PROGRESS.md). Fail loud but safe:
                 * report the miss on stderr and exit 0 with no dump. The
                 * caller (run.py) treats a missing dump as its own
                 * detectable condition (no inventory.tsv under the expected
                 * dump dir), not a silent gap.
                 */
                fprintf(stderr, "WTRACE_DIRECT_SNAPSHOT_UNAVAILABLE (dylib not loaded?)\n");
            }
        }
        return 0;
    }
}
